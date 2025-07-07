# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Development Environment

**Virtual Environment**: Use `/home/snadboy/venv` (already configured with Python 3.12.3)
```bash
source /home/snadboy/venv/bin/activate
```

**Install Development Dependencies**:
```bash
pip install -e ".[dev]"  # Installs with development extras (pytest, black, flake8, mypy)
```

## Common Commands

**Run the Monitor (CLI)**:
```bash
python -m docker_monitor.main --log-level debug
# Or using entry point: docker-monitor --log-level debug
```

**Start API Server**:
```bash
python -m docker_monitor.main --api-port 8080
```

**Configuration Helper**:
```bash
docker-monitor-config  # Shows current configuration
```

**Code Quality**:
```bash
black docker_monitor/          # Code formatting
flake8 docker_monitor/         # Linting
mypy docker_monitor/           # Type checking
```

**Testing**:
```bash
pytest                         # Run tests (when implemented)
```

## Architecture Overview

This is a **production-ready Docker container monitoring system** with both CLI and web service capabilities.

### Core Components

**Main Orchestrator**: `DockerMonitor` class in `monitor.py` coordinates all operations

**Multi-Host Support**: Abstract `DockerHost` pattern with implementations:
- `LocalDockerHost` - Direct Docker socket access
- `SSHDockerHost` - Remote Docker hosts via SSH

**Service Discovery**: Extracts container labels with `snadboy.` prefix for service configuration

**Managers**:
- `DockerHostManager` - Host management with error tracking/recovery
- `CaddyManager` - Reverse proxy configuration via Caddy Admin API

**API Layer**: FastAPI REST API (`api_server.py`) with comprehensive endpoints for monitoring and debugging. FastAPI provides automatic validation, async support, and built-in API documentation at `/docs`.

### Key Patterns

**Service Registry**: Extensible schema system in `schemas.py` for validating service types (currently supports 'revp' for reverse proxy)

**Error Tracking**: Persistent error tracking with exponential backoff for failed host connections

**Configuration**: Environment-driven config (`config.py`) with CLI overrides and Docker environment detection

## Important Implementation Details

**Container Processing**: The `ContainerProcessor` extracts labels, validates against schemas, and generates configurations

**Health Monitoring**: Kubernetes-style endpoints (`/health`, `/healthz`, `/readiness`) for container orchestration

**SSH Authentication**: Automatic SSH key setup and host key management for remote Docker hosts

**Signal Handling**: Graceful shutdown with proper cleanup of connections and background tasks

## Configuration

**Environment Variables**: All configuration via env vars with `DOCKER_MONITOR_` prefix
**Label Prefix**: Default `snadboy.` for container service discovery
**Paths**: Auto-detects Docker vs local environment for config/log paths

## API Endpoints

Key endpoints for integration:
- `GET /containers` - All monitored containers
- `GET /services/schema` - Supported service types
- `GET /health` - Detailed system health
- `GET /errors` - Error analysis and recovery status

## Package Structure

This is now a proper Python package with:
- `docker_monitor/` - Main package directory
- `setup.py` - Package installation script
- `requirements.txt` - Dependencies
- Console entry points: `docker-monitor` and `docker-monitor-config`

## Dashboard

The FastAPI server includes a comprehensive web dashboard at `/dashboard` with:
- Multi-tab interface (Overview, Containers, Health, Errors, Services)
- Dark/light theme toggle
- Real-time data updates
- Responsive mobile-friendly design
- Interactive container monitoring