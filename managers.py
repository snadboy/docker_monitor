"""
Docker Host Abstractions and Implementations

This module provides the abstract base class for Docker hosts and concrete
implementations for local and SSH-based Docker connections.
"""

import docker
import json
import subprocess
import socket
import time
import os
import signal
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Callable
import logging


class DockerHost(ABC):
    """Abstract base class for Docker host connections"""
    
    def __init__(self, name: str, config: Dict, logger: logging.Logger):
        self.name = name
        self.config = config
        self.logger = logger
        self.status = 'disconnected'
        self.error_message = None
        
    @abstractmethod
    def connect(self) -> bool:
        """Connect to Docker host. Returns True if successful."""
        pass
    
    @abstractmethod
    def disconnect(self):
        """Clean up connection resources"""
        pass
    
    @abstractmethod
    def test_connection(self) -> bool:
        """Test if connection is still alive"""
        pass
    
    @abstractmethod
    def get_containers(self) -> List[Dict]:
        """Get all containers from this host"""
        pass
    
    @abstractmethod
    def get_container_details(self, container_id: str) -> Optional[Dict]:
        """Get detailed container information"""
        pass
    
    @abstractmethod
    def monitor_events(self, event_callback: Callable[[Dict, str], None]):
        """Start monitoring Docker events (blocking call)"""
        pass
    
    @abstractmethod
    def get_host_ip(self) -> Optional[str]:
        """Get the IP address for this host (for Caddy routing)"""
        pass
    
    def get_type(self) -> str:
        """Get host type identifier"""
        return self.__class__.__name__.lower().replace('dockerhost', '')


class LocalDockerHost(DockerHost):
    """Local Docker host using Docker Python library"""
    
    def __init__(self, name: str, config: Dict, logger: logging.Logger):
        super().__init__(name, config, logger)
        self.client = None
        
    def connect(self) -> bool:
        """Connect to local Docker daemon"""
        try:
            self.logger.debug(f"Connecting to local Docker host '{self.name}'")
            self.client = docker.from_env()
            self.client.ping()
            self.status = 'connected'
            self.error_message = None
            self.logger.info(f"Successfully connected to local Docker host '{self.name}'")
            return True
            
        except Exception as e:
            self.status = 'failed'
            self.error_message = str(e)
            self.logger.error(f"Failed to connect to local Docker host '{self.name}': {e}")
            return False
    
    def disconnect(self):
        """Close local Docker client"""
        if self.client:
            try:
                self.client.close()
                self.logger.info(f"Closed connection to local Docker host '{self.name}'")
            except Exception as e:
                self.logger.error(f"Error closing local Docker connection '{self.name}': {e}")
            finally:
                self.client = None
                self.status = 'disconnected'
    
    def test_connection(self) -> bool:
        """Test local Docker connection"""
        try:
            if self.client:
                self.client.ping()
                return True
        except Exception as e:
            self.logger.error(f"Local Docker connection test failed for '{self.name}': {e}")
            self.error_message = str(e)
        return False
    
    def get_containers(self) -> List[Dict]:
        """Get all containers from local Docker"""
        containers = []
        
        if not self.client or self.status != 'connected':
            return containers
            
        try:
            docker_containers = self.client.containers.list(all=True)
            
            for container in docker_containers:
                containers.append({
                    'id': container.id,
                    'short_id': container.short_id,
                    'name': container.name,
                    'status': container.status,
                    'labels': container.labels or {},
                    'image': container.image.tags[0] if container.image.tags else container.image.id,
                    'attrs': container.attrs,
                    'source': 'local'
                })
                
        except Exception as e:
            self.logger.error(f"Error getting containers from local host '{self.name}': {e}")
            
        return containers
    
    def get_container_details(self, container_id: str) -> Optional[Dict]:
        """Get detailed container information from local Docker"""
        try:
            if self.client and self.status == 'connected':
                container = self.client.containers.get(container_id)
                return {
                    'id': container.id,
                    'short_id': container.short_id,
                    'name': container.name,
                    'status': container.status,
                    'labels': container.labels or {},
                    'image': container.image.tags[0] if container.image.tags else container.image.id,
                    'attrs': container.attrs,
                    'source': 'local'
                }
        except Exception as e:
            self.logger.error(f"Error getting container details for '{container_id}' from local host: {e}")
        
        return None
    
    def monitor_events(self, event_callback: Callable[[Dict, str], None]):
        """Monitor Docker events from local host"""
        if not self.client or self.status != 'connected':
            return
            
        self.logger.info(f"Starting real-time event monitoring for local host '{self.name}'")
        
        try:
            for event in self.client.events(decode=True, filters={'type': 'container'}):
                event_callback(event, self.name)
                
        except Exception as e:
            self.logger.error(f"Error monitoring Docker events on local host '{self.name}': {e}")
            raise
    
    def get_host_ip(self) -> Optional[str]:
        """Get local host IP address"""
        # Check for explicit override
        if self.config.get('local_host_ip'):
            # Clean the IP - remove comments and whitespace
            raw_ip = self.config['local_host_ip'].strip()
            # Split on # to remove inline comments
            clean_ip = raw_ip.split('#')[0].strip()
            if clean_ip:
                # Validate it's a reasonable IP format
                try:
                    socket.inet_aton(clean_ip)  # Basic IP validation
                    self.logger.debug(f"Using explicit local IP override: {clean_ip}")
                    return clean_ip
                except socket.error:
                    self.logger.warning(f"Invalid IP format in LOCAL_HOST_IP: '{clean_ip}', falling back to auto-detection")
            
        # Auto-detect local IP
        try:
            # In Docker container, try multiple methods
            if os.path.exists('/.dockerenv'):
                # Try to get gateway IP (often the host IP in Docker bridge networks)
                try:
                    result = subprocess.run(['ip', 'route', 'show', 'default'], 
                                          capture_output=True, text=True, timeout=5)
                    if result.returncode == 0:
                        for line in result.stdout.split('\n'):
                            if 'default via' in line:
                                gateway_ip = line.split()[2]
                                return gateway_ip
                except Exception:
                    pass
            
            # Standard method: Connect to remote address to determine local IP
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                s.connect(("8.8.8.8", 80))
                local_ip = s.getsockname()[0]
                
                if local_ip.startswith('172.'):
                    self.logger.warning(f"Detected container internal IP ({local_ip}). Consider setting LOCAL_HOST_IP")
                
                return local_ip
                
        except Exception as e:
            self.logger.warning(f"Failed to detect local IP: {e}")
            
        return None


class SSHDockerHost(DockerHost):
    """SSH Docker host using SSH commands"""
    
    def __init__(self, name: str, config: Dict, logger: logging.Logger):
        super().__init__(name, config, logger)
        self.ssh_user = config.get('ssh_user', 'root')
        self.ssh_host = name  # IP address
        self.ssh_port = config.get('ssh_port', 22)
        
    def connect(self) -> bool:
        """Test SSH Docker connection with enhanced error capture"""
        try:
            self.logger.debug(f"Testing SSH Docker connection to '{self.name}'")
            
            # Try multiple approaches to capture SSH output
            captured_output = self._execute_ssh_with_multiple_methods()
            
            if captured_output['success']:
                self.status = 'connected'
                self.error_message = None
                self.logger.info(f"Successfully connected to SSH Docker host '{self.name}'")
                return True
            else:
                # Analyze the captured output for specific issues
                error_details = self._analyze_ssh_error(
                    captured_output['stderr'], 
                    captured_output['stdout'],
                    captured_output['timeout_occurred']
                )
                raise Exception(error_details)
                
        except Exception as e:
            self.status = 'failed'
            self.error_message = str(e)
            self.logger.error(f"Failed to connect to SSH Docker host '{self.name}': {e}")
            return False
    
    def _execute_ssh_with_multiple_methods(self) -> Dict:
        """Try multiple methods to capture SSH output, including interactive prompts"""
        
        # Method 1: Try with pseudo-TTY using pty module
        try:
            result = self._execute_ssh_with_pty()
            if result['stdout'] or result['stderr'] or result['success']:
                self.logger.debug("SSH pty method captured output successfully")
                return result
        except Exception as e:
            self.logger.debug(f"SSH pty method failed: {e}")
        
        # Method 2: Try with script command wrapper
        try:
            result = self._execute_ssh_with_script_wrapper()
            if result['stdout'] or result['stderr'] or result['success']:
                self.logger.debug("SSH script wrapper method captured output successfully")
                return result
        except Exception as e:
            self.logger.debug(f"SSH script wrapper method failed: {e}")
        
        # Method 3: Try with maximum verbosity
        try:
            result = self._execute_ssh_with_verbose()
            if result['stdout'] or result['stderr'] or result['success']:
                self.logger.debug("SSH verbose method captured output successfully")
                return result
        except Exception as e:
            self.logger.debug(f"SSH verbose method failed: {e}")
        
        # Method 4: Fallback to original method
        self.logger.debug("Using fallback SSH method")
        return self._execute_ssh_fallback()
    
    def _execute_ssh_with_pty(self) -> Dict:
        """Execute SSH using pseudo-TTY to capture interactive prompts"""
        import pty
        import fcntl
        
        # Build SSH command
        cmd = [
            'ssh',
            '-o', 'ConnectTimeout=10',
            '-o', 'StrictHostKeyChecking=ask',
            '-T',  # Disable pseudo-terminal allocation for the remote command
            f'{self.ssh_user}@{self.ssh_host}',
            'docker', 'version', '--format', 'json'
        ]
        
        self.logger.debug(f"Executing SSH with pty: {' '.join(cmd)}")
        
        # Create master and slave pty
        master_fd, slave_fd = pty.openpty()
        
        try:
            # Start the process with pty
            process = subprocess.Popen(
                cmd,
                stdin=slave_fd,
                stdout=slave_fd,
                stderr=slave_fd,
                text=True,
                bufsize=0,
                preexec_fn=os.setsid  # Create new process group
            )
            
            # Close slave fd in parent process
            os.close(slave_fd)
            
            # Read output from master fd with timeout
            output_data = []
            start_time = time.time()
            timeout = 15
            
            # Make master fd non-blocking
            flags = fcntl.fcntl(master_fd, fcntl.F_GETFL)
            fcntl.fcntl(master_fd, fcntl.F_SETFL, flags | os.O_NONBLOCK)
            
            while True:
                # Check if process has finished
                if process.poll() is not None:
                    break
                
                # Check for timeout
                if time.time() - start_time > timeout:
                    self.logger.debug("SSH pty timeout reached")
                    break
                
                try:
                    # Try to read data
                    data = os.read(master_fd, 1024)
                    if data:
                        decoded_data = data.decode('utf-8', errors='replace')
                        output_data.append(decoded_data)
                        self.logger.debug(f"SSH pty output: {decoded_data.strip()}")
                except (OSError, BlockingIOError):
                    # No data available
                    time.sleep(0.01)
                    continue
            
            # Terminate the process if still running
            if process.poll() is None:
                try:
                    os.killpg(os.getpgid(process.pid), signal.SIGTERM)
                    process.wait(timeout=2)
                except (subprocess.TimeoutExpired, ProcessLookupError):
                    try:
                        os.killpg(os.getpgid(process.pid), signal.SIGKILL)
                        process.wait(timeout=1)
                    except (subprocess.TimeoutExpired, ProcessLookupError):
                        pass
            
            # Read any remaining data
            try:
                while True:
                    data = os.read(master_fd, 1024)
                    if not data:
                        break
                    decoded_data = data.decode('utf-8', errors='replace')
                    output_data.append(decoded_data)
            except (OSError, BlockingIOError):
                pass
            
            full_output = ''.join(output_data)
            
            return {
                'success': process.returncode == 0 if process.returncode is not None else False,
                'returncode': process.returncode,
                'stdout': full_output,  # PTY combines stdout/stderr
                'stderr': '',
                'timeout_occurred': time.time() - start_time > timeout
            }
            
        finally:
            try:
                os.close(master_fd)
            except OSError:
                pass
    
    def _execute_ssh_with_script_wrapper(self) -> Dict:
        """Execute SSH using script command to capture all terminal output"""
        import tempfile
        
        # Create temporary file for script output
        with tempfile.NamedTemporaryFile(mode='w+', delete=False, suffix='.ssh_capture') as tmp_file:
            script_output_file = tmp_file.name
        
        try:
            # Build command with script wrapper
            ssh_cmd = [
                'ssh',
                '-o', 'ConnectTimeout=10',
                '-o', 'StrictHostKeyChecking=ask',
                f'{self.ssh_user}@{self.ssh_host}',
                'docker', 'version', '--format', 'json'
            ]
            
            # Use script command to capture all terminal output
            script_cmd = [
                'script', '-qec', ' '.join(f"'{arg}'" for arg in ssh_cmd), script_output_file
            ]
            
            self.logger.debug(f"Executing SSH with script wrapper: {' '.join(script_cmd)}")
            
            process = subprocess.Popen(
                script_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            
            try:
                stdout, stderr = process.communicate(timeout=15)
                timeout_occurred = False
            except subprocess.TimeoutExpired:
                process.kill()
                stdout, stderr = process.communicate()
                timeout_occurred = True
            
            # Read the script output file
            script_output = ""
            try:
                with open(script_output_file, 'r') as f:
                    script_output = f.read()
                    self.logger.debug(f"Script captured output: {script_output.strip()}")
            except Exception as e:
                self.logger.debug(f"Failed to read script output: {e}")
            
            return {
                'success': process.returncode == 0 and not timeout_occurred,
                'returncode': process.returncode,
                'stdout': script_output,
                'stderr': stderr,
                'timeout_occurred': timeout_occurred
            }
            
        finally:
            # Clean up temporary file
            try:
                os.unlink(script_output_file)
            except OSError:
                pass
    
    def _execute_ssh_with_verbose(self) -> Dict:
        """Execute SSH with maximum verbosity to capture connection details"""
        cmd = [
            'ssh',
            '-vvv',  # Maximum verbosity
            '-o', 'ConnectTimeout=10',
            '-o', 'StrictHostKeyChecking=ask',
            '-o', 'BatchMode=no',
            f'{self.ssh_user}@{self.ssh_host}',
            'docker', 'version', '--format', 'json'
        ]
        
        self.logger.debug(f"Executing SSH with verbose: {' '.join(cmd)}")
        
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            stdin=subprocess.PIPE,
            text=True
        )
        
        try:
            stdout, stderr = process.communicate(timeout=15)
            timeout_occurred = False
        except subprocess.TimeoutExpired:
            process.kill()
            stdout, stderr = process.communicate()
            timeout_occurred = True
        
        # Verbose output goes to stderr
        self.logger.debug(f"SSH verbose stderr: {stderr.strip()}")
        
        return {
            'success': process.returncode == 0 and not timeout_occurred,
            'returncode': process.returncode,
            'stdout': stdout,
            'stderr': stderr,
            'timeout_occurred': timeout_occurred
        }
    
    def _execute_ssh_fallback(self) -> Dict:
        """Fallback SSH execution method"""
        cmd = [
            'ssh',
            '-o', 'ConnectTimeout=10',
            f'{self.ssh_user}@{self.ssh_host}',
            'docker', 'version', '--format', 'json'
        ]
        
        self.logger.debug(f"Executing SSH fallback: {' '.join(cmd)}")
        
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        try:
            stdout, stderr = process.communicate(timeout=15)
            timeout_occurred = False
        except subprocess.TimeoutExpired:
            process.kill()
            stdout, stderr = process.communicate()
            timeout_occurred = True
        
        return {
            'success': process.returncode == 0 and not timeout_occurred,
            'returncode': process.returncode,
            'stdout': stdout,
            'stderr': stderr,
            'timeout_occurred': timeout_occurred
        }
    
    def _analyze_ssh_error(self, stderr: str, stdout: str, timeout_occurred: bool = False) -> str:
        """Analyze SSH error output and provide specific guidance"""
        all_output = stderr + stdout
        error_output = all_output.lower()
        
        # Log the full output for debugging
        if all_output.strip():
            self.logger.debug(f"SSH error analysis - Full output: {all_output.strip()}")
        
        if timeout_occurred:
            if 'authenticity of host' in error_output or 'can\'t be established' in error_output:
                host_key_info = self._extract_host_key_info(all_output)
                return (f"SSH timeout waiting for host key verification prompt. "
                       f"Host key verification required. {host_key_info} "
                       f"Solutions: 1) Set SSH_AUTO_POPULATE_KNOWN_HOSTS=true, "
                       f"2) Run 'ssh-keyscan {self.ssh_host} >> ~/.ssh/known_hosts', "
                       f"3) Set StrictHostKeyChecking=no (less secure). "
                       f"SSH output: {all_output.strip()}")
            
            elif 'password:' in error_output or 'passphrase' in error_output:
                return (f"SSH timeout waiting for password/passphrase prompt. "
                       f"Ensure SSH key authentication is configured properly. "
                       f"SSH output: {all_output.strip()}")
            
            elif all_output.strip():
                return (f"SSH connection timeout ({15}s) with output: {all_output.strip()}")
            else:
                return (f"SSH connection timeout ({15}s) with no output. "
                       f"Check network connectivity and SSH service availability.")
        
        # Non-timeout errors
        if 'authenticity of host' in error_output or 'host key verification failed' in error_output:
            host_key_info = self._extract_host_key_info(all_output)
            return (f"Host key verification failed. {host_key_info} "
                   f"Run 'ssh-keyscan {self.ssh_host} >> ~/.ssh/known_hosts' to add host key, "
                   f"or set SSH_AUTO_POPULATE_KNOWN_HOSTS=true. "
                   f"SSH output: {all_output.strip()}")
        
        elif 'permission denied' in error_output:
            return (f"SSH authentication failed. Check SSH key, username, or host access. "
                   f"SSH output: {all_output.strip()}")
        
        elif 'connection refused' in error_output:
            return (f"SSH connection refused. Check if SSH daemon is running on target host. "
                   f"SSH output: {all_output.strip()}")
        
        elif 'no route to host' in error_output or 'network is unreachable' in error_output:
            return (f"Network connectivity issue. Check host IP/hostname and network routing. "
                   f"SSH output: {all_output.strip()}")
        
        elif 'docker: command not found' in error_output or 'docker: not found' in error_output:
            return (f"Docker is not installed or not in PATH on remote host. "
                   f"SSH output: {all_output.strip()}")
        
        elif 'cannot connect to the docker daemon' in error_output:
            return (f"SSH successful but Docker daemon is not running on remote host. "
                   f"SSH output: {all_output.strip()}")
        
        else:
            # Generic error with full output
            return f"SSH Docker test failed. SSH output: {all_output.strip() or 'No output captured'}"
    
    def _extract_host_key_info(self, output: str) -> str:
        """Extract host key information from SSH output"""
        lines = output.split('\n')
        key_info = []
        
        for line in lines:
            line = line.strip()
            if 'key fingerprint is' in line.lower():
                key_info.append(f"Key fingerprint: {line.split('is')[-1].strip()}")
            elif line.startswith('ED25519') or line.startswith('RSA') or line.startswith('ECDSA'):
                key_info.append(f"Key type: {line}")
        
        return ' '.join(key_info) if key_info else "Host key details not captured"
    
    def disconnect(self):
        """No persistent connection to close for SSH"""
        self.status = 'disconnected'
        self.logger.info(f"Disconnected from SSH Docker host '{self.name}'")
    
    def test_connection(self) -> bool:
        """Test SSH Docker connection with enhanced error reporting"""
        try:
            # Use the enhanced _execute_ssh_docker_command method
            result = self._execute_ssh_docker_command(['version', '--format', 'json'])
            
            if result is not None:
                self.error_message = None
                return True
            else:
                # Error details already logged by _execute_ssh_docker_command
                return False
                
        except Exception as e:
            self.logger.error(f"SSH Docker connection test failed for '{self.name}': {e}")
            self.error_message = str(e)
            return False
    
    def _execute_ssh_docker_command(self, docker_args: List[str]) -> Optional[str]:
        """Execute a Docker command on remote host via SSH with enhanced error handling"""
        if self.status != 'connected':
            return None
        
        # Enhanced SSH command with connection options
        ssh_cmd = [
            'ssh',
            '-o', 'ConnectTimeout=10',
            '-o', 'ServerAliveInterval=30',
            '-o', 'ServerAliveCountMax=3',
            '-o', 'BatchMode=yes',  # Prevent interactive prompts
            f'{self.ssh_user}@{self.ssh_host}',
            'docker'
        ] + docker_args
        
        try:
            self.logger.debug(f"Executing SSH command: {' '.join(ssh_cmd)}")
            
            # Use Popen for better error handling
            process = subprocess.Popen(
                ssh_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,
                universal_newlines=True
            )
            
            try:
                stdout, stderr = process.communicate(timeout=30)
                
                if process.returncode == 0:
                    return stdout.strip()
                else:
                    # Analyze the specific error
                    error_details = self._analyze_docker_command_error(stderr, stdout, docker_args)
                    self.logger.error(f"SSH Docker command failed on '{self.name}': {error_details}")
                    
                    # Update host status if it's a connection issue
                    if self._is_connection_error(stderr):
                        self.status = 'failed'
                        self.error_message = error_details
                    
                    return None
                    
            except subprocess.TimeoutExpired:
                process.kill()
                partial_stdout, partial_stderr = process.communicate()
                
                timeout_details = f"Command timeout (30s). Partial output: {partial_stderr.strip() or partial_stdout.strip() or 'No output'}"
                self.logger.error(f"SSH Docker command timeout on '{self.name}': {timeout_details}")
                
                # Mark host as potentially failed on timeout
                self.status = 'failed'
                self.error_message = timeout_details
                return None
                
        except Exception as e:
            self.logger.error(f"SSH Docker command error on '{self.name}': {e}")
            return None
    
    def _analyze_docker_command_error(self, stderr: str, stdout: str, docker_args: List[str]) -> str:
        """Analyze Docker command error and provide specific guidance"""
        error_output = (stderr + stdout).lower()
        command = ' '.join(docker_args)
        
        if 'connection refused' in error_output or 'connection reset' in error_output:
            return f"SSH connection failed during Docker command '{command}': {stderr.strip()}"
        
        elif 'docker: command not found' in error_output:
            return f"Docker not found on remote host for command '{command}': {stderr.strip()}"
        
        elif 'cannot connect to the docker daemon' in error_output:
            return f"Docker daemon not running on remote host for command '{command}': {stderr.strip()}"
        
        elif 'permission denied' in error_output and 'docker' in error_output:
            return f"Docker permission denied on remote host for command '{command}'. User may need to be in docker group: {stderr.strip()}"
        
        elif 'no such container' in error_output:
            return f"Container not found for command '{command}': {stderr.strip()}"
        
        elif 'timeout' in error_output:
            return f"Docker command timeout for '{command}': {stderr.strip()}"
        
        else:
            return f"Docker command '{command}' failed: {stderr.strip() or stdout.strip() or 'Unknown error'}"
    
    def _is_connection_error(self, stderr: str) -> bool:
        """Check if the error indicates a connection issue that should mark host as failed"""
        error_indicators = [
            'connection refused',
            'connection reset',
            'connection timed out',
            'network is unreachable',
            'no route to host',
            'host key verification failed',
            'permission denied (publickey)',
            'connection closed by remote host'
        ]
        
        error_lower = stderr.lower()
        return any(indicator in error_lower for indicator in error_indicators)
    
    def get_containers(self) -> List[Dict]:
        """Get all containers from SSH Docker host"""
        containers = []
        
        if self.status != 'connected':
            return containers
            
        try:
            # Get container list in JSON format
            output = self._execute_ssh_docker_command([
                'ps', '--all', '--format', 'json'
            ])
            
            if output:
                # Parse each line as JSON (Docker outputs one JSON object per line)
                for line in output.strip().split('\n'):
                    if line.strip():
                        try:
                            container_json = json.loads(line)
                            container_id = container_json.get('ID', '')
                            name = container_json.get('Names', '')
                            status = container_json.get('Status', '')
                            image = container_json.get('Image', '')
                            
                            # Get detailed container info via inspect
                            inspect_output = self._execute_ssh_docker_command([
                                'inspect', container_id
                            ])
                            
                            attrs = {}
                            labels = {}
                            if inspect_output:
                                try:
                                    inspect_data = json.loads(inspect_output)
                                    if inspect_data and len(inspect_data) > 0:
                                        attrs = inspect_data[0]
                                        labels = attrs.get('Config', {}).get('Labels') or {}
                                except json.JSONDecodeError as e:
                                    self.logger.error(f"Error parsing container inspect JSON: {e}")
                            
                            containers.append({
                                'id': container_id,
                                'short_id': container_id[:12],
                                'name': name,
                                'status': status.split()[0] if status else 'unknown',
                                'labels': labels,
                                'image': image,
                                'attrs': attrs,
                                'source': 'ssh'
                            })
                            
                        except json.JSONDecodeError as e:
                            self.logger.error(f"Error parsing container JSON line: {e}")
                            
        except Exception as e:
            self.logger.error(f"Error getting containers from SSH host '{self.name}': {e}")
            
        return containers
    
    def get_container_details(self, container_id: str) -> Optional[Dict]:
        """Get detailed container information from SSH Docker host"""
        try:
            inspect_output = self._execute_ssh_docker_command([
                'inspect', container_id
            ])
            
            if inspect_output:
                inspect_data = json.loads(inspect_output)
                if inspect_data and len(inspect_data) > 0:
                    container_attrs = inspect_data[0]
                    
                    return {
                        'id': container_id,
                        'short_id': container_id[:12],
                        'name': container_attrs.get('Name', '').lstrip('/'),
                        'status': container_attrs.get('State', {}).get('Status', 'unknown'),
                        'labels': container_attrs.get('Config', {}).get('Labels') or {},
                        'image': container_attrs.get('Config', {}).get('Image', ''),
                        'attrs': container_attrs,
                        'source': 'ssh'
                    }
        except Exception as e:
            self.logger.error(f"Error getting container details for '{container_id}' from SSH host: {e}")
        
        return None
    
    def monitor_events(self, event_callback: Callable[[Dict, str], None]):
        """Monitor Docker events from SSH host using 'docker events' command"""
        if self.status != 'connected':
            return
            
        self.logger.info(f"Starting real-time event monitoring for SSH host '{self.name}'")
        
        while True:  # Reconnection loop
            try:
                # Build SSH command for Docker events
                ssh_cmd = [
                    'ssh', f'{self.ssh_user}@{self.ssh_host}', 
                    'docker', 'events', 
                    '--format', 'json',
                    '--filter', 'type=container'
                ]
                
                self.logger.debug(f"Starting SSH Docker events: {' '.join(ssh_cmd)}")
                
                # Start SSH process for Docker events
                process = subprocess.Popen(
                    ssh_cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    bufsize=1,  # Line buffered
                    universal_newlines=True
                )
                
                try:
                    # Read events line by line
                    for line in iter(process.stdout.readline, ''):
                        line = line.strip()
                        if not line:
                            continue
                        
                        try:
                            # Parse the JSON event
                            event = json.loads(line)
                            self.logger.debug(f"SSH event from '{self.name}': {event.get('Action', 'unknown')} for {event.get('id', 'unknown')[:12]}")
                            
                            # Call the event callback
                            event_callback(event, self.name)
                            
                        except json.JSONDecodeError as e:
                            self.logger.error(f"Error parsing SSH event JSON from '{self.name}': {e}")
                            
                except KeyboardInterrupt:
                    # Graceful shutdown
                    break
                    
                finally:
                    # Clean up the SSH process
                    if process.poll() is None:
                        process.terminate()
                        try:
                            process.wait(timeout=5)
                        except subprocess.TimeoutExpired:
                            process.kill()
                            process.wait()
                
                # Check return code and decide on reconnection
                returncode = process.returncode
                if returncode != 0:
                    stderr_output = process.stderr.read() if process.stderr else "No error output"
                    self.logger.warning(f"SSH Docker events process for '{self.name}' exited with code {returncode}: {stderr_output}")
                
                self.logger.info(f"SSH Docker events connection to '{self.name}' lost. Reconnecting in 5 seconds...")
                time.sleep(5)
                
            except Exception as e:
                self.logger.error(f"Error in SSH Docker events for host '{self.name}': {e}")
                self.logger.info(f"Retrying SSH connection to '{self.name}' in 10 seconds...")
                time.sleep(10)
    
    def get_host_ip(self) -> Optional[str]:
        """Get SSH host IP address"""
        # For SSH hosts, clean the host IP/hostname and resolve if needed
        clean_host = self.ssh_host.strip().split('#')[0].strip()  # Remove comments
        
        try:
            socket.inet_aton(clean_host)  # Test if it's a valid IP
            self.logger.debug(f"Using direct IP for SSH host '{self.name}': {clean_host}")
            return clean_host
        except socket.error:
            # It's a hostname, resolve it
            try:
                resolved_ip = socket.gethostbyname(clean_host)
                self.logger.debug(f"Resolved SSH hostname '{clean_host}' to IP: {resolved_ip}")
                return resolved_ip
            except Exception as e:
                self.logger.warning(f"Could not resolve SSH hostname '{clean_host}': {e}")
                return None


class DockerHostFactory:
    """Factory for creating DockerHost instances"""
    
    @staticmethod
    def create_host(name: str, host_config: Dict, config: Dict, logger: logging.Logger) -> DockerHost:
        """Create appropriate DockerHost instance based on configuration"""
        host_type = host_config.get('type', 'local')
        
        if host_type == 'local':
            return LocalDockerHost(name, config, logger)
        elif host_type == 'ssh':
            return SSHDockerHost(name, config, logger)
        else:
            raise ValueError(f"Unknown Docker host type: {host_type}")