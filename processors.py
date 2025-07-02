"""
Container Processing and Caddy Management

This module contains the ContainerProcessor which extracts and validates snadboy
labels from containers, and the CaddyManager which handles Caddy reverse proxy
configuration via Admin API.
"""

import requests
import json
import time
import subprocess
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional
import logging

from .schemas import SERVICE_SCHEMAS


class ContainerProcessor:
    """Processes containers and extracts snadboy label information"""
    
    def __init__(self, config: Dict, logger: logging.Logger):
        self.config = config
        self.logger = logger
        self.label_prefix = config.get('label_prefix', 'snadboy.').lower()
        
        # Use shared service schemas instead of defining them again
        self.service_schemas = SERVICE_SCHEMAS
    
    def get_supported_services(self) -> Dict:
        """Get list of supported service types and their schemas"""
        return {
            service_type: {
                'description': schema['description'],
                'required_properties': schema['required'],
                'optional_properties': list(schema['optional'].keys()),
                'example': f"snadboy.{service_type}.domain=example.com",
                'status': 'implemented'
            }
            for service_type, schema in self.service_schemas.items()
        }
    
    def has_snadboy_labels(self, container_data: Dict) -> bool:
        """Check if container has snadboy labels"""
        labels = container_data.get('labels', {})
        return any(key.lower().startswith(self.label_prefix) for key in labels.keys())
    
    def extract_snadboy_labels(self, container_data: Dict) -> Dict[str, str]:
        """Extract snadboy labels from container"""
        snadboy_labels = {}
        labels = container_data.get('labels', {})
        
        for key, value in labels.items():
            if key.lower().startswith(self.label_prefix):
                snadboy_labels[key] = value
        
        return snadboy_labels
    
    def process_container(self, container_data: Dict, host_name: str, host_ip: Optional[str]) -> Optional[Dict]:
        """Process container and create monitoring record"""
        if not self.has_snadboy_labels(container_data):
            return None
        
        try:
            snadboy_labels = self.extract_snadboy_labels(container_data)
            attrs = container_data.get('attrs', {})
            
            # Build container info
            container_info = {
                'id': container_data['id'],
                'short_id': container_data['short_id'],
                'name': container_data['name'],
                'status': container_data['status'],
                'image': container_data['image'],
                'created': attrs.get('Created'),
                'started_at': attrs.get('State', {}).get('StartedAt'),
                'labels': container_data.get('labels', {}),
                'snadboy_labels': snadboy_labels,
                'last_updated': datetime.now().isoformat(),
                'docker_host_name': host_name,
                'host_ip': host_ip,  # Real host machine IP for Caddy
                'source': container_data.get('source', 'unknown')
            }
            
            # Extract network information
            self._extract_network_info(container_info, attrs)
            
            # Extract port mappings
            self._extract_port_info(container_info, attrs)
            
            # Extract environment variables
            self._extract_environment_info(container_info, attrs)
            
            self.logger.debug(f"Successfully processed container {container_info['name']} on host '{host_name}'")
            return container_info
            
        except Exception as e:
            self.logger.error(f"Error processing container {container_data.get('name', 'unknown')}: {e}")
            return None
    
    def _extract_network_info(self, container_info: Dict, attrs: Dict):
        """Extract network and IP information"""
        networks_detail = attrs.get('NetworkSettings', {}).get('Networks', {})
        container_info['docker_networks'] = {}
        container_info['docker_ips'] = []
        
        for network_name, network_data in networks_detail.items():
            docker_ip = network_data.get('IPAddress')
            if docker_ip:
                container_info['docker_networks'][network_name] = {
                    'docker_ip': docker_ip,
                    'gateway': network_data.get('Gateway'),
                    'mac_address': network_data.get('MacAddress'),
                    'network_id': network_data.get('NetworkID')
                }
                container_info['docker_ips'].append(docker_ip)
        
        # Primary Docker IP (first non-empty IP found)
        container_info['primary_docker_ip'] = container_info['docker_ips'][0] if container_info['docker_ips'] else None
        
        # Legacy compatibility
        container_info['networks'] = container_info['docker_networks']
        container_info['ip_addresses'] = container_info['docker_ips']
        container_info['primary_ip'] = container_info['primary_docker_ip']
    
    def _extract_port_info(self, container_info: Dict, attrs: Dict):
        """Extract port mapping information"""
        ports_data = attrs.get('NetworkSettings', {}).get('Ports', {})
        container_info['ports'] = {}
        container_info['exposed_ports'] = []
        
        for container_port, host_bindings in ports_data.items():
            if host_bindings:
                for binding in host_bindings:
                    host_port = binding.get('HostPort')
                    if host_port:
                        container_info['ports'][container_port] = {
                            'host_ip': binding.get('HostIp', '0.0.0.0'),
                            'host_port': int(host_port)
                        }
                        container_info['exposed_ports'].append({
                            'container_port': container_port,
                            'host_port': int(host_port),
                            'protocol': container_port.split('/')[-1] if '/' in container_port else 'tcp'
                        })
    
    def _extract_environment_info(self, container_info: Dict, attrs: Dict):
        """Extract environment variables"""
        env_vars = attrs.get('Config', {}).get('Env', [])
        container_info['environment'] = {}
        for env_var in env_vars:
            if '=' in env_var:
                key, value = env_var.split('=', 1)
                container_info['environment'][key] = value


class CaddyManager:
    """Manages Caddy configuration via Admin API with persistent state"""
    
    def __init__(self, config: Dict, logger: logging.Logger):
        self.config = config
        self.logger = logger
        self.caddy_admin_url = config.get('caddy_admin_url', 'http://localhost:2019')
        self.state_file = Path(config.get('caddy_state_file', '/app/data/caddy-state.json'))
        self.retry_attempts = config.get('caddy_retry_attempts', 3)
        self.retry_delay = config.get('caddy_retry_delay', 5)
        
        # Use shared service schemas
        self.service_schemas = SERVICE_SCHEMAS
        
        # Validate Caddy URL configuration
        self._validate_caddy_url()
        
        # Ensure state directory exists
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        self.logger.info(f"Caddy state file: {self.state_file}")
        
        # Load existing state
        self.managed_routes = self.load_state()
        self.caddy_available = False
        self.last_health_check = 0
        self.health_check_interval = 30  # seconds
    
    def _validate_caddy_url(self):
        """Validate Caddy Admin URL and warn about common Docker networking issues"""
        url = self.caddy_admin_url.lower()
        
        # Check if running in Docker container
        in_docker = os.path.exists('/.dockerenv')
        
        if in_docker and ('localhost' in url or '127.0.0.1' in url):
            self.logger.error("🚨 DOCKER NETWORKING ISSUE DETECTED 🚨")
            self.logger.error("=" * 60)
            self.logger.error(f"Caddy Admin URL is set to: {self.caddy_admin_url}")
            self.logger.error("This will NOT work inside a Docker container!")
            self.logger.error("")
            self.logger.error("📋 SOLUTIONS:")
            self.logger.error("1. Use host IP address:")
            self.logger.error("   export CADDY_ADMIN_URL=http://192.168.1.100:2019")
            self.logger.error("")
            self.logger.error("2. Use Docker Compose service name:")
            self.logger.error("   export CADDY_ADMIN_URL=http://caddy:2019")
            self.logger.error("")
            self.logger.error("3. Use Docker Desktop host gateway:")
            self.logger.error("   export CADDY_ADMIN_URL=http://host.docker.internal:2019")
            self.logger.error("")
            self.logger.error("4. Use Docker bridge gateway (auto-detect):")
            try:
                result = subprocess.run(['ip', 'route', 'show', 'default'], 
                                      capture_output=True, text=True, timeout=5)
                if result.returncode == 0:
                    for line in result.stdout.split('\n'):
                        if 'default via' in line:
                            gateway_ip = line.split()[2]
                            self.logger.error(f"   export CADDY_ADMIN_URL=http://{gateway_ip}:2019")
                            break
            except Exception:
                self.logger.error("   export CADDY_ADMIN_URL=http://172.17.0.1:2019")
            self.logger.error("")
            self.logger.error("5. Use host networking:")
            self.logger.error("   docker run --network host ...")
            self.logger.error("=" * 60)
        
        elif not in_docker and 'localhost' not in url and '127.0.0.1' not in url:
            self.logger.info(f"Using remote Caddy Admin API: {self.caddy_admin_url}")
            self.logger.info("Ensure Caddy Admin API is accessible from this machine")
        
        else:
            self.logger.info(f"Caddy Admin API URL: {self.caddy_admin_url}")
    
    def load_state(self) -> Dict:
        """Load managed routes from state file"""
        try:
            if self.state_file.exists():
                with open(self.state_file, 'r') as f:
                    data = json.load(f)
                    routes = data.get('managed_routes', {})
                    self.logger.info(f"Loaded {len(routes)} managed routes from state file")
                    return routes
            else:
                self.logger.info("No existing state file found, starting fresh")
                return {}
        except Exception as e:
            self.logger.error(f"Error loading state file: {e}")
            # Backup corrupted file
            if self.state_file.exists():
                backup_file = self.state_file.with_suffix('.json.corrupted')
                self.state_file.rename(backup_file)
                self.logger.warning(f"Moved corrupted state file to {backup_file}")
            return {}
    
    def save_state(self):
        """Save managed routes to state file"""
        try:
            state_data = {
                'managed_routes': self.managed_routes,
                'last_updated': datetime.now().isoformat(),
                'caddy_admin_url': self.caddy_admin_url
            }
            
            # Atomic write using temporary file
            temp_file = self.state_file.with_suffix('.tmp')
            with open(temp_file, 'w') as f:
                json.dump(state_data, f, indent=2)
            
            # Atomic rename
            temp_file.rename(self.state_file)
            self.logger.debug(f"Saved {len(self.managed_routes)} managed routes to state file")
            
        except Exception as e:
            self.logger.error(f"Error saving state file: {e}")
    
    def test_caddy_health(self) -> bool:
        """Check if Caddy Admin API is available"""
        now = time.time()
        if now - self.last_health_check < self.health_check_interval and self.caddy_available:
            return True  # Skip frequent health checks if recently successful
        
        try:
            response = requests.get(f"{self.caddy_admin_url}/config/", timeout=5)
            self.caddy_available = response.status_code == 200
            if self.caddy_available:
                self.logger.debug("Caddy Admin API is healthy")
            else:
                self.logger.warning(f"Caddy Admin API returned status {response.status_code}")
        except requests.exceptions.ConnectionError as e:
            self.caddy_available = False
            # Provide specific error messages for common issues
            url = self.caddy_admin_url.lower()
            in_docker = os.path.exists('/.dockerenv')
            
            if in_docker and ('localhost' in url or '127.0.0.1' in url):
                self.logger.error("❌ Connection failed: localhost doesn't work in Docker containers!")
                self.logger.error("   Set CADDY_ADMIN_URL to the actual Caddy server IP/hostname")
                self.logger.error("   Example: export CADDY_ADMIN_URL=http://192.168.1.100:2019")
            else:
                self.logger.warning(f"Caddy Admin API connection failed: {e}")
                self.logger.warning(f"Ensure Caddy is running and accessible at: {self.caddy_admin_url}")
        except Exception as e:
            self.caddy_available = False
            self.logger.warning(f"Caddy Admin API health check failed: {e}")
        
        self.last_health_check = now
        return self.caddy_available
    
    def generate_routes_from_containers(self, monitored_containers: Dict) -> Dict:
        """Generate Caddy routes from monitored containers with snadboy labels"""
        routes = {}
        
        for container_key, container_info in monitored_containers.items():
            if container_info.get('status') != 'running':
                continue
                
            snadboy_labels = container_info.get('snadboy_labels', {})
            host_ip = container_info.get('host_ip')
            container_name = container_info.get('name', 'unknown')
            
            if not host_ip:
                self.logger.warning(f"Container '{container_name}': No host IP available, skipping Caddy routes")
                continue
            
            # Extract services from labels (Option C: multiple services per container)
            services = self._extract_services_from_labels(snadboy_labels, container_name)
            
            for service_name, service_config in services.items():
                route_id = f"docker-monitor-{container_key.replace(':', '-')}-{service_name}"
                
                # Build upstream URL
                service_port = service_config.get('port')
                if not service_port:
                    self.logger.warning(f"Container '{container_name}': No port specified for service '{service_name}'")
                    continue
                
                upstream = f"{host_ip}:{service_port}"
                
                # Generate Caddy route configuration
                caddy_route = self._generate_caddy_route_config(service_config, upstream)
                
                routes[route_id] = {
                    'container_key': container_key,
                    'container_name': container_name,
                    'service_name': service_name,
                    'domain': service_config.get('domain'),
                    'upstream': upstream,
                    'caddy_config': caddy_route,
                    'created': datetime.now().isoformat()
                }
                
                self.logger.debug(f"Container '{container_name}': Generated route {route_id}: {service_config.get('domain')} -> {upstream}")
        
        return routes
    
    def _extract_services_from_labels(self, labels: Dict, container_name: str = 'unknown') -> Dict:
        """Extract and validate service configurations from snadboy labels using service registry"""
        raw_services = {}
        
        # First pass: Group labels by service name
        for label_key, label_value in labels.items():
            if not label_key.lower().startswith('snadboy.'):
                continue
                
            # Remove 'snadboy.' prefix and split (handle case insensitive)
            remaining_key = label_key[8:]  # Remove 'snadboy.' prefix
            parts = remaining_key.split('.')
            if len(parts) < 2:
                self.logger.debug(f"Container '{container_name}': Skipping invalid snadboy label format: {label_key}")
                continue
                
            service_name = parts[0].lower()  # Normalize service name to lowercase
            property_name = '.'.join(parts[1:]).lower()  # Normalize property name to lowercase
            
            if service_name not in raw_services:
                raw_services[service_name] = {}
            
            raw_services[service_name][property_name] = label_value
        
        # Second pass: Validate against service registry
        valid_services = {}
        for service_name, config in raw_services.items():
            validation_result = self._validate_service_config(service_name, config, container_name)
            
            if validation_result['valid']:
                valid_services[service_name] = validation_result['config']
                self.logger.info(f"Container '{container_name}': Valid service '{service_name}' ({self.service_schemas[service_name]['description']}) "
                               f"configured with domain={validation_result['config']['domain']} port={validation_result['config']['port']}")
            else:
                self.logger.warning(f"Container '{container_name}': Service '{service_name}' validation failed: {validation_result['error']}")
        
        return valid_services
    
    def _validate_service_config(self, service_name: str, config: Dict, container_name: str) -> Dict:
        """Validate service configuration against service registry"""
        
        # Check if service type is supported
        if service_name not in self.service_schemas:
            supported_services = list(self.service_schemas.keys())
            return {
                'valid': False,
                'error': f"Unsupported service type '{service_name}'. Supported types: {supported_services}. "
                        f"Available properties: {list(config.keys())}"
            }
        
        schema = self.service_schemas[service_name]
        validated_config = {}
        
        # Check required properties
        missing_required = []
        for required_prop in schema['required']:
            if required_prop not in config:
                missing_required.append(required_prop)
            else:
                validated_config[required_prop] = config[required_prop]
        
        if missing_required:
            return {
                'valid': False,
                'error': f"Missing required properties: {missing_required}. "
                        f"Available properties: {list(config.keys())}. "
                        f"Required for '{service_name}': {schema['required']}"
            }
        
        # Add optional properties with defaults and smart ssl_force logic
        for optional_prop, default_value in schema['optional'].items():
            if optional_prop in config:
                validated_config[optional_prop] = config[optional_prop]
            else:
                # Smart default for ssl_force based on scheme
                if optional_prop == 'ssl_force' and default_value is None:
                    scheme = validated_config.get('scheme', 'http')
                    validated_config[optional_prop] = 'true' if scheme == 'https' else 'false'
                else:
                    validated_config[optional_prop] = default_value
                self.logger.debug(f"Container '{container_name}': Service '{service_name}' using default {optional_prop}={validated_config[optional_prop]}")
        
        # Validate property values
        validation_errors = []
        for prop_name, prop_value in validated_config.items():
            if prop_name in schema.get('validation', {}):
                validator = schema['validation'][prop_name]
                if not validator(prop_value):
                    validation_errors.append(f"{prop_name}='{prop_value}' (invalid format)")
        
        if validation_errors:
            return {
                'valid': False,
                'error': f"Property validation failed: {validation_errors}"
            }
        
        # Check for unknown properties (warn but don't fail)
        unknown_props = set(config.keys()) - set(schema['required']) - set(schema['optional'].keys())
        if unknown_props:
            self.logger.warning(f"Container '{container_name}': Service '{service_name}' has unknown properties: {list(unknown_props)}. "
                               f"Supported properties: {schema['required'] + list(schema['optional'].keys())}")
        
        return {
            'valid': True,
            'config': validated_config,
            'error': None
        }
    
    def _generate_caddy_route_config(self, service_config: Dict, upstream: str) -> Dict:
        """Generate enhanced Caddy JSON route configuration for REVP service"""
        domain = service_config.get('domain')
        path = service_config.get('path', '/')
        scheme = service_config.get('scheme', 'http')
        websocket = service_config.get('websocket', 'false').lower() == 'true'
        ssl_force = service_config.get('ssl_force', 'false').lower() == 'true'
        middleware = service_config.get('middleware', '').split(',') if service_config.get('middleware') else []
        
        # Build Caddy route
        route = {
            "match": [{"host": [domain]}],
            "handle": []
        }
        
        # Add path matching if specified
        if path and path != '/':
            route["match"][0]["path"] = [f"{path}*"]
        
        # Add SSL force redirect if enabled
        if ssl_force and scheme == 'http':
            route["handle"].append({
                "handler": "static_response",
                "headers": {
                    "Location": [f"https://{domain}{{http.request.uri}}"]
                },
                "status_code": 301
            })
            return route  # Return early for redirect-only route
        
        # Add middleware handlers
        for mw in middleware:
            mw = mw.strip()
            if mw == 'auth':
                route["handle"].append({"handler": "authentication"})
            elif mw == 'compress':
                route["handle"].append({"handler": "encode", "encodings": {"gzip": {}}})
            elif mw == 'rate_limit':
                route["handle"].append({"handler": "rate_limit"})
            # Add more middleware as needed
        
        # Build reverse proxy handler
        proxy_handler = {
            "handler": "reverse_proxy",
            "upstreams": [{"dial": upstream}],
            "headers": {
                "request": {
                    "set": {
                        "Host": ["{http.request.host}"],
                        "X-Real-IP": ["{http.request.remote.host}"],
                        "X-Forwarded-For": ["{http.request.remote}"],
                        "X-Forwarded-Proto": [scheme]
                    }
                }
            }
        }
        
        # Add WebSocket support if enabled
        if websocket:
            proxy_handler["headers"]["request"]["set"]["Connection"] = ["Upgrade"]
            proxy_handler["headers"]["request"]["set"]["Upgrade"] = ["websocket"]
            proxy_handler["headers"]["request"]["set"]["Sec-WebSocket-Protocol"] = ["{http.request.header.Sec-WebSocket-Protocol}"]
            proxy_handler["headers"]["request"]["set"]["Sec-WebSocket-Version"] = ["{http.request.header.Sec-WebSocket-Version}"]
            
            # Enable WebSocket transport
            proxy_handler["transport"] = {
                "protocol": "http",
                "versions": ["1.1", "2"]
            }
        
        route["handle"].append(proxy_handler)
        
        return route
    
    def add_route(self, route_id: str, route_config: Dict) -> bool:
        """Add a single route to Caddy"""
        try:
            caddy_config = route_config['caddy_config']
            
            # Add route to Caddy via Admin API
            response = requests.post(
                f"{self.caddy_admin_url}/config/apps/http/servers/srv0/routes",
                json=caddy_config,
                timeout=10
            )
            
            if response.status_code in [200, 201]:
                self.logger.info(f"Added Caddy route {route_id}: {route_config.get('domain')} -> {route_config.get('upstream')}")
                return True
            else:
                self.logger.error(f"Failed to add Caddy route {route_id}: HTTP {response.status_code} - {response.text}")
                return False
                
        except Exception as e:
            self.logger.error(f"Error adding Caddy route {route_id}: {e}")
            return False
    
    def remove_route(self, route_id: str) -> bool:
        """Remove a single route from Caddy"""
        try:
            # Find the route index in Caddy config
            response = requests.get(f"{self.caddy_admin_url}/config/apps/http/servers/srv0/routes", timeout=10)
            if response.status_code != 200:
                self.logger.error(f"Failed to get current Caddy routes: HTTP {response.status_code}")
                return False
            
            current_routes = response.json()
            route_index = None
            
            # Find our route by matching domain or other identifiers
            route_info = self.managed_routes.get(route_id, {})
            target_domain = route_info.get('domain')
            
            if target_domain:
                for i, route in enumerate(current_routes):
                    if route.get('match', [{}])[0].get('host') == [target_domain]:
                        route_index = i
                        break
            
            if route_index is not None:
                # Remove the specific route
                response = requests.delete(
                    f"{self.caddy_admin_url}/config/apps/http/servers/srv0/routes/{route_index}",
                    timeout=10
                )
                
                if response.status_code in [200, 204]:
                    self.logger.info(f"Removed Caddy route {route_id} for domain {target_domain}")
                    return True
                else:
                    self.logger.error(f"Failed to remove Caddy route {route_id}: HTTP {response.status_code} - {response.text}")
                    return False
            else:
                self.logger.warning(f"Could not find Caddy route {route_id} with domain {target_domain}")
                return True  # Consider it successful if not found
                
        except Exception as e:
            self.logger.error(f"Error removing Caddy route {route_id}: {e}")
            return False
    
    def sync_with_retry(self, monitored_containers: Dict) -> bool:
        """Sync container changes to Caddy with retry logic"""
        for attempt in range(self.retry_attempts):
            try:
                if not self.test_caddy_health():
                    if attempt < self.retry_attempts - 1:
                        self.logger.warning(f"Caddy unavailable, retrying in {self.retry_delay}s (attempt {attempt + 1}/{self.retry_attempts})")
                        time.sleep(self.retry_delay)
                        continue
                    else:
                        self.logger.error("Caddy unavailable after all retry attempts")
                        return False
                
                # Generate desired routes from current containers
                desired_routes = self.generate_routes_from_containers(monitored_containers)
                
                # Calculate changes
                current_route_ids = set(self.managed_routes.keys())
                desired_route_ids = set(desired_routes.keys())
                
                routes_to_add = desired_route_ids - current_route_ids
                routes_to_remove = current_route_ids - desired_route_ids
                routes_to_check = current_route_ids & desired_route_ids
                
                # Check for modifications in existing routes
                routes_to_modify = set()
                for route_id in routes_to_check:
                    current_route = self.managed_routes[route_id]
                    desired_route = desired_routes[route_id]
                    
                    # Compare key properties
                    if (current_route.get('upstream') != desired_route.get('upstream') or
                        current_route.get('domain') != desired_route.get('domain')):
                        routes_to_modify.add(route_id)
                
                # Apply changes
                success = True
                
                # Remove old routes
                for route_id in routes_to_remove:
                    if not self.remove_route(route_id):
                        success = False
                
                # Modify changed routes (remove + add)
                for route_id in routes_to_modify:
                    if not self.remove_route(route_id) or not self.add_route(route_id, desired_routes[route_id]):
                        success = False
                
                # Add new routes
                for route_id in routes_to_add:
                    if not self.add_route(route_id, desired_routes[route_id]):
                        success = False
                
                if success:
                    # Update our state
                    self.managed_routes = desired_routes
                    self.save_state()
                    
                    total_changes = len(routes_to_add) + len(routes_to_remove) + len(routes_to_modify)
                    if total_changes > 0:
                        self.logger.info(f"Successfully synced Caddy routes: +{len(routes_to_add)} -{len(routes_to_remove)} ~{len(routes_to_modify)}")
                    
                    return True
                else:
                    if attempt < self.retry_attempts - 1:
                        self.logger.warning(f"Some route updates failed, retrying in {self.retry_delay}s (attempt {attempt + 1}/{self.retry_attempts})")
                        time.sleep(self.retry_delay)
                        continue
                    else:
                        self.logger.error("Failed to sync all routes after all retry attempts")
                        return False
                        
            except Exception as e:
                if attempt < self.retry_attempts - 1:
                    self.logger.error(f"Error syncing with Caddy: {e}, retrying in {self.retry_delay}s (attempt {attempt + 1}/{self.retry_attempts})")
                    time.sleep(self.retry_delay)
                else:
                    self.logger.error(f"Error syncing with Caddy after all retries: {e}")
                    return False
        
        return False
    
    def startup_recovery(self, monitored_containers: Dict):
        """Clean up inconsistencies on startup"""
        self.logger.info("Performing Caddy startup recovery...")
        
        # Generate what routes should exist based on current containers
        desired_routes = self.generate_routes_from_containers(monitored_containers)
        
        # Find orphaned routes (in state but container no longer exists)
        orphaned_routes = []
        for route_id, route_info in self.managed_routes.items():
            container_key = route_info.get('container_key')
            if container_key not in monitored_containers:
                orphaned_routes.append(route_id)
        
        # Remove orphaned routes
        for route_id in orphaned_routes:
            self.logger.info(f"Removing orphaned route {route_id}")
            self.remove_route(route_id)
            del self.managed_routes[route_id]
        
        # Perform full sync
        if self.sync_with_retry(monitored_containers):
            self.logger.info("Caddy startup recovery completed successfully")
        else:
            self.logger.error("Caddy startup recovery failed")