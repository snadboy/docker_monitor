"""
Enhanced Docker Monitor Package

A production-ready Docker container monitoring system with persistent error tracking,
intelligent connection recovery, Caddy reverse proxy integration, and service registry validation.

This package provides comprehensive Docker container monitoring capabilities across
multiple hosts (local and SSH), with real-time event processing, health monitoring,
and automatic reverse proxy configuration.
"""

__version__ = "2.5.0-enhanced-health"
__author__ = "Docker Monitor Team"
__description__ = "Production-ready Docker container monitoring with enhanced health tracking"

# Core components
from .monitor import DockerMonitor
from .config import load_config, validate_config, print_config_summary, override_config_from_args

# Host management
from .managers import DockerHostManager, SSHSetupManager
from .docker_hosts import DockerHost, LocalDockerHost, SSHDockerHost, DockerHostFactory

# Processing and integration
from .processors import ContainerProcessor, CaddyManager
from .api_server import APIServer

# Service registry
from .schemas import SERVICE_SCHEMAS, get_supported_service_types, get_service_examples, get_planned_services

# Public API
__all__ = [
    # Version info
    '__version__',
    '__author__',
    '__description__',
    
    # Main components
    'DockerMonitor',
    
    # Configuration
    'load_config',
    'validate_config', 
    'print_config_summary',
    'override_config_from_args',
    
    # Host management
    'DockerHostManager',
    'SSHSetupManager',
    'DockerHost',
    'LocalDockerHost', 
    'SSHDockerHost',
    'DockerHostFactory',
    
    # Processing
    'ContainerProcessor',
    'CaddyManager',
    'APIServer',
    
    # Service registry
    'SERVICE_SCHEMAS',
    'get_supported_service_types',
    'get_service_examples',
    'get_planned_services',
]


def create_monitor_from_config(config_overrides=None):
    """
    Convenience function to create a DockerMonitor instance with default configuration.
    
    Args:
        config_overrides (dict, optional): Configuration overrides to apply
        
    Returns:
        DockerMonitor: Configured monitor instance
        
    Example:
        >>> monitor = create_monitor_from_config({'log_level': 'DEBUG', 'caddy_enabled': True})
        >>> monitor.start()
    """
    config = load_config()
    
    if config_overrides:
        config.update(config_overrides)
    
    validation = validate_config(config)
    if not validation['valid']:
        raise ValueError(f"Invalid configuration: {validation['errors']}")
    
    return DockerMonitor(config)


def get_version_info():
    """
    Get detailed version and capability information.
    
    Returns:
        dict: Version and feature information
    """
    return {
        'version': __version__,
        'description': __description__,
        'author': __author__,
        'features': [
            'Multi-host Docker monitoring (local + SSH)',
            'Persistent error tracking with exponential backoff',
            'Container orchestration health checks (K8s, Docker Swarm)', 
            'Caddy reverse proxy integration',
            'Service registry with schema validation',
            'Real-time SSH diagnostics and troubleshooting',
            'Background connection recovery',
            'Comprehensive REST API',
            'Interactive web dashboard'
        ],
        'supported_service_types': list(SERVICE_SCHEMAS.keys()),
        'planned_service_types': list(get_planned_services().keys()),
        'endpoints': {
            'health': ['/health', '/healthz', '/readiness'],
            'api': ['/containers', '/labels', '/caddy', '/ips'],
            'debug': ['/debug', '/errors'],
            'docs': ['/', '/help', '/dashboard']
        }
    }


# Package metadata for introspection
PACKAGE_INFO = {
    'name': 'docker_monitor',
    'version': __version__,
    'description': __description__,
    'author': __author__,
    'supported_python': '>=3.7',
    'dependencies': [
        'docker>=6.0.0',
        'flask>=2.0.0', 
        'requests>=2.25.0'
    ],
    'optional_dependencies': {
        'ssh': ['paramiko>=2.7.0'],
        'dev': ['pytest>=6.0.0', 'black>=21.0.0', 'flake8>=3.8.0']
    }
}