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
    __version__ = "2.5.0-enhanced-health"
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

# Read requirements from requirements.txt
def read_requirements(filename="requirements.txt"):
    """Read requirements from requirements file"""
    req_file = Path(__file__).parent / filename
    if req_file.exists():
        with open(req_file, "r", encoding="utf-8") as f:
            return [line.strip() for line in f if line.strip() and not line.startswith("#")]
    return []

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

# Try to read from requirements.txt if it exists
requirements_file_deps = read_requirements()
if requirements_file_deps:
    INSTALL_REQUIRES = requirements_file_deps

# Package data
PACKAGE_DATA = {
    "docker_monitor": [
        "*.md",
        "*.txt",
        "*.yml",
        "*.yaml",
        "templates/*.html",
        "static/*",
    ]
}

# Console scripts entry points
CONSOLE_SCRIPTS = [
    "docker-monitor=docker_monitor.main:main",
    "docker-monitor-config=docker_monitor.config:main",
]

# Python version requirement
PYTHON_REQUIRES = ">=3.7"

# Classifiers for PyPI
CLASSIFIERS = [
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
    "Topic :: System :: Monitoring",
    "Topic :: System :: Systems Administration",
    "Topic :: Software Development :: Libraries :: Python Modules",
    "Environment :: Console",
    "Environment :: Web Environment",
]

# Keywords for PyPI
KEYWORDS = [
    "docker",
    "container",
    "monitoring",
    "health-check",
    "ssh",
    "caddy",
    "reverse-proxy",
    "microservices",
    "devops",
    "infrastructure",
    "api",
    "fastapi",
    "kubernetes",
    "docker-compose",
]

def validate_setup():
    """Validate setup configuration before building"""
    errors = []
    
    # Check required files
    required_files = ["docker_monitor/__init__.py"]
    for file_path in required_files:
        if not Path(file_path).exists():
            errors.append(f"Required file missing: {file_path}")
    
    # Check Python version
    if sys.version_info < (3, 7):
        errors.append(f"Python 3.7+ required, found {sys.version_info.major}.{sys.version_info.minor}")
    
    # Check package structure
    if not Path("docker_monitor").is_dir():
        errors.append("Package directory 'docker_monitor' not found")
    
    if errors:
        print("❌ Setup validation failed:")
        for error in errors:
            print(f"   - {error}")
        sys.exit(1)
    else:
        print("✅ Setup validation passed")

def main():
    """Main setup function"""
    # Validate setup before proceeding
    validate_setup()
    
    print(f"Building Enhanced Docker Monitor v{__version__}")
    print(f"Python version: {sys.version}")
    print(f"Install requires: {len(INSTALL_REQUIRES)} packages")
    print(f"Optional extras: {list(EXTRAS_REQUIRE.keys())}")
    
    setup(
        # Basic package information
        name="enhanced-docker-monitor",
        version=__version__,
        author=__author__,
        author_email="docker-monitor@example.com",
        description=__description__,
        long_description=read_long_description(),
        long_description_content_type="text/markdown",
        url="https://github.com/your-org/enhanced-docker-monitor",
        project_urls={
            "Documentation": "https://enhanced-docker-monitor.readthedocs.io/",
            "Source": "https://github.com/your-org/enhanced-docker-monitor",
            "Tracker": "https://github.com/your-org/enhanced-docker-monitor/issues",
            "Changelog": "https://github.com/your-org/enhanced-docker-monitor/blob/main/CHANGELOG.md",
        },
        
        # Package discovery and structure
        packages=find_packages(exclude=["tests", "tests.*", "docs", "docs.*"]),
        package_data=PACKAGE_DATA,
        include_package_data=True,
        zip_safe=False,
        
        # Dependencies
        python_requires=PYTHON_REQUIRES,
        install_requires=INSTALL_REQUIRES,
        extras_require=EXTRAS_REQUIRE,
        
        # Entry points
        entry_points={
            "console_scripts": CONSOLE_SCRIPTS,
        },
        
        # Metadata for PyPI
        classifiers=CLASSIFIERS,
        keywords=" ".join(KEYWORDS),
        license="MIT",
        platforms=["any"],
        
        # Options
        options={
            "bdist_wheel": {
                "universal": False,  # We support Python 3.7+ only
            },
        },
        
        # Additional metadata
        cmdclass={},
    )

if __name__ == "__main__":
    main()