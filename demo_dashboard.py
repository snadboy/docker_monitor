#!/usr/bin/env python3
"""
Docker Monitor Dashboard Demo

Run this script to see the Docker Monitor dashboard with sample data.
Perfect for testing the interface locally without full monitoring setup.
"""

import uvicorn
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from datetime import datetime

app = FastAPI(
    title="Docker Monitor Dashboard - Demo",
    description="Docker Monitor Dashboard with sample data",
    version="2.5.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# Sample data for demonstration
sample_health = {
    "status": "healthy",
    "timestamp": datetime.now().isoformat(),
    "uptime_seconds": 3600,
    "docker_hosts": {
        "total": 2,
        "connected": 2,
        "failed": 0,
        "status_details": {
            "local": "healthy",
            "remote-server": "healthy"
        }
    },
    "monitored_containers": 3,
    "caddy": {"enabled": True, "available": True, "managed_routes": 2},
    "version": "2.5.0"
}

sample_containers = {
    "containers": [
        {
            "name": "web-frontend",
            "short_id": "abc123def",
            "status": "running",
            "host_ip": "192.168.1.100",
            "docker_host_name": "local",
            "snadboy_labels": {
                "snadboy.revp.domain": "app.example.com",
                "snadboy.revp.port": "80",
                "snadboy.revp.ssl": "true"
            }
        },
        {
            "name": "api-backend", 
            "short_id": "def456ghi",
            "status": "running",
            "host_ip": "192.168.1.101",
            "docker_host_name": "remote-server",
            "snadboy_labels": {
                "snadboy.revp.domain": "api.example.com",
                "snadboy.revp.port": "8080",
                "snadboy.revp.path": "/api/v1"
            }
        },
        {
            "name": "database",
            "short_id": "ghi789jkl", 
            "status": "running",
            "host_ip": "192.168.1.100",
            "docker_host_name": "local",
            "snadboy_labels": {
                "snadboy.db.port": "5432",
                "snadboy.db.name": "appdb"
            }
        }
    ],
    "count": 3
}

@app.get("/health")
def health():
    return sample_health

@app.get("/containers")
def containers():
    return sample_containers

@app.get("/errors")
def errors():
    return {"host_errors": {}, "error_count": 0, "timestamp": datetime.now().isoformat()}

@app.get("/services/schema")
def services_schema():
    return {
        "implemented_services": {
            "revp": {
                "description": "Reverse Proxy Service (Caddy)",
                "required_properties": ["domain", "port"],
                "status": "implemented"
            }
        },
        "service_count": 1
    }

@app.get("/", response_class=HTMLResponse)
@app.get("/dashboard", response_class=HTMLResponse)
def dashboard():
    """Load the full dashboard HTML from the actual docker_monitor package"""
    try:
        # Try to import the real dashboard HTML
        from docker_monitor.api_server import APIServer
        
        # Create a minimal mock instance to get the HTML
        mock_config = {"api_base_url": "http://localhost:8090"}
        api_server = APIServer({}, None, None, mock_config, None)
        return api_server._get_dashboard_html()
    except ImportError:
        # Fallback simple dashboard if package not available
        return '''
        <!DOCTYPE html>
        <html><head><title>Docker Monitor Demo</title></head>
        <body style="font-family: Arial, sans-serif; margin: 2rem;">
        <h1>🐳 Docker Monitor Dashboard Demo</h1>
        <p>This is a simplified demo. Install the full package to see the complete dashboard.</p>
        <p><strong>API Endpoints:</strong></p>
        <ul>
        <li><a href="/docs">API Documentation</a></li>
        <li><a href="/health">Health Status</a></li>
        <li><a href="/containers">Containers</a></li>
        </ul>
        </body></html>
        '''

@app.get("/demo-info")
def demo_info():
    return {
        "message": "Docker Monitor Dashboard Demo",
        "features": [
            "Full dashboard UI (if package installed)",
            "Sample container data",
            "All API endpoints functional",
            "FastAPI automatic documentation"
        ],
        "endpoints": {
            "dashboard": "/dashboard", 
            "api_docs": "/docs",
            "health": "/health",
            "containers": "/containers"
        }
    }

if __name__ == "__main__":
    port = 8090
    print("🚀 Starting Docker Monitor Dashboard Demo...")
    print(f"📱 Dashboard: http://localhost:{port}/dashboard")
    print(f"📚 API Docs:  http://localhost:{port}/docs")
    print(f"ℹ️  Demo Info: http://localhost:{port}/demo-info")
    print("\nPress Ctrl+C to stop")
    
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="info")