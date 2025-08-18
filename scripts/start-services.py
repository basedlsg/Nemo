#!/usr/bin/env python3
import os, sys, subprocess, shlex
from pathlib import Path

# 1) Load .env once (if present)
def load_dotenv(dotenv_path: Path):
    if not dotenv_path.exists():
        print(f"[start-services] .env not found at {dotenv_path}, continuing...")
        return
    with dotenv_path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            k = k.strip(); v = v.strip().strip('"').strip("'")
            # do not overwrite values already present in the environment
            os.environ.setdefault(k, v)

# Locate .env at repo root (adjust if your layout differs)
REPO_ROOT = Path(__file__).resolve().parent.parent
DOTENV = REPO_ROOT / ".env"
load_dotenv(DOTENV)

# 2) Defensive defaults (fail-closed)
os.environ.setdefault("ENABLE_REAL_APIS", "false")         # set true in .env or cloud
os.environ.setdefault("ALLOW_MOCK_FALLBACK", "false")       # mock only when explicitly allowed

# Optional: debug print once
print("[start-services] ENABLE_REAL_APIS=", os.getenv("ENABLE_REAL_APIS"))
print("[start-services] ALLOW_MOCK_FALLBACK=", os.getenv("ALLOW_MOCK_FALLBACK"))

# 3) Commands to launch services (adjust paths as needed)
CMDS = [
    "uvicorn services.gateway.api:app --host 0.0.0.0 --port 8000",
    "uvicorn services.retriever.api:app --host 0.0.0.0 --port 8011",
    "uvicorn services.composer.api:app --host 0.0.0.0 --port 8012",
    # add OCR workers, discovery, verification, etc., if run locally
]

PROCS = []
try:
    for cmd in CMDS:
        print(f"[start-services] Launch: {cmd}")
        p = subprocess.Popen(shlex.split(cmd), env=os.environ.copy())
        PROCS.append(p)
    # Wait for any to exit
    exit_codes = [p.wait() for p in PROCS]
    sys.exit(max(exit_codes) if exit_codes else 0)
except KeyboardInterrupt:
    for p in PROCS:
        p.terminate()
    sys.exit(0)
