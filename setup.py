#!/usr/bin/env python3
"""
Enhanced Docker Monitor - Setup Script

This setup script creates a proper Python package for the Enhanced Docker Monitor
with all dependencies, entry points, and metadata properly configured.
"""

import os
import sys
from pathlib import Path
from setuptools import setup, find_packages

# Ensure we can import the package for metadata
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Read version and metadata from package
try:
    from docker_monitor import __version__, __author__, __description__, PACKAGE_INFO
except ImportError:
    # Fallback if package can't be imported
    __version__ = "2.5.0"
    __author__ = "Docker Monitor Team"
    __description__ = "Production-ready Docker container monitoring with enhanced health tracking"
    PACKAGE_INFO = {}

# Read long description from README
def read_long_description():
    """Read long description from README file"""
    readme_file = Path(__file__).parent / "README.md"
    if readme_file.exists():
        with open(readme_file, "r", encoding="utf-8") as f:
            return f.read()
    return __description__

# Core dependencies
INSTALL_REQUIRES = [
    "docker>=6.0.0",
    "fastapi>=0.104.0",
    "uvicorn[standard]>=0.24.0",
    "pydantic>=2.0.0",
    "requests>=2.25.0",
]

# Optional dependencies
EXTRAS_REQUIRE = {
    "ssh": [
        "paramiko>=2.7.0",
    ],
    "dev": [
        "pytest>=6.0.0",
        "pytest-cov>=2.10.0",
        "black>=21.0.0",
        "flake8>=3.8.0",
        "mypy>=0.800",
        "pre-commit>=2.10.0",
    ],
    "docs": [
        "sphinx>=3.5.0",
        "sphinx-rtd-theme>=0.5.0",
        "myst-parser>=0.13.0",
    ],
    "monitoring": [
        "prometheus-client>=0.8.0",
        "psutil>=5.7.0",
    ],
}

# Add 'all' extra that includes everything
EXTRAS_REQUIRE["all"] = [
    dep for extra_deps in EXTRAS_REQUIRE.values() 
    for dep in extra_deps
]

def main():
    setup(
        name="enhanced-docker-monitor",
        version=__version__,
        author=__author__,
        author_email="docker-monitor@example.com",
        description=__description__,
        long_description=read_long_description(),
        long_description_content_type="text/markdown",
        url="https://github.com/snadboy/docker_monitor",
        project_urls={
            "Bug Reports": "https://github.com/snadboy/docker_monitor/issues",
            "Source": "https://github.com/snadboy/docker_monitor",
            "Documentation": "https://github.com/snadboy/docker_monitor/blob/main/README.md",
        },
        packages=find_packages(),
        classifiers=[
            "Development Status :: 4 - Beta",
            "Intended Audience :: Developers",
            "Intended Audience :: System Administrators",
            "License :: OSI Approved :: MIT License",
            "Operating System :: OS Independent",
            "Programming Language :: Python :: 3",
            "Programming Language :: Python :: 3.7",
            "Programming Language :: Python :: 3.8",
            "Programming Language :: Python :: 3.9",
            "Programming Language :: Python :: 3.10",
            "Programming Language :: Python :: 3.11",
            "Programming Language :: Python :: 3.12",
            "Topic :: Software Development :: Libraries :: Python Modules",
            "Topic :: System :: Monitoring",
            "Topic :: System :: Systems Administration",
        ],
        python_requires=">=3.7",
        install_requires=INSTALL_REQUIRES,
        extras_require=EXTRAS_REQUIRE,
        entry_points={
            "console_scripts": [
                "docker-monitor=docker_monitor.main:main",
                "docker-monitor-config=docker_monitor.config:print_config_cli",
            ],
        },
        keywords=[
            "docker",
            "monitoring",
            "containers",
            "microservices",
            "devops",
            "infrastructure",
            "api",
            "fastapi",
            "kubernetes",
            "docker-compose",
        ],
        include_package_data=True,
        zip_safe=False,
    )

if __name__ == "__main__":
    main()