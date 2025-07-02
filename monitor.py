"""
Main DockerMonitor Orchestrator

This module contains the main DockerMonitor class that coordinates all components,
manages container monitoring, and handles connection recovery.
"""

import threading
import time
import logging
import sys
from datetime import datetime
from pathlib import Path
from logging.handlers import RotatingFileHandler
from typing import Dict, List, Optional

from .managers import DockerHostManager, SSHSetupManager
from .processors import ContainerProcessor, CaddyManager
from .api_server import APIServer


class DockerMonitor:
    """Main orchestrator - coordinates all components with connection recovery"""
    
    def __init__(self, config: Dict):
        self.config = config
        self.running = False
        self.logger = self._setup_logging()
        
        # Setup SSH configuration for remote hosts
        self.ssh_setup = SSHSetupManager(config, self.logger)
        self.ssh_setup.setup_ssh_for_hosts()
        
        # Core components with clear separation of concerns
        self.host_manager = DockerHostManager(config, self.logger)
        self.container_processor = ContainerProcessor(config, self.logger)
        self.monitored_containers = {}
        
        # Caddy integration
        self.caddy_manager = CaddyManager(config, self.logger) if config.get('caddy_enabled') else None
        self.last_caddy_sync = 0
        self.caddy_sync_interval = config.get('caddy_sync_interval', 15)  # seconds
        
        # API server (will be started in separate thread)
        self.api_server = APIServer(self.monitored_containers, self.host_manager, self.logger, config, self.container_processor)
        # Pass caddy_manager reference to API server for status endpoints
        self.api_server.caddy_manager = self.caddy_manager
        
    def _setup_logging(self) -> logging.Logger:
        """Setup logging with both console and file handlers"""
        logger_name = f'docker_monitor_{id(self)}'
        logger = logging.getLogger(logger_name)
        logger.setLevel(getattr(logging, self.config['log_level'].upper()))
        logger.handlers.clear()
        logger.propagate = False
        
        # Console handler
        if self.config['console_logging']:
            console_handler = logging.StreamHandler(sys.stdout)
            console_handler.setLevel(getattr(logging, self.config['log_level'].upper()))
            console_formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            console_handler.setFormatter(console_formatter)
            logger.addHandler(console_handler)
        
        # File handler
        if self.config.get('file_logging'):
            log_dir = Path(self.config.get('log_directory', './logs'))
            log_dir.mkdir(parents=True, exist_ok=True)
            
            file_handler = RotatingFileHandler(
                log_dir / 'docker_monitor.log',
                maxBytes=self.config.get('log_max_size', 10485760),
                backupCount=self.config.get('log_max_count', 5)
            )
            file_handler.setLevel(getattr(logging, self.config['log_level'].upper()))
            file_formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            file_handler.setFormatter(file_formatter)
            logger.addHandler(file_handler)
        
        logger.info("Logger initialized successfully")
        return logger
    
    def _parse_docker_hosts(self) -> List[Dict]:
        """Parse Docker host configurations"""
        hosts = []
        
        # Add local host if enabled
        if self.config.get('docker_hosts_local'):
            hosts.append({
                'name': 'local',
                'type': 'local'
            })
        
        # Add SSH hosts
        ssh_hosts = self.config.get('docker_hosts_ssh', '').strip()
        if ssh_hosts:
            # Support both space and newline separated, and clean comments
            ssh_entries = ssh_hosts.replace('\n', ' ').split()
            ssh_ips = []
            
            for entry in ssh_entries:
                # Remove inline comments and clean whitespace
                clean_entry = entry.split('#')[0].strip()
                if clean_entry:  # Only add non-empty entries
                    ssh_ips.append(clean_entry)
            
            for ip in ssh_ips:
                hosts.append({
                    'name': ip,
                    'type': 'ssh'
                })
        
        # Default to local if no hosts specified
        if not hosts:
            hosts.append({
                'name': 'local',
                'type': 'local'
            })
        
        self.logger.info(f"Configured {len(hosts)} Docker host(s): {[h['name'] for h in hosts]}")
        return hosts
    
    def connect_docker_hosts(self) -> bool:
        """Connect to all configured Docker hosts"""
        docker_hosts = self._parse_docker_hosts()
        connected_count = 0
        
        for host_config in docker_hosts:
            if self.host_manager.add_host(host_config['name'], host_config):
                connected_count += 1
        
        if connected_count == 0:
            self.logger.error("No Docker hosts could be connected")
            return False
        
        self.logger.info(f"Connected to {connected_count}/{len(docker_hosts)} Docker hosts")
        
        # Log any initial connection errors
        errors = self.host_manager.get_host_errors()
        if errors:
            self.logger.warning(f"Initial connection errors for {len(errors)} hosts:")
            for host_name, error_info in errors.items():
                self.logger.warning(f"  - {host_name}: {error_info['error']}")
        
        return True
    
    def scan_existing_containers(self):
        """Scan for existing containers with snadboy labels across all hosts"""
        total_containers = 0
        
        all_containers = self.host_manager.get_all_containers()
        
        for host_name, containers in all_containers.items():
            host_containers = 0
            host_ip = self.host_manager.host_ips.get(host_name)
            
            self.logger.info(f"Host '{host_name}': Found {len(containers)} total containers")
            
            for container_data in containers:
                self.logger.debug(f"=== Container Debug: {container_data['name']} on {host_name} ===")
                self.logger.debug(f"Container ID: {container_data['id']}")
                self.logger.debug(f"Container status: {container_data['status']}")
                self.logger.debug(f"Container labels: {container_data['labels']}")
                
                # Check for snadboy labels using container processor
                if self.container_processor.has_snadboy_labels(container_data):
                    self.logger.debug(f"Found snadboy labels in container {container_data['name']}")
                    
                    # Process container
                    container_info = self.container_processor.process_container(container_data, host_name, host_ip)
                    
                    if container_info:
                        container_key = f"{host_name}:{container_data['id']}"
                        self.monitored_containers[container_key] = container_info
                        host_containers += 1
                        self.logger.info(f"Found container on '{host_name}': {container_info['name']} with snadboy labels")
                else:
                    self.logger.debug(f"No snadboy labels found in container {container_data['name']}")
            
            self.logger.info(f"Host '{host_name}': Found {host_containers} containers with snadboy labels")
            total_containers += host_containers
        
        self.logger.info(f"Initial scan complete. Monitoring {total_containers} containers across {len(self.host_manager.hosts)} hosts")
        
        # Caddy startup recovery
        if self.caddy_manager:
            self.caddy_manager.startup_recovery(self.monitored_containers)
    
    def sync_caddy_if_needed(self):
        """Sync with Caddy every 15 seconds if there are changes"""
        if not self.caddy_manager:
            return
            
        now = time.time()
        if now - self.last_caddy_sync >= self.caddy_sync_interval:
            try:
                self.caddy_manager.sync_with_retry(self.monitored_containers)
                self.last_caddy_sync = now
            except Exception as e:
                self.logger.error(f"Error syncing with Caddy: {e}")
    
    def start_caddy_sync_thread(self):
        """Start background thread for periodic Caddy syncing"""
        if not self.caddy_manager:
            return None
            
        def caddy_sync_loop():
            """Background thread that syncs with Caddy every 15 seconds"""
            self.logger.info(f"Starting Caddy sync thread (interval: {self.caddy_sync_interval}s)")
            
            while self.running:
                try:
                    self.sync_caddy_if_needed()
                    time.sleep(1)  # Check every second, but only sync every 15s
                except Exception as e:
                    self.logger.error(f"Error in Caddy sync thread: {e}")
                    time.sleep(5)  # Wait a bit before retrying
        
        caddy_thread = threading.Thread(target=caddy_sync_loop, daemon=True, name="CaddySync")
        caddy_thread.start()
        self.logger.info("Started Caddy sync thread")
        return caddy_thread
    
    def start_connection_recovery_thread(self):
        """Start background thread to attempt reconnection to failed hosts"""
        def recovery_loop():
            """Background thread that attempts reconnection with exponential backoff"""
            self.logger.info("Starting connection recovery thread")
            
            while self.running:
                try:
                    # Get hosts that need recovery attempts
                    recovery_candidates = self.host_manager.get_hosts_needing_recovery()
                    
                    for host_name in recovery_candidates:
                        if not self.running:
                            break
                        
                        self.logger.info(f"Attempting recovery for host '{host_name}'")
                        success = self.host_manager.attempt_reconnection(host_name)
                        
                        if success:
                            # If reconnection successful, rescan containers and restart monitoring
                            self.logger.info(f"Host '{host_name}' recovered, rescanning containers...")
                            
                            # Get new containers from recovered host
                            host = self.host_manager.hosts.get(host_name)
                            if host and host.status == 'connected':
                                try:
                                    containers = host.get_containers()
                                    host_ip = self.host_manager.host_ips.get(host_name)
                                    
                                    # Process any new containers with snadboy labels
                                    for container_data in containers:
                                        if self.container_processor.has_snadboy_labels(container_data):
                                            container_info = self.container_processor.process_container(
                                                container_data, host_name, host_ip
                                            )
                                            if container_info:
                                                container_key = f"{host_name}:{container_data['id']}"
                                                self.monitored_containers[container_key] = container_info
                                                self.logger.info(f"Recovered container: {container_info['name']} on {host_name}")
                                    
                                    # Start monitoring thread for recovered host
                                    monitor_thread = threading.Thread(
                                        target=host.monitor_events,
                                        args=(self.handle_container_event,),
                                        daemon=True,
                                        name=f"Monitor-{host_name}-Recovery"
                                    )
                                    monitor_thread.start()
                                    self.logger.info(f"Restarted monitoring for recovered host '{host_name}'")
                                    
                                except Exception as e:
                                    self.logger.error(f"Error rescanning containers on recovered host '{host_name}': {e}")
                        else:
                            # Log the continued failure
                            failures = self.host_manager.consecutive_failures.get(host_name, 0)
                            self.logger.warning(f"Recovery failed for host '{host_name}' (attempt #{failures})")
                    
                    # Sleep for 10 seconds before checking again
                    time.sleep(10)
                    
                except Exception as e:
                    self.logger.error(f"Error in connection recovery thread: {e}")
                    time.sleep(30)  # Wait longer on exception
        
        recovery_thread = threading.Thread(target=recovery_loop, daemon=True, name="ConnectionRecovery")
        recovery_thread.start()
        self.logger.info("Started connection recovery thread")
        return recovery_thread
    
    def handle_container_event(self, event: Dict, host_name: str):
        """Handle container events from any host - COMPLETE IMPLEMENTATION"""
        try:
            container_id = event.get('id')
            action = event.get('Action')
            
            if not container_id:
                return
            
            container_key = f"{host_name}:{container_id}"
            host = self.host_manager.hosts.get(host_name)
            host_ip = self.host_manager.host_ips.get(host_name)
            
            self.logger.debug(f"Container event from '{host_name}': {action} for {container_id[:12]}")
            
            if action in ['create', 'start', 'restart']:
                try:
                    # Get detailed container information from the host
                    container_data = host.get_container_details(container_id)
                    
                    if container_data:
                        # Check if container has snadboy labels
                        if self.container_processor.has_snadboy_labels(container_data):
                            # Process container
                            container_info = self.container_processor.process_container(container_data, host_name, host_ip)
                            
                            if container_info:
                                self.monitored_containers[container_key] = container_info
                                self.logger.info(f"Added/Updated container on '{host_name}': {container_info['name']} ({action})")
                            else:
                                self.logger.warning(f"Failed to process container {container_id[:12]} despite having snadboy labels")
                        else:
                            self.logger.debug(f"Container {container_id[:12]} on '{host_name}' has no snadboy labels")
                    else:
                        self.logger.warning(f"Could not get details for container {container_id[:12]} on '{host_name}'")
                        
                except Exception as e:
                    self.logger.error(f"Error processing container {container_id[:12]} on '{host_name}': {e}")
                
            elif action in ['stop', 'kill', 'die', 'destroy']:
                if container_key in self.monitored_containers:
                    container_name = self.monitored_containers[container_key]['name']
                    if action == 'destroy':
                        del self.monitored_containers[container_key]
                        self.logger.info(f"Removed container from '{host_name}': {container_name} ({action})")
                    else:
                        # Update status for stop/kill/die events
                        self.monitored_containers[container_key]['status'] = action
                        self.monitored_containers[container_key]['last_updated'] = datetime.now().isoformat()
                        self.logger.info(f"Updated container on '{host_name}': {container_name} -> {action}")
                
                # Trigger immediate Caddy sync for responsive updates
                if self.caddy_manager:
                    # Reset sync timer to trigger sync soon
                    self.last_caddy_sync = 0
                        
        except Exception as e:
            self.logger.error(f"Error handling container event from '{host_name}': {e}")
    
    def start_api_server(self):
        """Start the API server in a separate thread"""
        api_thread = threading.Thread(target=self.api_server.start, daemon=True, name="APIServer")
        api_thread.start()
        self.logger.info("Started API server thread")
        return api_thread
    
    def start(self):
        """Start the monitoring service"""
        self.logger.info("Starting Enhanced Docker Monitor...")
        
        if not self.connect_docker_hosts():
            self.logger.error("Failed to connect to Docker hosts. Exiting.")
            return False
        
        self.running = True
        
        # Scan existing containers
        self.scan_existing_containers()
        
        # Start API server
        api_thread = self.start_api_server()
        
        # Start Caddy sync thread
        caddy_thread = self.start_caddy_sync_thread()
        
        # Start connection recovery thread
        recovery_thread = self.start_connection_recovery_thread()
        
        # Start monitoring all connected hosts
        monitor_threads = self.host_manager.start_monitoring(self.handle_container_event)
        
        # Log startup summary
        connected_hosts = len(self.host_manager.get_connected_hosts())
        failed_hosts = len(self.host_manager.get_host_errors())
        total_containers = len(self.monitored_containers)
        
        self.logger.info("🚀 Enhanced Docker Monitor started successfully!")
        self.logger.info(f"📊 Status: {connected_hosts} hosts connected, {failed_hosts} hosts failed, {total_containers} containers monitored")
        
        if self.caddy_manager:
            caddy_status = "enabled" if self.caddy_manager.caddy_available else "enabled (unavailable)"
            self.logger.info(f"🔄 Caddy integration: {caddy_status}")
        
        if failed_hosts > 0:
            self.logger.info(f"🔄 Connection recovery active for {failed_hosts} failed hosts")
        
        self.logger.info(f"🌐 API server: http://localhost:{self.config.get('api_port', 8080)}")
        self.logger.info(f"❤️  Health checks: /health, /healthz, /readiness")
        
        try:
            # Wait for all monitoring threads
            for thread in monitor_threads:
                thread.join()
        except KeyboardInterrupt:
            self.logger.info("Received interrupt signal")
        finally:
            self.stop()
        
        return True
    
    def stop(self):
        """Stop the monitoring service"""
        self.logger.info("Stopping Enhanced Docker Monitor...")
        self.running = False
        self.host_manager.shutdown()
        self.logger.info("Docker Monitor stopped")