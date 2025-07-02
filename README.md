# Enhanced Docker Monitor

[![Python Version](https://img.shields.io/badge/python-3.7+-blue.svg)](https://python.org)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Docker](https://img.shields.io/badge/docker-supported-blue.svg)](https://docker.com)

A production-ready Docker container monitoring system with persistent error tracking, intelligent connection recovery, Caddy reverse proxy integration, and service registry validation.

## 🚀 Features

- **Multi-Host Docker Monitoring**: Monitor containers across local and SSH-connected Docker hosts
- **Persistent Error Tracking**: Track connection failures with exponential backoff recovery
- **Health Monitoring**: Kubernetes-style health checks (`/health`, `/healthz`, `/readiness`)
- **Caddy Integration**: Automatic reverse proxy configuration via Caddy Admin API
- **Service Registry**: Extensible service type validation with schema support
- **Real-time Events**: Live container event monitoring and processing
- **REST API**: Comprehensive API for container discovery and debugging
- **Web Dashboard**: Interactive dashboard with light/dark themes
- **SSH Support**: Secure monitoring of remote Docker hosts via SSH
- **Connection Recovery**: Automatic reconnection to failed hosts

## 📦 Installation

### From Source

```bash
# Clone the repository
git clone https://github.com/your-org/enhanced-docker-monitor.git
cd enhanced-docker-monitor

# Install the package
pip install -e .

# Or install with optional dependencies
pip install -e ".[all]"  # All optional features
pip install -e ".[ssh]"  # SSH support only
pip install -e ".[dev]"  # Development tools
```

### Using pip (when published)

```bash
pip install enhanced-docker-monitor
```

## 🏗️ Architecture

The Enhanced Docker Monitor is built with a modular architecture for maintainability and extensibility:

```
docker_monitor/
├── __init__.py          # Package initialization and public API
├── main.py              # Application entry point
├── config.py            # Configuration loading and validation
├── schemas.py           # Service registry and validation schemas
├── docker_hosts.py      # Docker host abstractions (Local/SSH)
├── managers.py          # Host manager and SSH setup
├── processors.py        # Container processing and Caddy management
├── api_server.py        # Flask REST API server
└── monitor.py           # Main orchestrator
```

### Core Components

- **DockerMonitor**: Main orchestrator that coordinates all components
- **DockerHostManager**: Manages multiple Docker hosts with error tracking
- **ContainerProcessor**: Processes containers and extracts snadboy labels
- **CaddyManager**: Handles Caddy reverse proxy configuration
- **APIServer**: Provides REST API and web dashboard
- **SSHSetupManager**: Manages SSH configuration for remote hosts

## 🎯 Quick Start

### Basic Usage

```python
from docker_monitor import create_monitor_from_config

# Create monitor with default configuration
monitor = create_monitor_from_config()

# Start monitoring
monitor.start()
```

### Custom Configuration

```python
from docker_monitor import DockerMonitor, load_config

# Load and customize configuration
config = load_config()
config.update({
    'log_level': 'DEBUG',
    'api_port': 9090,
    'caddy_enabled': True,
    'caddy_admin_url': 'http://caddy:2019'
})

# Create and start monitor
monitor = DockerMonitor(config)
monitor.start()
```

### Command Line Usage

```bash
# Start with default configuration
docker-monitor

# Enable debug logging and Caddy integration
docker-monitor --log-level DEBUG --caddy-enabled

# Monitor SSH hosts
docker-monitor --docker-hosts-ssh "192.168.1.10 192.168.1.11"

# Custom API port and Caddy URL
docker-monitor --api-port 9090 --caddy-admin-url http://caddy:2019

# Check configuration
docker-monitor --config-check

# View configuration summary
docker-monitor --config-summary
```

## ⚙️ Configuration

### Environment Variables

| Variable             | Default                 | Description                                 |
| -------------------- | ----------------------- | ------------------------------------------- |
| `LOG_LEVEL`          | `INFO`                  | Logging level (DEBUG, INFO, WARNING, ERROR) |
| `API_PORT`           | `8080`                  | API server port                             |
| `DOCKER_HOSTS_LOCAL` | `true`                  | Enable local Docker host monitoring         |
| `DOCKER_HOSTS_SSH`   | -                       | Space-separated SSH host IPs                |
| `SSH_USER`           | `root`                  | SSH username for remote hosts               |
| `CADDY_ENABLED`      | `false`                 | Enable Caddy reverse proxy integration      |
| `CADDY_ADMIN_URL`    | `http://localhost:2019` | Caddy Admin API URL                         |
| `LABEL_PREFIX`       | `snadboy.`              | Container label prefix to monitor           |

### Service Labels

The monitor uses container labels to configure services:

```yaml
# Basic reverse proxy service
labels:
  snadboy.revp.domain: "app.example.com"
  snadboy.revp.port: "80"

# Advanced configuration
labels:
  snadboy.revp.domain: "app.example.com"
  snadboy.revp.port: "80"
  snadboy.revp.path: "/app"
  snadboy.revp.scheme: "https"
  snadboy.revp.websocket: "true"
  snadboy.revp.ssl_force: "true"
  snadboy.revp.middleware: "auth,compress"

# Multiple services per container
labels:
  snadboy.web.domain: "app.example.com"
  snadboy.web.port: "80"
  snadboy.api.domain: "api.example.com"
  snadboy.api.port: "8080"
```

## 🐳 Docker Deployment

### Docker Compose

```yaml
version: '3.8'

services:
  caddy:
    image: caddy:2
    ports:
      - "80:80"
      - "443:443" 
      - "2019:2019"  # Admin API
    volumes:
      - caddy_data:/data
      - caddy_config:/config

  docker-monitor:
    image: enhanced-docker-monitor
    environment:
      - LOG_LEVEL=INFO
      - CADDY_ENABLED=true
      - CADDY_ADMIN_URL=http://caddy:2019
      - DOCKER_HOSTS_SSH=192.168.1.10 192.168.1.11
    ports:
      - "8080:8080"
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock:ro
      - ./ssh:/home/monitor/.ssh:ro
      - ./data:/app/data
      - ./logs:/app/logs
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8080/healthz"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 40s

volumes:
  caddy_data:
  caddy_config:
```

### SSH Setup for Remote Hosts

```bash
# Generate SSH key
ssh-keygen -t ed25519 -f ./ssh/ssh_private_key -N ""

# Copy public key to remote hosts
for host in 192.168.1.10 192.168.1.11; do
  ssh-copy-id -i ./ssh/ssh_private_key.pub root@$host
done

# Set proper permissions
chmod 600 ./ssh/ssh_private_key
chmod 644 ./ssh/ssh_private_key.pub
```

## 🌐 API Endpoints

### Health Monitoring

- `GET /health` - Detailed health status with error information
- `GET /healthz` - Kubernetes-style health check
- `GET /readiness` - Readiness probe for orchestration
- `GET /errors` - Detailed error analysis and recovery status

### Container Management

- `GET /containers` - List all monitored containers
- `GET /containers/{id}` - Get specific container details
- `GET /containers/summary` - Container summary by host

### Service Discovery

- `GET /services/schema` - Supported service types and schemas
- `GET /labels` - All snadboy labels from containers
- `GET /caddy` - Container info for Caddy reverse proxy
- `GET /ips` - Container IP addresses and networking

### Debugging

- `GET /debug` - Complete system state for troubleshooting
- `GET /dashboard` - Interactive web dashboard

## 🔧 Development

### Setting Up Development Environment

```bash
# Clone the repository
git clone https://github.com/your-org/enhanced-docker-monitor.git
cd enhanced-docker-monitor

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Linux/Mac
# or
venv\Scripts\activate  # Windows

# Install in development mode with all extras
pip install -e ".[dev]"

# Install pre-commit hooks
pre-commit install
```

### Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=docker_monitor

# Run specific test file
pytest tests/test_monitor.py
```

### Code Formatting

```bash
# Format code with black
black docker_monitor/

# Check with flake8
flake8 docker_monitor/

# Type checking with mypy
mypy docker_monitor/
```

### Module Structure

Each module has a specific responsibility:

```python
# Import specific components
from docker_monitor.monitor import DockerMonitor
from docker_monitor.managers import DockerHostManager
from docker_monitor.processors import ContainerProcessor, CaddyManager
from docker_monitor.api_server import APIServer
from docker_monitor.docker_hosts import LocalDockerHost, SSHDockerHost

# Or use the convenience function
from docker_monitor import create_monitor_from_config
```

## 📊 Monitoring Integration

### Kubernetes

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: docker-monitor
spec:
  template:
    spec:
      containers:
      - name: docker-monitor
        image: enhanced-docker-monitor
        ports:
        - containerPort: 8080
        livenessProbe:
          httpGet:
            path: /healthz
            port: 8080
          initialDelaySeconds: 30
          periodSeconds: 30
        readinessProbe:
          httpGet:
            path: /readiness
            port: 8080
          initialDelaySeconds: 5
          periodSeconds: 10
```

### Prometheus Monitoring

```yaml
# Prometheus scrape config
scrape_configs:
- job_name: 'docker-monitor'
  static_configs:
  - targets: ['docker-monitor:8080']
  metrics_path: '/metrics'  # If prometheus integration is enabled
```

## 🔍 Troubleshooting

### Common Issues

1. **SSH Connection Failures**
   ```bash
   # Check SSH connectivity
   ssh -o ConnectTimeout=10 root@192.168.1.10 docker version
   
   # View detailed SSH errors
   curl http://localhost:8080/errors
   ```

2. **Caddy Integration Issues**
   ```bash
   # Verify Caddy Admin API
   curl http://localhost:2019/config/
   
   # Check Docker networking
   docker network ls
   ```

3. **Container Detection Issues**
   ```bash
   # Debug container discovery
   curl http://localhost:8080/debug
   
   # Check label formatting
   docker inspect container_name | jq '.Config.Labels'
   ```

### Debug Endpoints

- `/debug` - Complete system state
- `/errors` - Host connection errors
- `/health` - Overall system health
- `/caddy/status` - Caddy integration status

## 📝 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 📚 Documentation

- [API Reference](docs/api.md)
- [Configuration Guide](docs/configuration.md)
- [Deployment Guide](docs/deployment.md)
- [Development Guide](docs/development.md)

## 🙏 Acknowledgments

- [Docker SDK for Python](https://docker-py.readthedocs.io/)
- [Flask Web Framework](https://flask.palletsprojects.com/)
- [Caddy Web Server](https://caddyserver.com/)
- [Requests HTTP Library](https://requests.readthedocs.io/)