#!/usr/bin/env python3
import os, sys, subprocess, shlex
from pathlib import Path

def load_dotenv(p: Path):
    if not p.exists(): return
    for line in p.read_text(encoding="utf-8").splitlines():
        line=line.strip()
        if not line or line.startswith("#") or "=" not in line: continue
        k,v=line.split("=",1); os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT/".env")
os.environ.setdefault("ENABLE_REAL_APIS","false")
os.environ.setdefault("ALLOW_MOCK_FALLBACK","false")

# Corrected commands to point to api:app
CMDS = [
  "uvicorn services.gateway.api:app --host 0.0.0.0 --port 8000 --log-level debug",
  "uvicorn services.retriever.api:app --host 0.0.0.0 --port 8011 --log-level debug",
  "uvicorn services.composer.api:app --host 0.0.0.0 --port 8012 --log-level debug",
]

procs = []
try:
    for cmd in CMDS:
        print(f"[start-services] Launching: {cmd}")
        p = subprocess.Popen(shlex.split(cmd), env=os.environ.copy())
        procs.append(p)
    
    # Wait for any process to exit, then terminate others
    exit_codes = [p.wait() for p in procs]
    sys.exit(max(exit_codes) if exit_codes else 0)

except KeyboardInterrupt:
    print("\n[start-services] Terminating services...")
    for p in procs:
        p.terminate()
    sys.exit(0)
