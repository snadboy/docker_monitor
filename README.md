# Enhanced Docker Monitor

A production-ready Docker container monitoring system with persistent error tracking, intelligent connection recovery, Caddy reverse proxy integration, and comprehensive FastAPI-based REST API.

## Features

- **Multi-host Docker monitoring** (local + SSH remote hosts)
- **Persistent error tracking** with exponential backoff recovery
- **FastAPI REST API** with automatic documentation
- **Kubernetes-style health checks** (`/health`, `/healthz`, `/readiness`)
- **Caddy reverse proxy integration** with automatic route management
- **Service registry** with schema validation
- **Interactive web dashboard** with dark/light themes
- **Real-time container event monitoring**
- **SSH host management** with automatic key setup
- **Background connection recovery**

## Installation

### Using pip

```bash
pip install enhanced-docker-monitor
```

### Development Installation

```bash
git clone https://github.com/snadboy/docker_monitor.git
cd docker_monitor
pip install -e ".[dev]"
```

## Quick Start

### Basic Usage

```bash
# Start monitoring with API server
docker-monitor --api-port 8080

# Monitor with debug logging
docker-monitor --log-level DEBUG

# Show configuration
docker-monitor-config
```

### Access the Dashboard

Once running, access:
- **Dashboard**: http://localhost:8080/dashboard
- **API Documentation**: http://localhost:8080/docs
- **Health Check**: http://localhost:8080/health

## Configuration

The monitor can be configured via environment variables:

```bash
export DOCKER_MONITOR_API_PORT=8080
export DOCKER_MONITOR_LOG_LEVEL=INFO
export DOCKER_MONITOR_LABEL_PREFIX=snadboy.
export DOCKER_MONITOR_CADDY_ENABLED=true
export DOCKER_MONITOR_CADDY_ADMIN_URL=http://localhost:2019
```

## Project Structure

```
docker_monitor/
├── __init__.py          # Package initialization and exports
├── main.py              # Application entry point and CLI
├── monitor.py           # Main orchestrator
├── config.py            # Configuration management
├── api_server.py        # FastAPI REST API server
├── managers.py          # Host and SSH management
├── processors.py        # Container processing and Caddy management
├── docker_hosts.py      # Docker host abstractions (Local/SSH)
└── schemas.py           # Service registry and validation schemas
```

## Core Components

### DockerMonitor
Main orchestrator that coordinates all monitoring operations, manages container discovery, and handles connection recovery.

### FastAPI REST API
Comprehensive REST API with automatic documentation providing:
- Container monitoring endpoints
- Health status and diagnostics
- Service registry management
- Caddy integration status
- Interactive web dashboard

### Multi-Host Support
Abstract `DockerHost` pattern with implementations:
- `LocalDockerHost` - Direct Docker socket access
- `SSHDockerHost` - Remote Docker hosts via SSH

### Service Discovery
Extracts container labels with configurable prefix (default: `snadboy.`) for automatic service configuration and reverse proxy setup.

## API Endpoints

### Health Monitoring
- `GET /health` - Detailed health status with error information
- `GET /healthz` - Kubernetes-style health check
- `GET /readiness` - Readiness probe for orchestration
- `GET /errors` - Connection error analysis and recovery status

### Container Management
- `GET /containers` - List all monitored containers
- `GET /containers/{id}` - Get specific container details
- `GET /containers/summary` - Container summary by host

### Service Configuration
- `GET /services/schema` - Supported service types and validation
- `GET /labels` - All snadboy labels from containers

### Integration
- `GET /caddy` - Container info for Caddy reverse proxy
- `GET /caddy/status` - Caddy integration status
- `GET /ips` - Container IP address mapping

### Documentation
- `GET /dashboard` - Interactive web dashboard
- `GET /docs` - Swagger/OpenAPI documentation
- `GET /debug` - System debugging information

## Service Labels

Configure services using container labels:

### Reverse Proxy (Caddy)
```yaml
labels:
  snadboy.revp.domain: "app.example.com"
  snadboy.revp.port: "80"
  snadboy.revp.path: "/"
  snadboy.revp.ssl: "true"
```

### Planned Service Types
- `snadboy.api.*` - API service configuration
- `snadboy.web.*` - Web service configuration  
- `snadboy.db.*` - Database service configuration
- `snadboy.metrics.*` - Metrics service configuration

## Architecture

### Error Tracking
Persistent error tracking with exponential backoff for failed host connections, automatic recovery attempts, and detailed error reporting.

### Configuration
Environment-driven configuration with CLI overrides, automatic Docker vs local environment detection, and comprehensive validation.

### Health Monitoring
Kubernetes-style health endpoints suitable for container orchestration, with detailed system status and connection monitoring.

### Signal Handling
Graceful shutdown with proper cleanup of connections, background tasks, and monitoring threads.

## Development

### Running Tests
```bash
pytest
```

### Code Quality
```bash
black docker_monitor/          # Code formatting
flake8 docker_monitor/         # Linting  
mypy docker_monitor/           # Type checking
```

### Development Server
```bash
python -m docker_monitor.main --api-port 8080 --log-level DEBUG
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests
5. Submit a pull request

## License

MIT License - see LICENSE file for details.

## Support

- **Issues**: https://github.com/snadboy/docker_monitor/issues
- **Documentation**: https://github.com/snadboy/docker_monitor/blob/main/README.md
- **Source Code**: https://github.com/snadboy/docker_monitor