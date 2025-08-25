#!/usr/bin/env python3
"""
Simple API startup script.
"""
import os
import sys
import subprocess
from pathlib import Path

def main():
    """Start the API server."""
    print("🚀 Starting Chinese Energy Compliance Assistant API")
    print("=" * 50)

    # Check if virtual environment exists
    if not Path("venv").exists():
        print("❌ Virtual environment not found. Run: python scripts/setup_env.py")
        return False

    # Load environment variables
    env_file = Path(".env")
    if env_file.exists():
        print("📁 Loading environment variables...")
        with open(env_file) as f:
            for line in f:
                if '=' in line and not line.startswith('#'):
                    key, value = line.strip().split('=', 1)
                    os.environ[key] = value

    # Set environment variables
    os.environ['FEATURE_ONLINE_QUERY'] = 'true'
    os.environ['QUERY_MODE'] = 'web_only'

    # Start API server
    cmd = [
        ".\\venv\\Scripts\\python.exe",
        "-m", "uvicorn",
        "main:app",
        "--host", "0.0.0.0",
        "--port", "8000",
        "--reload"
    ]

    print("🌐 Starting API server...")
    print(f"   Command: {' '.join(cmd)}")
    print("   URL: http://localhost:8000")
    print("   Docs: http://localhost:8000/docs")
    print("\nPress Ctrl+C to stop the server\n")

    try:
        subprocess.run(cmd, check=True)
        return True
    except KeyboardInterrupt:
        print("\n🛑 Server stopped")
        return True
    except Exception as e:
        print(f"❌ Server failed: {e}")
        return False

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)
