"""
Service Registry and Validation Schemas for Docker Monitor

This module contains the service registry that defines supported service types
and their validation schemas. Currently supports reverse proxy (revp) services
with planned support for additional service types.
"""

from typing import Dict, List, Optional, Callable

# Service Registry - Shared between CaddyManager and ContainerProcessor
SERVICE_SCHEMAS = {
    'revp': {  # Reverse Proxy - Currently Implemented
        'description': 'Reverse Proxy Service (Caddy HTTP/HTTPS)',
        'required': ['domain', 'port'],
        'optional': {
            'path': '/',
            'scheme': 'http',  # http, https
            'websocket': 'false',  # true, false
            'ssl_force': None,  # auto-determined based on scheme if not specified
            'middleware': '',
            'headers': ''
        },
        'validation': {
            'port': lambda x: x.isdigit() and 1 <= int(x) <= 65535,
            'scheme': lambda x: x.lower() in ['http', 'https'],
            'websocket': lambda x: x.lower() in ['true', 'false'],
            'ssl_force': lambda x: x.lower() in ['true', 'false'] if x else True,
            'path': lambda x: x.startswith('/') if x else True
        }
    }
    
    # Future service types (architecture ready):
    # 'tcp': TCP load balancing for databases, raw TCP services
    # 'udp': UDP load balancing for DNS, gaming, real-time protocols  
    # 'grpc': gRPC services with HTTP/2, load balancing, health checks
    # 'files': File servers with directory browsing, WebDAV, auth
    # 'stream': Media streaming with bandwidth limits, CDN integration
}

def get_supported_service_types() -> List[str]:
    """Get list of currently supported service types"""
    return list(SERVICE_SCHEMAS.keys())

def get_service_schema(service_type: str) -> Optional[Dict]:
    """Get schema for a specific service type"""
    return SERVICE_SCHEMAS.get(service_type.lower())

def validate_service_property(service_type: str, property_name: str, value: str) -> bool:
    """Validate a single service property value"""
    schema = get_service_schema(service_type)
    if not schema:
        return False
    
    validators = schema.get('validation', {})
    validator = validators.get(property_name)
    
    if validator:
        try:
            return validator(value)
        except Exception:
            return False
    
    return True  # No specific validation, assume valid

def get_service_examples() -> Dict[str, Dict]:
    """Get example service configurations"""
    return {
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

def get_planned_services() -> Dict[str, Dict]:
    """Get information about planned but not yet implemented service types"""
    return {
        'api': {
            'description': 'API Service (Planned)',
            'purpose': 'API services with rate limiting, authentication, CORS headers',
            'example_features': ['Rate limiting', 'Authentication middleware', 'CORS headers', 'API versioning'],
            'sample_labels': {
                'snadboy.api.domain': 'api.example.com',
                'snadboy.api.port': '8080', 
                'snadboy.api.rate_limit': '1000',
                'snadboy.api.auth': 'bearer'
            }
        },
        'web': {
            'description': 'Web Application Service (Planned)',
            'purpose': 'Web apps with SSL redirect, caching, compression, static file serving',
            'example_features': ['SSL redirect', 'Gzip compression', 'Static file caching', 'Security headers'],
            'sample_labels': {
                'snadboy.web.domain': 'myapp.example.com',
                'snadboy.web.port': '80',
                'snadboy.web.ssl_redirect': 'true',
                'snadboy.web.compression': 'true'
            }
        },
        'db': {
            'description': 'Database Service (Planned)', 
            'purpose': 'Database services with TCP proxying, health checks, connection pooling',
            'example_features': ['TCP load balancing', 'Health checks', 'Connection pooling', 'Read/write routing'],
            'sample_labels': {
                'snadboy.db.domain': 'db.example.com',
                'snadboy.db.port': '5432',
                'snadboy.db.protocol': 'tcp',
                'snadboy.db.read_only': 'false'
            }
        },
        'metrics': {
            'description': 'Metrics Service (Planned)',
            'purpose': 'Monitoring endpoints with Prometheus integration and scrape configuration',
            'example_features': ['Prometheus discovery', 'Scrape intervals', 'Metric authentication', 'Alert routing'],
            'sample_labels': {
                'snadboy.metrics.domain': 'metrics.example.com',
                'snadboy.metrics.port': '9090',
                'snadboy.metrics.path': '/metrics',
                'snadboy.metrics.scrape_interval': '30s'
            }
        }
    }