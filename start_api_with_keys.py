#!/usr/bin/env python3

import os
import subprocess
import sys

# Set the environment variables
os.environ["PPLX_API_KEY"] = "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"
os.environ["GOOGLE_API_KEY"] = "AIzaSyAM6Ko33ubRd_d8tkr6b4rocOqRXgyAy0Q"
os.environ["GOOGLE_CSE_ID"] = "c2902a74ad3664d41"
os.environ["ALLOWLIST_DOMAINS"] = "gd.gov.cn,gdee.gd.gov.cn,gddrc.gd.gov.cn,csg.cn,beijing.gov.cn,bj.gov.cn,shanghai.gov.cn,sh.gov.cn,sd.gov.cn,shandong.gov.cn,nmg.gov.cn,innermongolia.gov.cn"

print("Starting API server with API keys...")
print(f"PPLX_API_KEY: {'✅ Set' if os.environ.get('PPLX_API_KEY') else '❌ Not set'}")
print(f"GOOGLE_API_KEY: {'✅ Set' if os.environ.get('GOOGLE_API_KEY') else '❌ Not set'}")
print(f"GOOGLE_CSE_ID: {'✅ Set' if os.environ.get('GOOGLE_CSE_ID') else '❌ Not set'}")

# Start the uvicorn server
try:
    subprocess.run([
        sys.executable, "-m", "uvicorn", "services.gateway.api:app", 
        "--host", "0.0.0.0", "--port", "8000", "--reload"
    ], env=os.environ)
except KeyboardInterrupt:
    print("\nAPI server stopped.")
