#!/usr/bin/env python
"""
Quick Start Script for Health Check Kiosk
==========================================

This script helps you quickly start the Health Check Kiosk monolithic application.
It checks dependencies, runs migrations, and starts the development server.

Usage:
    python start.py
"""

import os
import subprocess
import sys
from pathlib import Path


def print_header(text):
    """Print a formatted header"""
    print("\n" + "=" * 60)
    print(f"  {text}")
    print("=" * 60 + "\n")


def print_success(text):
    """Print success message"""
    print(f"✓ {text}")


def print_error(text):
    """Print error message"""
    print(f"✗ {text}")


def print_info(text):
    """Print info message"""
    print(f"ℹ {text}")


def check_python_version():
    """Check if Python version is compatible"""
    print_header("Checking Python Version")

    version = sys.version_info
    print(f"Python {version.major}.{version.minor}.{version.micro}")

    if version.major < 3 or (version.major == 3 and version.minor < 8):
        print_error("Python 3.8 or higher is required")
        return False

    print_success("Python version is compatible")
    return True


def check_virtual_env():
    """Check if virtual environment exists"""
    print_header("Checking Virtual Environment")

    venv_path = Path("venv")

    if not venv_path.exists():
        print_info("Virtual environment not found. Creating one...")
        try:
            subprocess.run([sys.executable, "-m", "venv", "venv"], check=True)
            print_success("Virtual environment created")
        except subprocess.CalledProcessError:
            print_error("Failed to create virtual environment")
            return False
    else:
        print_success("Virtual environment exists")

    return True


def get_python_executable():
    """Get the path to the Python executable in the virtual environment"""
    if os.name == "nt":  # Windows
        return os.path.join("venv", "Scripts", "python.exe")
    else:  # Unix-like
        return os.path.join("venv", "bin", "python")


def get_pip_executable():
    """Get the path to the pip executable in the virtual environment"""
    if os.name == "nt":  # Windows
        return os.path.join("venv", "Scripts", "pip.exe")
    else:  # Unix-like
        return os.path.join("venv", "bin", "pip")


def install_dependencies():
    """Install required dependencies"""
    print_header("Installing Dependencies")

    pip_exec = get_pip_executable()

    try:
        print_info("Installing Django and other packages...")
        subprocess.run(
            [
                pip_exec,
                "install",
                "-q",
                "django",
                "djangorestframework",
                "django-cors-headers",
                "requests",
            ],
            check=True,
        )
        print_success("Dependencies installed successfully")
        return True
    except subprocess.CalledProcessError:
        print_error("Failed to install dependencies")
        return False


def run_migrations():
    """Run database migrations"""
    print_header("Running Database Migrations")

    python_exec = get_python_executable()

    try:
        # Make migrations
        print_info("Creating migrations...")
        subprocess.run([python_exec, "manage.py", "makemigrations"], check=True)

        # Apply migrations
        print_info("Applying migrations...")
        subprocess.run([python_exec, "manage.py", "migrate"], check=True)

        print_success("Migrations completed successfully")
        return True
    except subprocess.CalledProcessError:
        print_error("Failed to run migrations")
        return False


def check_superuser():
    """Check if superuser exists, create if not"""
    print_header("Checking Superuser")

    python_exec = get_python_executable()

    try:
        # Check if any superuser exists
        check_cmd = (
            "from django.contrib.auth.models import User; "
            "import sys; "
            "sys.exit(0 if User.objects.filter(is_superuser=True).exists() else 1)"
        )

        result = subprocess.run(
            [python_exec, "manage.py", "shell", "-c", check_cmd], capture_output=True
        )

        if result.returncode == 0:
            print_success("Superuser already exists")
            return True

        # Create superuser
        print_info("Creating default superuser...")
        print_info("Username: admin")
        print_info("Password: admin123")

        create_cmd = (
            "from django.contrib.auth.models import User; "
            "User.objects.create_superuser('admin', 'admin@example.com', 'admin123')"
        )

        subprocess.run(
            [python_exec, "manage.py", "shell", "-c", create_cmd],
            check=True,
            capture_output=True,
        )

        print_success("Superuser created successfully")
        print_info("Login credentials - Username: admin, Password: admin123")
        return True

    except subprocess.CalledProcessError:
        print_error("Failed to create superuser")
        return False


def start_server():
    """Start the Django development server"""
    print_header("Starting Development Server")

    python_exec = get_python_executable()

    print_success("Server is starting...")
    print("\n" + "=" * 60)
    print("  Health Check Kiosk is now running!")
    print("=" * 60)
    print("\nAccess the application at:")
    print("  • Kiosk Interface:  http://127.0.0.1:8000/")
    print("  • Dashboard:        http://127.0.0.1:8000/dashboard/")
    print("  • Patient List:     http://127.0.0.1:8000/patients/")
    print("  • QR Scanner:       http://127.0.0.1:8000/scanner/")
    print("  • Admin Panel:      http://127.0.0.1:8000/admin/")
    print("\nLogin credentials:")
    print("  • Username: admin")
    print("  • Password: admin123")
    print("\nPress Ctrl+C to stop the server\n")
    print("=" * 60 + "\n")

    try:
        subprocess.run([python_exec, "manage.py", "runserver", "0.0.0.0:8000"])
    except KeyboardInterrupt:
        print("\n\nServer stopped.")
        print_success("Thank you for using Health Check Kiosk!")


def main():
    """Main function"""
    print("\n" + "=" * 60)
    print("  HEALTH CHECK KIOSK - QUICK START")
    print("=" * 60)

    # Change to script directory
    script_dir = Path(__file__).parent.absolute()
    os.chdir(script_dir)

    # Run checks and setup
    checks = [
        ("Python Version", check_python_version),
        ("Virtual Environment", check_virtual_env),
        ("Dependencies", install_dependencies),
        ("Database Migrations", run_migrations),
        ("Superuser", check_superuser),
    ]

    for check_name, check_func in checks:
        if not check_func():
            print_error(
                f"{check_name} check failed. Please fix the issue and try again."
            )
            sys.exit(1)

    # Start server
    start_server()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nSetup interrupted by user.")
        sys.exit(0)
    except Exception as e:
        print_error(f"Unexpected error: {e}")
        sys.exit(1)
