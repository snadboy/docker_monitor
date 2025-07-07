#!/usr/bin/env python3
"""
Enhanced Docker Monitor - Application Entry Point

This is the main entry point for the Enhanced Docker Monitor application.
It handles command line arguments, configuration, and starts the monitoring service.
"""

import argparse
import signal
import sys
import os

from docker_monitor import (
    DockerMonitor, 
    load_config, 
    validate_config, 
    print_config_summary, 
    override_config_from_args,
    get_version_info
)


def setup_signal_handlers():
    """Setup signal handlers for graceful shutdown"""
    def signal_handler(signum, frame):
        print(f"\nReceived signal {signum}. Shutting down gracefully...")
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)


def create_argument_parser():
    """Create and configure the argument parser"""
    parser = argparse.ArgumentParser(
        description='Enhanced Docker Container Monitor with Multi-Host Support',
        epilog='''
Examples:
  %(prog)s --log-level DEBUG --caddy-enabled
  %(prog)s --api-port 9090 --caddy-admin-url http://caddy:2019
  %(prog)s --label-prefix "myapp." --caddy-sync-interval 30
  
Environment Variables:
  LOG_LEVEL              Logging level (DEBUG, INFO, WARNING, ERROR)
  API_PORT              API server port (default: 8080)
  DOCKER_HOSTS_LOCAL    Enable local Docker host (default: true)
  DOCKER_HOSTS_SSH      Space-separated list of SSH host IPs
  SSH_USER              SSH username (default: root)
  CADDY_ENABLED         Enable Caddy integration (default: false)
  CADDY_ADMIN_URL       Caddy Admin API URL (default: http://localhost:2019)
  LABEL_PREFIX          Container label prefix (default: snadboy.)
        ''',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    # Version
    parser.add_argument(
        '--version', '-v',
        action='version',
        version=f"Enhanced Docker Monitor v{get_version_info()['version']}"
    )
    
    # Logging options
    logging_group = parser.add_argument_group('Logging Options')
    logging_group.add_argument(
        '--log-level',
        choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'],
        help='Set logging level (overrides LOG_LEVEL env var)'
    )
    logging_group.add_argument(
        '--no-console-logging',
        action='store_true',
        help='Disable console logging'
    )
    logging_group.add_argument(
        '--no-file-logging',
        action='store_true',
        help='Disable file logging'
    )
    logging_group.add_argument(
        '--log-directory',
        help='Log file directory (overrides LOG_DIRECTORY env var)'
    )
    
    # API options
    api_group = parser.add_argument_group('API Server Options')
    api_group.add_argument(
        '--api-port',
        type=int,
        help='API server port (overrides API_PORT env var, default: 8080)'
    )
    
    # Docker options
    docker_group = parser.add_argument_group('Docker Host Options')
    docker_group.add_argument(
        '--docker-hosts-ssh',
        help='Space-separated SSH host IPs (overrides DOCKER_HOSTS_SSH env var)'
    )
    docker_group.add_argument(
        '--ssh-user',
        help='SSH username (overrides SSH_USER env var, default: root)'
    )
    docker_group.add_argument(
        '--label-prefix',
        help='Container label prefix to monitor (overrides LABEL_PREFIX env var, default: snadboy.)'
    )
    docker_group.add_argument(
        '--local-host-ip',
        help='Override local host IP detection (overrides LOCAL_HOST_IP env var)'
    )
    
    # Caddy options
    caddy_group = parser.add_argument_group('Caddy Integration Options')
    caddy_group.add_argument(
        '--caddy-enabled',
        action='store_true',
        help='Enable Caddy reverse proxy integration'
    )
    caddy_group.add_argument(
        '--caddy-admin-url',
        help='Caddy Admin API URL (overrides CADDY_ADMIN_URL env var, default: http://localhost:2019)'
    )
    caddy_group.add_argument(
        '--caddy-sync-interval',
        type=int,
        help='Caddy sync interval in seconds (overrides CADDY_SYNC_INTERVAL env var, default: 15)'
    )
    caddy_group.add_argument(
        '--caddy-state-file',
        help='Caddy state file path (overrides CADDY_STATE_FILE env var)'
    )
    
    # Utility options
    util_group = parser.add_argument_group('Utility Options')
    util_group.add_argument(
        '--config-check',
        action='store_true',
        help='Check configuration and exit'
    )
    util_group.add_argument(
        '--config-summary',
        action='store_true',
        help='Print configuration summary and exit'
    )
    util_group.add_argument(
        '--version-info',
        action='store_true',
        help='Print detailed version information and exit'
    )
    
    return parser


def apply_cli_overrides(config, args):
    """Apply command line argument overrides to configuration"""
    # Apply standard overrides
    config = override_config_from_args(config, args)
    
    # Apply additional CLI-specific overrides
    if args.no_console_logging:
        config['console_logging'] = False
    if args.no_file_logging:
        config['file_logging'] = False
    if args.log_directory:
        config['log_directory'] = args.log_directory
    if args.docker_hosts_ssh:
        config['docker_hosts_ssh'] = args.docker_hosts_ssh
    if args.ssh_user:
        config['ssh_user'] = args.ssh_user
    if args.local_host_ip:
        config['local_host_ip'] = args.local_host_ip
    if args.caddy_state_file:
        config['caddy_state_file'] = args.caddy_state_file
    
    return config


def main():
    """Main application entry point"""
    # Setup signal handlers
    setup_signal_handlers()
    
    # Parse command line arguments
    parser = create_argument_parser()
    args = parser.parse_args()
    
    # Handle utility options
    if args.version_info:
        version_info = get_version_info()
        print(f"Enhanced Docker Monitor v{version_info['version']}")
        print(f"Description: {version_info['description']}")
        print(f"Author: {version_info['author']}")
        print()
        print("Features:")
        for feature in version_info['features']:
            print(f"  • {feature}")
        print()
        print(f"Supported Service Types: {', '.join(version_info['supported_service_types'])}")
        print(f"Planned Service Types: {', '.join(version_info['planned_service_types'])}")
        print()
        print("API Endpoints:")
        for category, endpoints in version_info['endpoints'].items():
            print(f"  {category}: {', '.join(endpoints)}")
        return 0
    
    # Load configuration
    try:
        config = load_config()
        config = apply_cli_overrides(config, args)
    except Exception as e:
        print(f"Error loading configuration: {e}", file=sys.stderr)
        return 1
    
    # Validate configuration
    validation = validate_config(config)
    
    if args.config_check:
        print("Configuration validation:")
        if validation['valid']:
            print("✅ Configuration is valid")
        else:
            print("❌ Configuration has errors:")
            for error in validation['errors']:
                print(f"   - {error}")
        
        if validation['warnings']:
            print("⚠️  Warnings:")
            for warning in validation['warnings']:
                print(f"   - {warning}")
        
        return 0 if validation['valid'] else 1
    
    if args.config_summary:
        print_config_summary(config)
        return 0
    
    # Check for configuration errors
    if not validation['valid']:
        print("❌ Configuration errors found:", file=sys.stderr)
        for error in validation['errors']:
            print(f"   - {error}", file=sys.stderr)
        print("\nUse --config-check to validate configuration", file=sys.stderr)
        return 1
    
    # Create and start the monitor
    try:
        monitor = DockerMonitor(config)
        
        # Print configuration summary if there are warnings
        if validation['warnings']:
            print_config_summary(config, monitor.logger)
        
        # Start the monitoring service
        success = monitor.start()
        return 0 if success else 1
        
    except KeyboardInterrupt:
        print("\nReceived interrupt signal. Shutting down...")
        return 0
    except Exception as e:
        print(f"Fatal error: {e}", file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())