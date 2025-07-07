#!/usr/bin/env python3
"""
Simple test script to run just the API server and show the dashboard
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import uvicorn
from fastapi import FastAPI
from fastapi.responses import HTMLResponse

# Create a minimal FastAPI app just for the dashboard
app = FastAPI(title="Docker Monitor Dashboard Test")

@app.get("/", response_class=HTMLResponse)
@app.get("/dashboard", response_class=HTMLResponse)
def dashboard():
    """Simple dashboard for testing"""
    return '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Docker Monitor Dashboard - Test</title>
    <style>
        :root {
            --bg-primary: #ffffff;
            --bg-secondary: #f8f9fa;
            --bg-tertiary: #e9ecef;
            --text-primary: #212529;
            --text-secondary: #6c757d;
            --text-muted: #adb5bd;
            --border-color: #dee2e6;
            --success-color: #28a745;
            --warning-color: #ffc107;
            --danger-color: #dc3545;
            --info-color: #17a2b8;
            --accent-color: #007bff;
            --shadow: 0 0.125rem 0.25rem rgba(0, 0, 0, 0.075);
        }

        [data-theme="dark"] {
            --bg-primary: #1a1a1a;
            --bg-secondary: #2d2d2d;
            --bg-tertiary: #404040;
            --text-primary: #ffffff;
            --text-secondary: #b0b0b0;
            --text-muted: #808080;
            --border-color: #404040;
            --success-color: #40c757;
            --warning-color: #ffcd39;
            --danger-color: #f86c6b;
            --accent-color: #375a7f;
        }

        * { margin: 0; padding: 0; box-sizing: border-box; }

        body {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            background-color: var(--bg-primary);
            color: var(--text-primary);
            line-height: 1.6;
            transition: all 0.3s ease;
        }

        .header {
            background: var(--bg-secondary);
            border-bottom: 1px solid var(--border-color);
            padding: 1rem 2rem;
            display: flex;
            justify-content: space-between;
            align-items: center;
            box-shadow: var(--shadow);
        }

        .header h1 {
            font-size: 1.5rem;
            font-weight: 600;
            color: var(--text-primary);
        }

        .theme-toggle {
            background: var(--accent-color);
            color: white;
            border: none;
            padding: 0.5rem 1rem;
            border-radius: 0.375rem;
            cursor: pointer;
            font-size: 0.875rem;
            transition: all 0.2s ease;
        }

        .theme-toggle:hover {
            filter: brightness(110%);
        }

        .container {
            max-width: 1200px;
            margin: 0 auto;
            padding: 2rem;
        }

        .info-card {
            background: var(--bg-secondary);
            border: 1px solid var(--border-color);
            border-radius: 0.5rem;
            padding: 2rem;
            margin-bottom: 2rem;
            box-shadow: var(--shadow);
        }

        .info-card h2 {
            color: var(--accent-color);
            margin-bottom: 1rem;
        }

        .info-card p {
            margin-bottom: 0.5rem;
            color: var(--text-secondary);
        }

        .feature-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 1.5rem;
            margin-top: 2rem;
        }

        .feature-card {
            background: var(--bg-secondary);
            border: 1px solid var(--border-color);
            border-radius: 0.5rem;
            padding: 1.5rem;
            box-shadow: var(--shadow);
        }

        .feature-card h3 {
            color: var(--accent-color);
            margin-bottom: 0.5rem;
        }

        .status-badge {
            display: inline-block;
            padding: 0.25rem 0.75rem;
            border-radius: 9999px;
            font-size: 0.75rem;
            font-weight: 500;
            background: rgba(40, 167, 69, 0.1);
            color: var(--success-color);
        }
    </style>
</head>
<body>
    <div class="header">
        <h1>🐳 Docker Monitor Dashboard - Test Mode</h1>
        <button class="theme-toggle" onclick="toggleTheme()">🌙 Dark</button>
    </div>

    <div class="container">
        <div class="info-card">
            <h2>Dashboard Test Mode</h2>
            <p>This is a simplified version of the Docker Monitor dashboard running in test mode.</p>
            <p><span class="status-badge">FastAPI Active</span> The full dashboard includes real-time container monitoring, health checks, and system status.</p>
            <p><strong>Full Dashboard Features:</strong></p>
            <ul style="margin-left: 1.5rem; margin-top: 0.5rem;">
                <li>Real-time container monitoring with auto-refresh</li>
                <li>Multi-host Docker environment support</li>
                <li>Health status tracking and error recovery</li>
                <li>Caddy reverse proxy integration</li>
                <li>Service registry with schema validation</li>
                <li>Interactive debugging tools</li>
            </ul>
        </div>

        <div class="feature-grid">
            <div class="feature-card">
                <h3>🔄 Real-time Monitoring</h3>
                <p>Auto-refreshing dashboard that monitors Docker containers across multiple hosts with persistent error tracking.</p>
            </div>
            
            <div class="feature-card">
                <h3>📊 Health Tracking</h3>
                <p>Kubernetes-style health checks with detailed system status and connection recovery monitoring.</p>
            </div>
            
            <div class="feature-card">
                <h3>🎨 Modern UI</h3>
                <p>Responsive design with dark/light theme toggle and mobile-friendly interface.</p>
            </div>
            
            <div class="feature-card">
                <h3>🔧 API Integration</h3>
                <p>Full REST API with automatic documentation at /docs and comprehensive endpoint coverage.</p>
            </div>
        </div>
    </div>

    <script>
        let currentTheme = localStorage.getItem('theme') || 'light';
        document.documentElement.setAttribute('data-theme', currentTheme);
        updateThemeButton();

        function toggleTheme() {
            currentTheme = currentTheme === 'light' ? 'dark' : 'light';
            document.documentElement.setAttribute('data-theme', currentTheme);
            localStorage.setItem('theme', currentTheme);
            updateThemeButton();
        }

        function updateThemeButton() {
            const button = document.querySelector('.theme-toggle');
            button.textContent = currentTheme === 'light' ? '🌙 Dark' : '☀️ Light';
        }
    </script>
</body>
</html>
    '''

@app.get("/docs-info")
def docs_info():
    """API documentation information"""
    return {
        "message": "FastAPI automatic documentation",
        "docs_url": "/docs",
        "redoc_url": "/redoc",
        "features": [
            "Interactive API documentation",
            "Request/response validation",
            "Automatic OpenAPI schema generation",
            "Type-safe endpoints with Pydantic models"
        ]
    }

if __name__ == "__main__":
    port = 8085
    print("🚀 Starting Docker Monitor Dashboard Test Server...")
    print(f"📱 Dashboard: http://localhost:{port}/dashboard")
    print(f"📚 API Docs: http://localhost:{port}/docs")
    print(f"🔄 Auto-refresh: http://localhost:{port}/docs-info")
    print("\nPress Ctrl+C to stop")
    
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="info")