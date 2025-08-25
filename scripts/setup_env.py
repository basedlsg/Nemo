#!/usr/bin/env python3
"""
Minimal environment setup for Chinese energy compliance assistant.
"""
import os
import sys
import subprocess
from pathlib import Path

def run_command(cmd, description):
    """Run a command and return success status."""
    print(f"🔧 {description}...")
    try:
        result = subprocess.run(cmd, shell=True, check=True, capture_output=True, text=True)
        print(f"✅ {description} completed")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ {description} failed: {e.stderr}")
        return False

def setup_environment():
    """Minimal environment setup."""
    print("🚀 Setting up Chinese Energy Compliance Assistant Environment")
    print("=" * 60)

    # Check Python version
    python_version = sys.version_info
    if python_version < (3, 8):
        print(f"❌ Python {python_version.major}.{python_version.minor} is too old. Need Python 3.8+")
        return False

    print(f"✅ Python {python_version.major}.{python_version.minor}.{python_version.micro}")

    # Create virtual environment if it doesn't exist
    if not Path("venv").exists():
        if not run_command("python -m venv venv", "Creating virtual environment"):
            return False
    else:
        print("✅ Virtual environment already exists")

    # Activate virtual environment (Windows)
    activate_cmd = ".\\venv\\Scripts\\Activate.ps1" if os.name == 'nt' else "source venv/bin/activate"
    print(f"💡 To activate: {activate_cmd}")

    # Install/update pip
    if not run_command(".\\venv\\Scripts\\python.exe -m pip install --upgrade pip", "Upgrading pip"):
        return False

    # Install requirements
    if not run_command(".\\venv\\Scripts\\pip.exe install -r requirements.txt", "Installing requirements"):
        return False

    # Test imports
    test_imports = ".\\venv\\Scripts\\python.exe -c \"import fastapi, uvicorn, requests, pydantic; print('✅ All imports successful')\""
    if not run_command(test_imports, "Testing imports"):
        return False

    # Load environment variables from env.yaml
    env_file = Path("env.yaml")
    if env_file.exists():
        print("📁 Loading environment variables...")
        with open(env_file) as f:
            for line in f:
                if '=' in line and not line.startswith('#'):
                    key, value = line.strip().split('=', 1)
                    os.environ[key] = value

        # Create .env file for easier loading
        with open('.env', 'w') as f:
            with open(env_file) as env_f:
                for line in env_f:
                    if '=' in line and not line.startswith('#'):
                        f.write(line)

        print("✅ Environment variables loaded")

    print("\n🎉 Environment setup complete!")
    print("\n📋 Next steps:")
    print("1. Activate environment: .\\venv\\Scripts\\Activate.ps1")
    print("2. Start API: python -m uvicorn main:app --host 0.0.0.0 --port 8000")
    print("3. Test API: python scripts/test_simple.py")

    return True

if __name__ == "__main__":
    success = setup_environment()
    exit(0 if success else 1)
