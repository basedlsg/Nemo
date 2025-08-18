#!/usr/bin/env python3
"""
Interactive script to help obtain and configure real API keys.
"""

import os
import sys
import webbrowser
from pathlib import Path

def main():
    print("🔑 API Key Configuration Assistant")
    print("=" * 50)
    print()
    
    # Check if we're in the right directory
    project_root = Path(__file__).parent.parent
    env_file = project_root / ".env"
    
    print("This script will help you obtain real API keys for the Geo-Adaptive Energy Assistant.")
    print("We'll open the necessary websites and guide you through the process.")
    print()
    
    # Perplexity API
    print("🧠 PERPLEXITY API")
    print("-" * 20)
    print("Perplexity provides AI-powered search and research capabilities.")
    print("1. Go to: https://www.perplexity.ai/settings/api")
    print("2. Sign up or log in to your account")
    print("3. Create a new API key")
    print("4. Copy the key (starts with 'pplx-')")
    print()
    
    open_perplexity = input("Open Perplexity API page? (y/n): ").lower().strip()
    if open_perplexity == 'y':
        webbrowser.open("https://www.perplexity.ai/settings/api")
    
    perplexity_key = input("Enter your Perplexity API key (or press Enter to skip): ").strip()
    
    print()
    
    # Google Custom Search Engine
    print("🔍 GOOGLE CUSTOM SEARCH ENGINE")
    print("-" * 35)
    print("Google CSE provides web search capabilities for verification.")
    print("1. Go to: https://console.cloud.google.com/apis/credentials")
    print("2. Create a new project or select existing one")
    print("3. Enable the Custom Search API")
    print("4. Create credentials (API key)")
    print("5. Also create a Custom Search Engine at: https://cse.google.com/cse/")
    print()
    
    open_google = input("Open Google Cloud Console? (y/n): ").lower().strip()
    if open_google == 'y':
        webbrowser.open("https://console.cloud.google.com/apis/credentials")
    
    google_api_key = input("Enter your Google API key (or press Enter to skip): ").strip()
    google_engine_id = input("Enter your Google CSE Engine ID (or press Enter to skip): ").strip()
    
    print()
    
    # Update .env file
    if perplexity_key or google_api_key:
        print("📝 Updating .env file...")
        
        # Read current .env
        env_content = ""
        if env_file.exists():
            with open(env_file, 'r') as f:
                env_content = f.read()
        
        # Update keys
        if perplexity_key:
            if "PERPLEXITY_API_KEY=" in env_content:
                # Replace existing
                lines = env_content.split('\n')
                for i, line in enumerate(lines):
                    if line.startswith("PERPLEXITY_API_KEY="):
                        lines[i] = f"PERPLEXITY_API_KEY={perplexity_key}"
                env_content = '\n'.join(lines)
            else:
                # Add new
                env_content += f"\nPERPLEXITY_API_KEY={perplexity_key}\n"
        
        if google_api_key:
            if "GOOGLE_CSE_API_KEY=" in env_content:
                lines = env_content.split('\n')
                for i, line in enumerate(lines):
                    if line.startswith("GOOGLE_CSE_API_KEY="):
                        lines[i] = f"GOOGLE_CSE_API_KEY={google_api_key}"
                env_content = '\n'.join(lines)
            else:
                env_content += f"\nGOOGLE_CSE_API_KEY={google_api_key}\n"
        
        if google_engine_id:
            if "GOOGLE_CSE_ENGINE_ID=" in env_content:
                lines = env_content.split('\n')
                for i, line in enumerate(lines):
                    if line.startswith("GOOGLE_CSE_ENGINE_ID="):
                        lines[i] = f"GOOGLE_CSE_ENGINE_ID={google_engine_id}"
                env_content = '\n'.join(lines)
            else:
                env_content += f"\nGOOGLE_CSE_ENGINE_ID={google_engine_id}\n"
        
        # Write updated .env
        with open(env_file, 'w') as f:
            f.write(env_content)
        
        print("✅ .env file updated!")
        print()
        
        # Show what was configured
        print("🎯 Configuration Summary:")
        if perplexity_key:
            print(f"   ✅ Perplexity API: {perplexity_key[:10]}...")
        if google_api_key:
            print(f"   ✅ Google CSE API: {google_api_key[:10]}...")
        if google_engine_id:
            print(f"   ✅ Google CSE Engine: {google_engine_id}")
        
        print()
        print("🚀 Ready to start services with real APIs!")
        print("   Run: python scripts/start-working-services.py")
    
    else:
        print("⚠️  No API keys provided. Services will run in mock mode.")
        print("   You can run this script again later to add keys.")
    
    print()
    print("📚 Additional Resources:")
    print("   - Perplexity API Docs: https://docs.perplexity.ai/")
    print("   - Google CSE Setup: https://developers.google.com/custom-search/v1/introduction")

if __name__ == "__main__":
    main()