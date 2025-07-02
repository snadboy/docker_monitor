"""
Configuration Loading and Utilities

This module provides configuration loading from environment variables and defaults,
along with utility functions for configuration validation and setup.
"""

import os
from typing import Dict


def load_config() -> Dict:
    """Load configuration from environment variables and defaults"""
    config = {
        # Logging configuration
        'log_level': os.getenv('LOG_LEVEL', 'INFO'),
        'console_logging': os.getenv('CONSOLE_LOGGING', 'true').lower() == 'true',
        'file_logging': os.getenv('FILE_LOGGING', 'true').lower() == 'true',
        'log_directory': os.getenv('LOG_DIRECTORY', '/app/logs'),
        'log_max_size': int(os.getenv('LOG_MAX_SIZE', '10485760')),
        'log_max_count': int(os.getenv('LOG_MAX_COUNT', '5')),
        
        # API configuration
        'api_port': int(os.getenv('API_PORT', '8080')),
        
        # Docker configuration
        'docker_hosts_local': os.getenv('DOCKER_HOSTS_LOCAL', 'true').lower() == 'true',
        'docker_hosts_ssh': os.getenv('DOCKER_HOSTS_SSH'),
        
        # Label prefix
        'label_prefix': os.getenv('LABEL_PREFIX', 'snadboy.'),
        
        # Host IP overrides
        'local_host_ip': os.getenv('LOCAL_HOST_IP'),
        
        # SSH connection details
        'ssh_user': os.getenv('SSH_USER', 'root'),
        'ssh_port': int(os.getenv('SSH_PORT', '22')),
        'ssh_auto_populate_known_hosts': os.getenv('SSH_AUTO_POPULATE_KNOWN_HOSTS', 'true').lower() == 'true',
        'ssh_disable_host_checking_fallback': os.getenv('SSH_DISABLE_HOST_CHECKING_FALLBACK', 'false').lower() == 'true',
        
        # Caddy integration
        'caddy_enabled': os.getenv('CADDY_ENABLED', 'false').lower() == 'true',
        'caddy_admin_url': os.getenv('CADDY_ADMIN_URL', 'http://localhost:2019'),
        'caddy_state_file': os.getenv('CADDY_STATE_FILE', '/app/data/caddy-state.json'),
        'caddy_sync_interval': int(os.getenv('CADDY_SYNC_INTERVAL', '15')),
        'caddy_retry_attempts': int(os.getenv('CADDY_RETRY_ATTEMPTS', '3')),
        'caddy_retry_delay': int(os.getenv('CADDY_RETRY_DELAY', '5')),
    }
    
    # Only set ssh_directory if explicitly provided
    if os.getenv('SSH_DIRECTORY'):
        config['ssh_directory'] = os.getenv('SSH_DIRECTORY')
    
    # Auto-detect local paths when running outside container
    if not os.path.exists('/.dockerenv'):
        if config['log_directory'] == '/app/logs':
            config['log_directory'] = './logs'
        if config['caddy_state_file'] == '/app/data/caddy-state.json':
            config['caddy_state_file'] = './data/caddy-state.json'
    
    return config


def validate_config(config: Dict) -> Dict:
    """Validate configuration and return any warnings or errors"""
    warnings = []
    errors = []
    
    # Validate log level
    valid_log_levels = ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']
    if config['log_level'].upper() not in valid_log_levels:
        errors.append(f"Invalid log level '{config['log_level']}'. Must be one of: {valid_log_levels}")
    
    # Validate API port
    if not (1 <= config['api_port'] <= 65535):
        errors.append(f"Invalid API port {config['api_port']}. Must be between 1 and 65535")
    
    # Validate SSH port
    if not (1 <= config['ssh_port'] <= 65535):
        errors.append(f"Invalid SSH port {config['ssh_port']}. Must be between 1 and 65535")
    
    # Validate Caddy sync interval
    if config['caddy_sync_interval'] < 1:
        errors.append(f"Invalid Caddy sync interval {config['caddy_sync_interval']}. Must be at least 1 second")
    
    # Validate Caddy retry attempts
    if config['caddy_retry_attempts'] < 1:
        errors.append(f"Invalid Caddy retry attempts {config['caddy_retry_attempts']}. Must be at least 1")
    
    # Validate Caddy retry delay
    if config['caddy_retry_delay'] < 1:
        errors.append(f"Invalid Caddy retry delay {config['caddy_retry_delay']}. Must be at least 1 second")
    
    # Check for Docker host configuration
    has_local = config['docker_hosts_local']
    has_ssh = bool(config.get('docker_hosts_ssh', '').strip())
    
    if not has_local and not has_ssh:
        warnings.append("No Docker hosts configured. Will default to local Docker host")
    
    # Check Caddy configuration
    if config['caddy_enabled']:
        if not config['caddy_admin_url']:
            errors.append("Caddy enabled but no admin URL specified")
        elif config['caddy_admin_url'] == 'http://localhost:2019' and os.path.exists('/.dockerenv'):
            warnings.append("Caddy Admin URL is localhost but running in Docker container. This may not work correctly")
    
    # Check SSH configuration
    if has_ssh:
        ssh_hosts = config.get('docker_hosts_ssh', '').strip()
        if ssh_hosts:
            # Count number of SSH hosts
            ssh_entries = ssh_hosts.replace('\n', ' ').split()
            ssh_ips = [entry.split('#')[0].strip() for entry in ssh_entries if entry.split('#')[0].strip()]
            if ssh_ips:
                warnings.append(f"SSH hosts configured: {len(ssh_ips)} hosts. Ensure SSH keys are properly configured")
    
    return {
        'valid': len(errors) == 0,
        'warnings': warnings,
        'errors': errors
    }


def get_config_summary(config: Dict) -> Dict:
    """Get a summary of the current configuration"""
    ssh_hosts_count = 0
    if config.get('docker_hosts_ssh'):
        ssh_entries = config['docker_hosts_ssh'].replace('\n', ' ').split()
        ssh_hosts_count = len([entry.split('#')[0].strip() for entry in ssh_entries if entry.split('#')[0].strip()])
    
    return {
        'version': '2.5.0-enhanced-health',
        'logging': {
            'level': config['log_level'],
            'console': config['console_logging'],
            'file': config['file_logging'],
            'directory': config['log_directory']
        },
        'api': {
            'port': config['api_port']
        },
        'docker_hosts': {
            'local_enabled': config['docker_hosts_local'],
            'ssh_hosts_count': ssh_hosts_count,
            'label_prefix': config['label_prefix']
        },
        'ssh': {
            'user': config['ssh_user'],
            'port': config['ssh_port'],
            'auto_populate_known_hosts': config['ssh_auto_populate_known_hosts']
        },
        'caddy': {
            'enabled': config['caddy_enabled'],
            'admin_url': config['caddy_admin_url'] if config['caddy_enabled'] else None,
            'sync_interval': config['caddy_sync_interval'] if config['caddy_enabled'] else None
        },
        'environment': {
            'in_docker': os.path.exists('/.dockerenv'),
            'log_dir_auto_detected': config['log_directory'] in ['./logs', '/app/logs'],
            'caddy_state_auto_detected': config['caddy_state_file'] in ['./data/caddy-state.json', '/app/data/caddy-state.json']
        }
    }


def print_config_summary(config: Dict, logger=None):
    """Print a formatted configuration summary"""
    summary = get_config_summary(config)
    validation = validate_config(config)
    
    def log_or_print(message, level='info'):
        if logger:
            getattr(logger, level)(message)
        else:
            print(message)
    
    log_or_print("=" * 60)
    log_or_print(f"Enhanced Docker Monitor v{summary['version']}")
    log_or_print("=" * 60)
    
    # Docker Hosts
    log_or_print(f"📋 Docker Hosts:")
    if summary['docker_hosts']['local_enabled']:
        log_or_print(f"   ✅ Local Docker host enabled")
    if summary['docker_hosts']['ssh_hosts_count'] > 0:
        log_or_print(f"   🔗 {summary['docker_hosts']['ssh_hosts_count']} SSH hosts configured")
    log_or_print(f"   🏷️  Label prefix: {summary['docker_hosts']['label_prefix']}")
    
    # API Configuration
    log_or_print(f"🌐 API Server:")
    log_or_print(f"   Port: {summary['api']['port']}")
    log_or_print(f"   Health endpoints: /health, /healthz, /readiness")
    log_or_print(f"   Web dashboard: /dashboard")
    
    # Logging
    log_or_print(f"📝 Logging:")
    log_or_print(f"   Level: {summary['logging']['level']}")
    log_or_print(f"   Console: {'enabled' if summary['logging']['console'] else 'disabled'}")
    log_or_print(f"   File: {'enabled' if summary['logging']['file'] else 'disabled'}")
    if summary['logging']['file']:
        log_or_print(f"   Directory: {summary['logging']['directory']}")
    
    # Caddy Integration
    if summary['caddy']['enabled']:
        log_or_print(f"🔄 Caddy Integration:")
        log_or_print(f"   Admin URL: {summary['caddy']['admin_url']}")
        log_or_print(f"   Sync interval: {summary['caddy']['sync_interval']}s")
    else:
        log_or_print(f"🔄 Caddy Integration: disabled")
    
    # SSH Configuration
    if summary['docker_hosts']['ssh_hosts_count'] > 0:
        log_or_print(f"🔐 SSH Configuration:")
        log_or_print(f"   User: {summary['ssh']['user']}")
        log_or_print(f"   Port: {summary['ssh']['port']}")
        log_or_print(f"   Auto-populate known_hosts: {'enabled' if summary['ssh']['auto_populate_known_hosts'] else 'disabled'}")
    
    # Environment
    log_or_print(f"🏗️  Environment:")
    log_or_print(f"   Running in Docker: {'yes' if summary['environment']['in_docker'] else 'no'}")
    
    # Validation Results
    if validation['warnings']:
        log_or_print(f"⚠️  Warnings:")
        for warning in validation['warnings']:
            log_or_print(f"   - {warning}")
    
    if validation['errors']:
        log_or_print(f"❌ Errors:")
        for error in validation['errors']:
            log_or_print(f"   - {error}", 'error')
    
    if validation['valid'] and not validation['warnings']:
        log_or_print(f"✅ Configuration is valid")
    
    log_or_print("=" * 60)


def override_config_from_args(config: Dict, args) -> Dict:
    """Override configuration with command line arguments"""
    if hasattr(args, 'log_level') and args.log_level:
        config['log_level'] = args.log_level
    if hasattr(args, 'api_port') and args.api_port:
        config['api_port'] = args.api_port
    if hasattr(args, 'label_prefix') and args.label_prefix:
        config['label_prefix'] = args.label_prefix
    if hasattr(args, 'caddy_enabled') and args.caddy_enabled:
        config['caddy_enabled'] = True
    if hasattr(args, 'caddy_admin_url') and args.caddy_admin_url:
        config['caddy_admin_url'] = args.caddy_admin_url
    if hasattr(args, 'caddy_sync_interval') and args.caddy_sync_interval:
        config['caddy_sync_interval'] = args.caddy_sync_interval
    
    return config