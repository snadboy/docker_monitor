"""
FastAPI REST API Server

This module provides the FastAPI-based REST API server with health endpoints,
container discovery, service management, and a web dashboard.
"""

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from datetime import datetime
from typing import Dict, List, Optional, Any, TYPE_CHECKING
import logging
from pydantic import BaseModel

if TYPE_CHECKING:
    from .managers import DockerHostManager
    from .processors import ContainerProcessor

from .schemas import get_planned_services


# Pydantic models for response validation
class HealthStatus(BaseModel):
    status: str
    timestamp: str
    uptime_seconds: float
    docker_hosts: Dict[str, Any]
    persistent_errors: Optional[Dict[str, Any]]
    monitored_containers: int
    caddy: Dict[str, Any]
    version: str


class ContainerInfo(BaseModel):
    name: str
    short_id: str
    status: str
    host_ip: Optional[str]
    docker_host_name: str
    snadboy_labels: Dict[str, str]
    primary_docker_ip: Optional[str]
    docker_networks: Dict[str, Any]
    docker_ips: List[str]
    exposed_ports: List[str]


class ContainersResponse(BaseModel):
    containers: List[Dict[str, Any]]
    count: int


class SimpleHealthResponse(BaseModel):
    status: str
    connected_hosts: Optional[int] = None
    reason: Optional[str] = None
    failed_hosts: Optional[List[str]] = None


class ReadinessResponse(BaseModel):
    status: str
    connected_hosts: Optional[int] = None
    total_containers: Optional[int] = None
    reason: Optional[str] = None
    error: Optional[str] = None


class APIServer:
    """FastAPI REST API server with enhanced health endpoints"""
    
    def __init__(self, monitored_containers: Dict, host_manager: 'DockerHostManager', logger: logging.Logger, config: Dict, container_processor: 'ContainerProcessor' = None):
        self.monitored_containers = monitored_containers
        self.host_manager = host_manager
        self.logger = logger
        self.config = config
        self.container_processor = container_processor
        self.app = self._setup_fastapi_app()
        self.start_time = datetime.now()
        self.caddy_manager = None  # Will be set externally if Caddy is enabled
    
    def _get_caddy_health_status(self) -> Dict:
        """Get Caddy health status"""
        if self.caddy_manager:
            return {
                'enabled': True,
                'available': self.caddy_manager.caddy_available,
                'admin_url': self.caddy_manager.caddy_admin_url,
                'managed_routes': len(self.caddy_manager.managed_routes),
                'last_health_check': datetime.fromtimestamp(self.caddy_manager.last_health_check).isoformat() if self.caddy_manager.last_health_check > 0 else None
            }
        else:
            return {'enabled': False}
    
    def _setup_fastapi_app(self) -> FastAPI:
        """Setup FastAPI application with all endpoints"""
        app = FastAPI(
            title="Enhanced Docker Monitor API",
            description="Production-ready Docker container monitoring with persistent error tracking, intelligent connection recovery, and service registry validation",
            version="2.5.0-enhanced-health",
            docs_url="/docs",
            redoc_url="/redoc"
        )
        
        @app.get("/", response_model=Dict[str, Any])
        @app.get("/help", response_model=Dict[str, Any])
        async def api_help():
            """API documentation and endpoint discovery"""
            endpoints = {
                'health_monitoring': {
                    '/health': {
                        'method': 'GET',
                        'description': 'Detailed health status with error information',
                        'response': 'JSON with host status, errors, and container counts',
                        'http_codes': '200 (healthy/degraded), 503 (unhealthy)'
                    },
                    '/healthz': {
                        'method': 'GET', 
                        'description': 'Kubernetes-style health check',
                        'response': 'Simple health status for container orchestration',
                        'http_codes': '200 (healthy), 503 (unhealthy - triggers restart)'
                    },
                    '/readiness': {
                        'method': 'GET',
                        'description': 'Readiness probe for container orchestration', 
                        'response': 'Service readiness status',
                        'http_codes': '200 (ready), 503 (not ready)'
                    },
                    '/errors': {
                        'method': 'GET',
                        'description': 'Detailed SSH connection error analysis',
                        'response': 'Host errors with recovery timings and backoff delays',
                        'http_codes': '200'
                    }
                },
                'container_management': {
                    '/containers': {
                        'method': 'GET',
                        'description': 'List all monitored containers with snadboy labels',
                        'response': 'Array of container objects with metadata',
                        'http_codes': '200'
                    },
                    '/containers/{id}': {
                        'method': 'GET',
                        'description': 'Get specific container details by ID or short ID',
                        'response': 'Single container object',
                        'http_codes': '200 (found), 404 (not found)'
                    },
                    '/containers/summary': {
                        'method': 'GET',
                        'description': 'Container summary grouped by host IP',
                        'response': 'Containers grouped by host with basic info',
                        'http_codes': '200'
                    }
                },
                'service_configuration': {
                    '/services/schema': {
                        'method': 'GET',
                        'description': 'Get supported service types and validation schemas',
                        'response': 'Service registry with types, properties, examples',
                        'http_codes': '200'
                    },
                    '/labels': {
                        'method': 'GET',
                        'description': 'Get all snadboy labels from monitored containers',
                        'response': 'Container labels organized by container name',
                        'http_codes': '200'
                    }
                },
                'caddy_integration': {
                    '/caddy': {
                        'method': 'GET',
                        'description': 'Get container info formatted for Caddy reverse proxy',
                        'response': 'Services with routing information for Caddy',
                        'http_codes': '200'
                    },
                    '/caddy/status': {
                        'method': 'GET',
                        'description': 'Get detailed Caddy integration status',
                        'response': 'Caddy availability, managed routes, configuration',
                        'http_codes': '200'
                    }
                },
                'network_information': {
                    '/ips': {
                        'method': 'GET',
                        'description': 'Get container IP addresses (host and Docker IPs)',
                        'response': 'IP mapping for containers across hosts',
                        'http_codes': '200'
                    }
                },
                'debugging': {
                    '/debug': {
                        'method': 'GET',
                        'description': 'Debug information for troubleshooting',
                        'response': 'Complete system state, hosts, containers, errors',
                        'http_codes': '200'
                    }
                },
                'documentation': {
                    '/': {
                        'method': 'GET',
                        'description': 'API documentation (this endpoint)',
                        'response': 'Complete API reference',
                        'http_codes': '200'
                    },
                    '/help': {
                        'method': 'GET',
                        'description': 'API documentation (alias for /)',
                        'response': 'Complete API reference',
                        'http_codes': '200'
                    },
                    '/dashboard': {
                        'method': 'GET',
                        'description': 'Web dashboard with light/dark theme and auto-refresh',
                        'response': 'Interactive HTML dashboard for monitoring',
                        'http_codes': '200'
                    }
                }
            }
            
            usage_examples = {
                'health_monitoring': [
                    'curl http://localhost:8080/health',
                    'curl http://localhost:8080/healthz',
                    'curl http://localhost:8080/errors'
                ],
                'container_discovery': [
                    'curl http://localhost:8080/containers',
                    'curl http://localhost:8080/containers/abc123',
                    'curl http://localhost:8080/labels'
                ],
                'service_management': [
                    'curl http://localhost:8080/services/schema',
                    'curl http://localhost:8080/caddy',
                    'curl http://localhost:8080/ips'
                ],
                'troubleshooting': [
                    'curl http://localhost:8080/debug',
                    'curl http://localhost:8080/errors',
                    'curl http://localhost:8080/caddy/status'
                ]
            }
            
            service_example = {
                'description': 'Example snadboy service labels using the service registry',
                'reverse_proxy': {
                    'snadboy.revp.domain': 'app.example.com',
                    'snadboy.revp.port': '80',
                    'snadboy.revp.path': '/',
                    'snadboy.revp.ssl': 'true'
                },
                'api_service': {
                    'snadboy.api.domain': 'api.example.com',
                    'snadboy.api.port': '8080',
                    'snadboy.api.path': '/api/v1',
                    'snadboy.api.auth': 'bearer'
                },
                'multiple_services': {
                    'snadboy.web.domain': 'app.example.com',
                    'snadboy.web.port': '80',
                    'snadboy.api.domain': 'api.example.com', 
                    'snadboy.api.port': '8080',
                    'snadboy.metrics.domain': 'metrics.example.com',
                    'snadboy.metrics.port': '9090'
                }
            }
            
            return {
                'service_name': 'Enhanced Docker Monitor API',
                'version': '2.5.0-enhanced-health',
                'description': 'Production-ready Docker container monitoring with persistent error tracking, intelligent connection recovery, and service registry validation',
                'base_url': str(self.config.get('api_base_url', 'http://localhost:8080')),
                'endpoints': endpoints,
                'usage_examples': usage_examples,
                'service_labels': service_example,
                'features': [
                    'Multi-host Docker monitoring (local + SSH)',
                    'Persistent error tracking with exponential backoff',
                    'Container orchestration health checks (K8s, Docker Swarm)', 
                    'Caddy reverse proxy integration',
                    'Service registry with schema validation',
                    'Real-time SSH diagnostics and troubleshooting',
                    'Background connection recovery',
                    'Comprehensive REST API'
                ],
                'supported_service_types': ['revp'],  # Only implemented service type
                'planned_service_types': ['api', 'web', 'db', 'metrics'],  # Documented but not implemented
                'quick_start': {
                    'health_check': 'curl http://localhost:8080/healthz',
                    'list_containers': 'curl http://localhost:8080/containers',
                    'view_errors': 'curl http://localhost:8080/errors',
                    'service_schema': 'curl http://localhost:8080/services/schema',
                    'debug_info': 'curl http://localhost:8080/debug'
                },
                'documentation': 'See README.md for complete documentation and deployment guides',
                'timestamp': datetime.now().isoformat()
            }
        
        @app.get("/dashboard", response_class=HTMLResponse)
        async def web_dashboard():
            """Web dashboard for container monitoring"""
            return self._get_dashboard_html()
        
        @app.get("/health", response_model=HealthStatus, responses={503: {"model": HealthStatus}})
        async def health_check():
            """Enhanced health check with persistent error tracking"""
            connected_hosts = 0
            failed_hosts = 0
            host_status = {}
            
            # Test all connections and get current state
            connection_results = self.host_manager.test_all_connections()
            
            for host_name, is_connected in connection_results.items():
                if is_connected:
                    host_status[host_name] = 'healthy'
                    connected_hosts += 1
                else:
                    host = self.host_manager.hosts.get(host_name)
                    if host:
                        error_msg = host.error_message or 'Connection failed'
                        host_status[host_name] = f'unhealthy: {error_msg}'
                    else:
                        host_status[host_name] = 'unhealthy: host not found'
                    failed_hosts += 1
            
            # Get persistent error details
            host_errors = self.host_manager.get_host_errors()
            
            # Determine overall health status and HTTP response code
            total_hosts = len(self.host_manager.hosts)
            if connected_hosts == 0:
                overall_status = 'unhealthy'
                http_status = 503  # Service Unavailable
            elif failed_hosts > 0:
                overall_status = 'degraded'
                http_status = 200  # Still functional but degraded
            else:
                overall_status = 'healthy'
                http_status = 200
            
            uptime = (datetime.now() - self.start_time).total_seconds()
            
            response_data = HealthStatus(
                status=overall_status,
                timestamp=datetime.now().isoformat(),
                uptime_seconds=uptime,
                docker_hosts={
                    'total': total_hosts,
                    'connected': connected_hosts,
                    'failed': failed_hosts,
                    'status_details': host_status
                },
                persistent_errors=host_errors if host_errors else None,
                monitored_containers=len(self.monitored_containers),
                caddy=self._get_caddy_health_status(),
                version='2.5.0-enhanced-health'
            )
            
            if http_status == 503:
                return JSONResponse(content=response_data.dict(), status_code=503)
            return response_data
        
        @app.get("/healthz", response_model=SimpleHealthResponse, responses={503: {"model": SimpleHealthResponse}})
        async def kubernetes_health():
            """Kubernetes-style health check that returns appropriate HTTP codes"""
            connected_hosts = len([h for h in self.host_manager.hosts.values() if h.status == 'connected'])
            
            if connected_hosts == 0:
                # No Docker hosts available - container should be marked unhealthy
                return JSONResponse(
                    content={'status': 'unhealthy', 'reason': 'no_docker_hosts'},
                    status_code=503
                )
            
            # Check for critical errors (hosts with persistent failures)
            critical_errors = [
                host_name for host_name, error_info in self.host_manager.host_errors.items()
                if error_info.get('consecutive_failures', 0) > 3
            ]
            
            if len(critical_errors) >= connected_hosts:
                # All connected hosts have critical errors
                return JSONResponse(
                    content={'status': 'unhealthy', 'reason': 'critical_host_errors', 'failed_hosts': critical_errors},
                    status_code=503
                )
            
            # Service is healthy enough to handle requests
            return SimpleHealthResponse(status='healthy', connected_hosts=connected_hosts)
        
        @app.get("/readiness", response_model=ReadinessResponse, responses={503: {"model": ReadinessResponse}})
        async def readiness_check():
            """Readiness probe - checks if service can handle requests"""
            # Service is ready if we have at least one connected host
            connected_hosts = len([h for h in self.host_manager.hosts.values() if h.status == 'connected'])
            
            if connected_hosts == 0:
                return JSONResponse(
                    content={'status': 'not_ready', 'reason': 'no_connected_hosts'},
                    status_code=503
                )
            
            # Additional readiness check: ensure we can actually list containers
            try:
                containers = self.host_manager.get_all_containers()
                total_containers = sum(len(containers) for containers in containers.values())
                
                return ReadinessResponse(
                    status='ready',
                    connected_hosts=connected_hosts,
                    total_containers=total_containers
                )
                
            except Exception as e:
                self.logger.error(f"Readiness check failed: {e}")
                return JSONResponse(
                    content={'status': 'not_ready', 'reason': 'container_listing_failed', 'error': str(e)},
                    status_code=503
                )
        
        @app.get("/containers", response_model=ContainersResponse)
        async def get_containers():
            """Get monitored containers"""
            return ContainersResponse(
                containers=list(self.monitored_containers.values()),
                count=len(self.monitored_containers)
            )

        @app.get("/containers/summary", response_model=Dict[str, List[Dict[str, Any]]])
        async def get_container_summary():
            """Get summary of monitored containers"""
            group_key = 'host_ip'
            grouped = {
                k: [{'name': item['name'], 'status': item['status'], 'snadboy_labels': item['snadboy_labels']}
                    for item in self.monitored_containers.values() if item[group_key] == k]
                for k in set(item[group_key] for item in self.monitored_containers.values())
            }
            return grouped
                
        @app.get("/containers/{container_id}", response_model=Dict[str, Any])
        async def get_container(container_id: str):
            """Get specific container info"""
            for key, container_data in self.monitored_containers.items():
                if container_id in key or container_data.get('short_id') == container_id:
                    return container_data
            raise HTTPException(status_code=404, detail="Container not found")
        
        @app.get("/labels", response_model=Dict[str, Dict[str, str]])
        async def get_labels():
            """Get all snadboy labels from monitored containers"""
            labels = {}
            for container_data in self.monitored_containers.values():
                container_labels = container_data.get('snadboy_labels', {})
                labels[container_data['name']] = container_labels
            return labels
        
        @app.get("/caddy", response_model=Dict[str, Any])
        async def get_caddy_config():
            """Get container info formatted for Caddy reverse proxy"""
            caddy_services = []
            for container_data in self.monitored_containers.values():
                if container_data['status'] != 'running':
                    continue
                    
                labels = container_data.get('snadboy_labels', {})
                host_ip = container_data.get('host_ip')
                
                if not host_ip:
                    self.logger.warning(f"No host IP available for container {container_data['name']}")
                    continue
                
                service_info = {
                    'container_name': container_data['name'],
                    'container_id': container_data['short_id'],
                    'host_ip': host_ip,
                    'docker_host_name': container_data.get('docker_host_name', 'unknown'),
                    'docker_networks': container_data.get('docker_networks', {}),
                    'primary_docker_ip': container_data.get('primary_docker_ip'),
                    'labels': labels,
                    'ports': container_data.get('exposed_ports', [])
                }
                
                # Extract common reverse proxy labels
                for key, value in labels.items():
                    key_lower = key.lower()
                    if 'domain' in key_lower or 'host' in key_lower:
                        service_info['domain'] = value
                    elif 'port' in key_lower and 'port' not in service_info:
                        service_info['port'] = value
                    elif 'path' in key_lower:
                        service_info['path'] = value
                    elif 'protocol' in key_lower:
                        service_info['protocol'] = value
                
                caddy_services.append(service_info)
            
            return {
                'services': caddy_services,
                'count': len(caddy_services),
                'timestamp': datetime.now().isoformat(),
                'note': 'host_ip is the real machine IP for Caddy routing, primary_docker_ip is internal Docker network IP'
            }
        
        @app.get("/ips", response_model=Dict[str, Any])
        async def get_container_ips():
            """Get all container IP addresses"""
            ips = {}
            for container_data in self.monitored_containers.values():
                container_name = container_data['name']
                ips[container_name] = {
                    'host_ip': container_data.get('host_ip'),
                    'docker_host_name': container_data.get('docker_host_name', 'unknown'),
                    'primary_docker_ip': container_data.get('primary_docker_ip'),
                    'all_docker_ips': container_data.get('docker_ips', []),
                    'docker_networks': container_data.get('docker_networks', {}),
                    'status': container_data['status']
                }
            return {
                'containers': ips,
                'note': 'host_ip = real machine IP for routing, docker_ips = internal container network IPs'
            }
        
        @app.get("/errors", response_model=Dict[str, Any])
        async def get_host_errors():
            """Get detailed information about host connection errors"""
            host_errors = self.host_manager.get_host_errors()
            
            # Add additional context
            error_details = {}
            for host_name, error_info in host_errors.items():
                failures = error_info.get('consecutive_failures', 0)
                backoff_delay = min(30 * (2 ** failures), 300)
                
                error_details[host_name] = {
                    **error_info,
                    'backoff_delay_seconds': backoff_delay,
                    'next_retry_after': datetime.fromtimestamp(
                        self.host_manager.error_timestamps.get(host_name, 0) + backoff_delay
                    ).isoformat() if host_name in self.host_manager.error_timestamps else None
                }
            
            return {
                'host_errors': error_details,
                'error_count': len(host_errors),
                'recovery_candidates': self.host_manager.get_hosts_needing_recovery(),
                'timestamp': datetime.now().isoformat()
            }
        
        @app.get("/services/schema", response_model=Dict[str, Any])
        async def get_services_schema():
            """Get supported service types and their schemas"""
            
            if self.container_processor:
                service_schemas = self.container_processor.get_supported_services()
            else:
                # Fallback schema if container processor not available
                service_schemas = {
                    'revp': {
                        'description': 'Reverse Proxy Service (Caddy)',
                        'required_properties': ['domain', 'port'],
                        'optional_properties': ['path', 'protocol', 'middleware', 'ssl', 'headers'],
                        'example': 'snadboy.revp.domain=example.com',
                        'status': 'implemented'
                    }
                }
            
            # Add examples for implemented service types
            for service_type, schema in service_schemas.items():
                if schema.get('status') == 'implemented':
                    schema['examples'] = {
                        'basic': {
                            f'snadboy.{service_type}.domain': f'{service_type}.example.com',
                            f'snadboy.{service_type}.port': '80'
                        }
                    }
                    
                    if service_type == 'revp':
                        schema['examples']['advanced'] = {
                            'snadboy.revp.domain': 'app.example.com',
                            'snadboy.revp.port': '80',
                            'snadboy.revp.path': '/app',
                            'snadboy.revp.scheme': 'https',
                            'snadboy.revp.websocket': 'true',
                            'snadboy.revp.ssl_force': 'true',
                            'snadboy.revp.middleware': 'auth,compress'
                        }
            
            # Document planned (unimplemented) service types
            planned_services = get_planned_services()
            
            return {
                'implemented_services': service_schemas,
                'planned_services': planned_services,
                'service_count': len(service_schemas),
                'usage_notes': [
                    'Currently only "revp" (Reverse Proxy) service type is implemented',
                    'Service names are case-insensitive (REVP = revp = Revp)',
                    'Property names are case-insensitive (DOMAIN = domain = Domain)',
                    'All services require "domain" and "port" as minimum properties',
                    'Invalid service types will be rejected with helpful error messages'
                ],
                'label_format': 'snadboy.{service_type}.{property}={value}',
                'validation_rules': {
                    'port': 'Must be a number between 1 and 65535',
                    'domain': 'Must be a valid hostname or IP address',
                    'path': 'Must start with / if specified',
                    'protocol': 'Must be http, https, tcp, or udp',
                    'ssl': 'Must be true or false'
                },
                'roadmap': 'Additional service types may be implemented based on user requirements. See README.md for detailed planned features.',
                'timestamp': datetime.now().isoformat()
            }
        
        @app.get("/debug", response_model=Dict[str, Any])
        async def debug_info():
            """Debug endpoint to troubleshoot container detection"""
            debug_data = {
                'config': {
                    'label_prefix': self.config.get('label_prefix', 'snadboy.'),
                    'docker_hosts': list(self.host_manager.hosts.keys()),
                    'connected_hosts': [name for name, host in self.host_manager.hosts.items() if host.status == 'connected']
                },
                'host_ips': self.host_manager.host_ips,
                'monitored_containers_count': len(self.monitored_containers),
                'monitored_containers_keys': list(self.monitored_containers.keys()),
                'persistent_errors': self.host_manager.get_host_errors(),
                'supported_services': ['revp'] if self.container_processor else ['revp'],  # Only implemented
                'planned_services': ['api', 'web', 'db', 'metrics'],  # Documented but not implemented
                'all_containers_per_host': {}
            }
            
            # Get all containers per host for debugging
            for host_name, host in self.host_manager.hosts.items():
                if host.status == 'connected':
                    try:
                        all_containers = host.get_containers()
                        containers_info = []
                        
                        for container_data in all_containers:
                            labels = container_data.get('labels', {})
                            has_snadboy_labels = any(
                                key.lower().startswith(self.config.get('label_prefix', 'snadboy.').lower()) 
                                for key in labels.keys()
                            )
                            
                            containers_info.append({
                                'name': container_data['name'],
                                'id': container_data['short_id'],
                                'status': container_data['status'],
                                'labels': labels,
                                'has_snadboy_labels': has_snadboy_labels,
                                'source': container_data.get('source', 'unknown')
                            })
                        
                        debug_data['all_containers_per_host'][host_name] = {
                            'total_containers': len(all_containers),
                            'containers': containers_info,
                            'host_type': host.get_type()
                        }
                    except Exception as e:
                        debug_data['all_containers_per_host'][host_name] = {
                            'error': str(e),
                            'host_type': host.get_type()
                        }
            
            return debug_data
        
        @app.get("/caddy/status", response_model=Dict[str, Any])
        async def get_caddy_status():
            """Get detailed Caddy integration status"""
            if not self.caddy_manager:
                return {
                    'enabled': False,
                    'message': 'Caddy integration is disabled'
                }
            
            return {
                'enabled': True,
                'available': self.caddy_manager.caddy_available,
                'admin_url': self.caddy_manager.caddy_admin_url,
                'state_file': str(self.caddy_manager.state_file),
                'managed_routes_count': len(self.caddy_manager.managed_routes),
                'managed_routes': self.caddy_manager.managed_routes,
                'last_health_check': datetime.fromtimestamp(self.caddy_manager.last_health_check).isoformat() if self.caddy_manager.last_health_check > 0 else None,
                'retry_config': {
                    'attempts': self.caddy_manager.retry_attempts,
                    'delay': self.caddy_manager.retry_delay
                }
            }
        
        return app
    
    def _get_dashboard_html(self) -> str:
        """Get the HTML content for the web dashboard"""
        return '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Docker Monitor Dashboard</title>
    <style>
        :root {
            --bg-primary: #ffffff;
            --bg-secondary: #f8f9fa;
            --bg-tertiary: #e9ecef;
            --text-primary: #212529;
            --text-secondary: #6c757d;
            --text-muted: #adb5bd;
            --border-color: #dee2e6;
            --success-color: #28a745;
            --warning-color: #ffc107;
            --danger-color: #dc3545;
            --info-color: #17a2b8;
            --accent-color: #007bff;
            --shadow: 0 0.125rem 0.25rem rgba(0, 0, 0, 0.075);
            --shadow-lg: 0 1rem 3rem rgba(0, 0, 0, 0.175);
        }

        [data-theme="dark"] {
            --bg-primary: #1a1a1a;
            --bg-secondary: #2d2d2d;
            --bg-tertiary: #404040;
            --text-primary: #ffffff;
            --text-secondary: #b0b0b0;
            --text-muted: #808080;
            --border-color: #404040;
            --success-color: #40c757;
            --warning-color: #ffcd39;
            --danger-color: #f86c6b;
            --info-color: #17a2b8;
            --accent-color: #375a7f;
            --shadow: 0 0.125rem 0.25rem rgba(0, 0, 0, 0.3);
            --shadow-lg: 0 1rem 3rem rgba(0, 0, 0, 0.4);
        }

        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }

        body {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
            background-color: var(--bg-primary);
            color: var(--text-primary);
            line-height: 1.6;
            transition: all 0.3s ease;
        }

        .header {
            background: var(--bg-secondary);
            border-bottom: 1px solid var(--border-color);
            padding: 1rem 2rem;
            display: flex;
            justify-content: space-between;
            align-items: center;
            box-shadow: var(--shadow);
            position: sticky;
            top: 0;
            z-index: 100;
        }

        .header h1 {
            font-size: 1.5rem;
            font-weight: 600;
            color: var(--text-primary);
        }

        .header-controls {
            display: flex;
            align-items: center;
            gap: 1rem;
        }

        .theme-toggle {
            background: var(--accent-color);
            color: white;
            border: none;
            padding: 0.5rem 1rem;
            border-radius: 0.375rem;
            cursor: pointer;
            font-size: 0.875rem;
            transition: all 0.2s ease;
        }

        .theme-toggle:hover {
            filter: brightness(110%);
        }

        .refresh-status {
            font-size: 0.75rem;
            color: var(--text-muted);
            display: flex;
            align-items: center;
            gap: 0.5rem;
        }

        .status-dot {
            width: 8px;
            height: 8px;
            border-radius: 50%;
            background: var(--success-color);
            animation: pulse 2s infinite;
        }

        @keyframes pulse {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.5; }
        }

        .container {
            max-width: 1400px;
            margin: 0 auto;
            padding: 2rem;
        }

        .tabs {
            display: flex;
            border-bottom: 1px solid var(--border-color);
            margin-bottom: 2rem;
            overflow-x: auto;
        }

        .tab {
            background: none;
            border: none;
            padding: 1rem 1.5rem;
            cursor: pointer;
            color: var(--text-secondary);
            font-size: 0.875rem;
            font-weight: 500;
            border-bottom: 2px solid transparent;
            transition: all 0.2s ease;
            white-space: nowrap;
        }

        .tab.active {
            color: var(--accent-color);
            border-bottom-color: var(--accent-color);
        }

        .tab:hover {
            color: var(--text-primary);
        }

        .tab-content {
            display: none;
        }

        .tab-content.active {
            display: block;
        }

        .stats-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 1.5rem;
            margin-bottom: 2rem;
        }

        .stat-card {
            background: var(--bg-secondary);
            border: 1px solid var(--border-color);
            border-radius: 0.5rem;
            padding: 1.5rem;
            box-shadow: var(--shadow);
        }

        .stat-card h3 {
            font-size: 0.875rem;
            font-weight: 600;
            color: var(--text-secondary);
            margin-bottom: 0.5rem;
            text-transform: uppercase;
            letter-spacing: 0.05em;
        }

        .stat-value {
            font-size: 2rem;
            font-weight: 700;
            color: var(--text-primary);
        }

        .stat-label {
            font-size: 0.75rem;
            color: var(--text-muted);
            margin-top: 0.25rem;
        }

        .data-table {
            background: var(--bg-secondary);
            border: 1px solid var(--border-color);
            border-radius: 0.5rem;
            overflow: hidden;
            box-shadow: var(--shadow);
        }

        .table-header {
            background: var(--bg-tertiary);
            padding: 1rem 1.5rem;
            border-bottom: 1px solid var(--border-color);
            font-weight: 600;
            color: var(--text-primary);
        }

        .table-content {
            max-height: 600px;
            overflow-y: auto;
        }

        .table-row {
            padding: 1rem 1.5rem;
            border-bottom: 1px solid var(--border-color);
            display: grid;
            grid-template-columns: 2fr 1fr 1fr 1fr;
            align-items: center;
            gap: 1rem;
        }

        .table-row:last-child {
            border-bottom: none;
        }

        .table-row:hover {
            background: var(--bg-tertiary);
        }

        .status-badge {
            display: inline-flex;
            align-items: center;
            padding: 0.25rem 0.75rem;
            border-radius: 9999px;
            font-size: 0.75rem;
            font-weight: 500;
            gap: 0.375rem;
        }

        .status-badge.healthy {
            background: rgba(40, 167, 69, 0.1);
            color: var(--success-color);
        }

        .status-badge.unhealthy {
            background: rgba(220, 53, 69, 0.1);
            color: var(--danger-color);
        }

        .status-badge.degraded {
            background: rgba(255, 193, 7, 0.1);
            color: var(--warning-color);
        }

        .status-badge.running {
            background: rgba(40, 167, 69, 0.1);
            color: var(--success-color);
        }

        .status-badge.stopped {
            background: rgba(220, 53, 69, 0.1);
            color: var(--danger-color);
        }

        .container-card {
            background: var(--bg-secondary);
            border: 1px solid var(--border-color);
            border-radius: 0.5rem;
            padding: 1.5rem;
            margin-bottom: 1rem;
            box-shadow: var(--shadow);
        }

        .container-header {
            display: flex;
            justify-content: space-between;
            align-items: flex-start;
            margin-bottom: 1rem;
        }

        .container-name {
            font-size: 1.125rem;
            font-weight: 600;
            color: var(--text-primary);
            margin-bottom: 0.25rem;
        }

        .container-id {
            font-size: 0.75rem;
            color: var(--text-muted);
            font-family: monospace;
        }

        .container-labels {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 0.75rem;
            margin-top: 1rem;
        }

        .label-item {
            background: var(--bg-tertiary);
            padding: 0.5rem 0.75rem;
            border-radius: 0.25rem;
            font-size: 0.75rem;
            font-family: monospace;
        }

        .label-key {
            color: var(--accent-color);
            font-weight: 600;
        }

        .label-value {
            color: var(--text-primary);
        }

        .error-card {
            background: rgba(220, 53, 69, 0.05);
            border: 1px solid rgba(220, 53, 69, 0.2);
            border-radius: 0.5rem;
            padding: 1.5rem;
            margin-bottom: 1rem;
        }

        .error-header {
            display: flex;
            justify-content: between;
            align-items: flex-start;
            margin-bottom: 1rem;
        }

        .error-host {
            font-size: 1rem;
            font-weight: 600;
            color: var(--danger-color);
        }

        .error-timestamp {
            font-size: 0.75rem;
            color: var(--text-muted);
        }

        .error-message {
            background: var(--bg-tertiary);
            padding: 1rem;
            border-radius: 0.25rem;
            font-family: monospace;
            font-size: 0.875rem;
            color: var(--text-primary);
            white-space: pre-wrap;
            margin-top: 0.75rem;
        }

        .loading {
            display: flex;
            justify-content: center;
            align-items: center;
            padding: 3rem;
            color: var(--text-muted);
        }

        .loading::after {
            content: "";
            width: 20px;
            height: 20px;
            margin-left: 10px;
            border: 2px solid var(--border-color);
            border-top: 2px solid var(--accent-color);
            border-radius: 50%;
            animation: spin 1s linear infinite;
        }

        @keyframes spin {
            0% { transform: rotate(0deg); }
            100% { transform: rotate(360deg); }
        }

        .empty-state {
            text-align: center;
            padding: 3rem;
            color: var(--text-muted);
        }

        .empty-state h3 {
            margin-bottom: 0.5rem;
            color: var(--text-secondary);
        }

        @media (max-width: 768px) {
            .header {
                padding: 1rem;
                flex-direction: column;
                gap: 1rem;
            }

            .container {
                padding: 1rem;
            }

            .stats-grid {
                grid-template-columns: 1fr;
            }

            .table-row {
                grid-template-columns: 1fr;
                gap: 0.5rem;
            }

            .container-header {
                flex-direction: column;
                gap: 0.5rem;
            }
        }
    </style>
</head>
<body>
    <div class="header">
        <h1>🐳 Docker Monitor Dashboard</h1>
        <div class="header-controls">
            <div class="refresh-status">
                <div class="status-dot"></div>
                <span id="lastUpdate">Loading...</span>
            </div>
            <button class="theme-toggle" onclick="toggleTheme()">🌙 Dark</button>
        </div>
    </div>

    <div class="container">
        <div class="tabs">
            <button class="tab active" onclick="showTab('overview')">Overview</button>
            <button class="tab" onclick="showTab('containers')">Containers</button>
            <button class="tab" onclick="showTab('health')">Health</button>
            <button class="tab" onclick="showTab('errors')">Errors</button>
            <button class="tab" onclick="showTab('services')">Services</button>
        </div>

        <div id="overview" class="tab-content active">
            <div class="stats-grid">
                <div class="stat-card">
                    <h3>System Status</h3>
                    <div class="stat-value" id="systemStatus">Loading...</div>
                    <div class="stat-label">Overall health</div>
                </div>
                <div class="stat-card">
                    <h3>Docker Hosts</h3>
                    <div class="stat-value" id="hostCount">-</div>
                    <div class="stat-label"><span id="connectedHosts">-</span> connected, <span id="failedHosts">-</span> failed</div>
                </div>
                <div class="stat-card">
                    <h3>Containers</h3>
                    <div class="stat-value" id="containerCount">-</div>
                    <div class="stat-label">Monitored with snadboy labels</div>
                </div>
                <div class="stat-card">
                    <h3>Caddy Routes</h3>
                    <div class="stat-value" id="routeCount">-</div>
                    <div class="stat-label">Active reverse proxy routes</div>
                </div>
            </div>

            <div class="data-table">
                <div class="table-header">Docker Hosts Status</div>
                <div class="table-content" id="hostsTable">
                    <div class="loading">Loading host information...</div>
                </div>
            </div>
        </div>

        <div id="containers" class="tab-content">
            <div id="containersContent">
                <div class="loading">Loading container information...</div>
            </div>
        </div>

        <div id="health" class="tab-content">
            <div id="healthContent">
                <div class="loading">Loading health information...</div>
            </div>
        </div>

        <div id="errors" class="tab-content">
            <div id="errorsContent">
                <div class="loading">Loading error information...</div>
            </div>
        </div>

        <div id="services" class="tab-content">
            <div id="servicesContent">
                <div class="loading">Loading service information...</div>
            </div>
        </div>
    </div>

    <script>
        let currentTheme = localStorage.getItem('theme') || 'light';
        let refreshInterval;
        
        // Initialize theme
        document.documentElement.setAttribute('data-theme', currentTheme);
        updateThemeButton();

        // Start auto-refresh
        refreshData();
        refreshInterval = setInterval(refreshData, 15000);

        function toggleTheme() {
            currentTheme = currentTheme === 'light' ? 'dark' : 'light';
            document.documentElement.setAttribute('data-theme', currentTheme);
            localStorage.setItem('theme', currentTheme);
            updateThemeButton();
        }

        function updateThemeButton() {
            const button = document.querySelector('.theme-toggle');
            button.textContent = currentTheme === 'light' ? '🌙 Dark' : '☀️ Light';
        }

        function showTab(tabName) {
            // Hide all tabs
            document.querySelectorAll('.tab-content').forEach(tab => {
                tab.classList.remove('active');
            });
            document.querySelectorAll('.tab').forEach(tab => {
                tab.classList.remove('active');
            });

            // Show selected tab
            document.getElementById(tabName).classList.add('active');
            event.target.classList.add('active');
        }

        async function refreshData() {
            try {
                await Promise.all([
                    updateOverview(),
                    updateContainers(),
                    updateHealth(),
                    updateErrors(),
                    updateServices()
                ]);
                
                document.getElementById('lastUpdate').textContent = 
                    `Updated ${new Date().toLocaleTimeString()}`;
            } catch (error) {
                console.error('Error refreshing data:', error);
                document.getElementById('lastUpdate').textContent = 
                    `Error at ${new Date().toLocaleTimeString()}`;
            }
        }

        async function updateOverview() {
            const [healthData, containersData] = await Promise.all([
                fetch('/health').then(r => r.json()),
                fetch('/containers').then(r => r.json())
            ]);

            // Update stats
            document.getElementById('systemStatus').textContent = healthData.status;
            document.getElementById('systemStatus').className = `stat-value status-${healthData.status}`;
            
            document.getElementById('hostCount').textContent = healthData.docker_hosts.total;
            document.getElementById('connectedHosts').textContent = healthData.docker_hosts.connected;
            document.getElementById('failedHosts').textContent = healthData.docker_hosts.failed;
            document.getElementById('containerCount').textContent = containersData.count;
            document.getElementById('routeCount').textContent = healthData.caddy?.managed_routes || 0;

            // Update hosts table
            const hostsTable = document.getElementById('hostsTable');
            if (healthData.docker_hosts.status_details) {
                hostsTable.innerHTML = Object.entries(healthData.docker_hosts.status_details)
                    .map(([host, status]) => {
                        const isHealthy = status === 'healthy';
                        const statusClass = isHealthy ? 'healthy' : 'unhealthy';
                        return `
                            <div class="table-row">
                                <div>
                                    <strong>${host}</strong>
                                    <div style="font-size: 0.75rem; color: var(--text-muted);">Docker Host</div>
                                </div>
                                <div><span class="status-badge ${statusClass}">${status}</span></div>
                                <div>${isHealthy ? 'Connected' : 'Failed'}</div>
                                <div>${new Date().toLocaleTimeString()}</div>
                            </div>
                        `;
                    }).join('');
            } else {
                hostsTable.innerHTML = '<div class="empty-state"><h3>No host data available</h3></div>';
            }
        }

        async function updateContainers() {
            try {
                const response = await fetch('/containers');
                const data = await response.json();
                
                const content = document.getElementById('containersContent');
                
                if (data.containers && data.containers.length > 0) {
                    content.innerHTML = data.containers.map(container => `
                        <div class="container-card">
                            <div class="container-header">
                                <div>
                                    <div class="container-name">${container.name}</div>
                                    <div class="container-id">${container.short_id}</div>
                                </div>
                                <span class="status-badge ${container.status}">${container.status}</span>
                            </div>
                            <div style="font-size: 0.875rem; color: var(--text-secondary); margin-bottom: 1rem;">
                                <strong>Host:</strong> ${container.docker_host_name || 'unknown'} 
                                (${container.host_ip || 'no IP'})
                            </div>
                            ${container.snadboy_labels ? `
                                <div class="container-labels">
                                    ${Object.entries(container.snadboy_labels).map(([key, value]) => `
                                        <div class="label-item">
                                            <span class="label-key">${key}:</span>
                                            <span class="label-value">${value}</span>
                                        </div>
                                    `).join('')}
                                </div>
                            ` : '<div style="color: var(--text-muted);">No snadboy labels</div>'}
                        </div>
                    `).join('');
                } else {
                    content.innerHTML = '<div class="empty-state"><h3>No containers found</h3><p>No containers with snadboy labels are currently being monitored.</p></div>';
                }
            } catch (error) {
                document.getElementById('containersContent').innerHTML = '<div class="error-card">Error loading containers</div>';
            }
        }

        async function updateHealth() {
            try {
                const response = await fetch('/health');
                const data = await response.json();
                
                const content = document.getElementById('healthContent');
                content.innerHTML = `
                    <div class="data-table">
                        <div class="table-header">System Health Details</div>
                        <div class="table-content">
                            <div class="table-row">
                                <div><strong>Overall Status</strong></div>
                                <div><span class="status-badge ${data.status}">${data.status}</span></div>
                                <div>System Health</div>
                                <div>${new Date(data.timestamp).toLocaleString()}</div>
                            </div>
                            <div class="table-row">
                                <div><strong>Uptime</strong></div>
                                <div>${Math.floor(data.uptime_seconds / 3600)}h ${Math.floor((data.uptime_seconds % 3600) / 60)}m</div>
                                <div>Service Runtime</div>
                                <div>Since startup</div>
                            </div>
                            <div class="table-row">
                                <div><strong>Docker Hosts</strong></div>
                                <div>${data.docker_hosts.connected}/${data.docker_hosts.total}</div>
                                <div>Connected/Total</div>
                                <div>${data.docker_hosts.failed} failed</div>
                            </div>
                            <div class="table-row">
                                <div><strong>Monitored Containers</strong></div>
                                <div>${data.monitored_containers}</div>
                                <div>With snadboy labels</div>
                                <div>Active</div>
                            </div>
                            ${data.caddy ? `
                                <div class="table-row">
                                    <div><strong>Caddy Integration</strong></div>
                                    <div><span class="status-badge ${data.caddy.available ? 'healthy' : 'unhealthy'}">${data.caddy.available ? 'Available' : 'Unavailable'}</span></div>
                                    <div>Reverse Proxy</div>
                                    <div>${data.caddy.managed_routes} routes</div>
                                </div>
                            ` : ''}
                        </div>
                    </div>
                `;
            } catch (error) {
                document.getElementById('healthContent').innerHTML = '<div class="error-card">Error loading health data</div>';
            }
        }

        async function updateErrors() {
            try {
                const response = await fetch('/errors');
                const data = await response.json();
                
                const content = document.getElementById('errorsContent');
                
                if (data.host_errors && Object.keys(data.host_errors).length > 0) {
                    content.innerHTML = Object.entries(data.host_errors).map(([host, error]) => `
                        <div class="error-card">
                            <div class="error-header">
                                <div class="error-host">${host}</div>
                                <div class="error-timestamp">${new Date(error.timestamp).toLocaleString()}</div>
                            </div>
                            <div style="margin-bottom: 0.5rem;">
                                <strong>Error Type:</strong> ${error.error_type}<br>
                                <strong>Consecutive Failures:</strong> ${error.consecutive_failures}<br>
                                <strong>Backoff Delay:</strong> ${error.backoff_delay_seconds}s
                            </div>
                            <div class="error-message">${error.error}</div>
                        </div>
                    `).join('');
                } else {
                    content.innerHTML = '<div class="empty-state"><h3>No errors</h3><p>All Docker hosts are healthy.</p></div>';
                }
            } catch (error) {
                document.getElementById('errorsContent').innerHTML = '<div class="error-card">Error loading error data</div>';
            }
        }

        async function updateServices() {
            try {
                const response = await fetch('/services/schema');
                const data = await response.json();
                
                const content = document.getElementById('servicesContent');
                content.innerHTML = `
                    <div class="data-table">
                        <div class="table-header">Supported Service Types</div>
                        <div class="table-content">
                            ${Object.entries(data.implemented_services || {}).map(([type, schema]) => `
                                <div class="container-card">
                                    <div class="container-header">
                                        <div>
                                            <div class="container-name">${type.toUpperCase()}</div>
                                            <div style="color: var(--text-secondary);">${schema.description}</div>
                                        </div>
                                        <span class="status-badge healthy">Implemented</span>
                                    </div>
                                    <div style="margin-bottom: 1rem;">
                                        <strong>Required:</strong> ${schema.required_properties.join(', ')}<br>
                                        <strong>Optional:</strong> ${schema.optional_properties.join(', ')}
                                    </div>
                                    ${schema.examples ? `
                                        <div class="container-labels">
                                            ${Object.entries(schema.examples.basic || {}).map(([key, value]) => `
                                                <div class="label-item">
                                                    <span class="label-key">${key}:</span>
                                                    <span class="label-value">${value}</span>
                                                </div>
                                            `).join('')}
                                        </div>
                                    ` : ''}
                                </div>
                            `).join('')}
                        </div>
                    </div>
                    
                    ${data.planned_services ? `
                        <div class="data-table" style="margin-top: 2rem;">
                            <div class="table-header">Planned Service Types</div>
                            <div class="table-content">
                                ${Object.entries(data.planned_services).map(([type, schema]) => `
                                    <div class="container-card">
                                        <div class="container-header">
                                            <div>
                                                <div class="container-name">${type.toUpperCase()}</div>
                                                <div style="color: var(--text-secondary);">${schema.description}</div>
                                            </div>
                                            <span class="status-badge degraded">Planned</span>
                                        </div>
                                        <div style="margin-bottom: 1rem; color: var(--text-secondary);">
                                            ${schema.purpose}
                                        </div>
                                        ${schema.sample_labels ? `
                                            <div class="container-labels">
                                                ${Object.entries(schema.sample_labels).map(([key, value]) => `
                                                    <div class="label-item">
                                                        <span class="label-key">${key}:</span>
                                                        <span class="label-value">${value}</span>
                                                    </div>
                                                `).join('')}
                                            </div>
                                        ` : ''}
                                    </div>
                                `).join('')}
                            </div>
                        </div>
                    ` : ''}
                `;
            } catch (error) {
                document.getElementById('servicesContent').innerHTML = '<div class="error-card">Error loading service data</div>';
            }
        }
    </script>
</body>
</html>
        '''
    
    def start(self):
        """Start the FastAPI server using uvicorn"""
        import uvicorn
        
        api_port = self.config.get('api_port', 8080)
        self.logger.info(f"Starting FastAPI server on port {api_port}")
        
        uvicorn.run(
            self.app,
            host='0.0.0.0',
            port=api_port,
            log_level='warning',  # Reduce uvicorn logging
            access_log=False  # Disable access logs for cleaner output
        )