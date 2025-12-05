import requests
import os
import json

# --- CONFIGURATION ---
# Ensure these are set in your terminal or .env
API_KEY = os.environ.get('PRINTFUL_API_KEY')
STORE_ID = os.environ.get('PRINTFUL_STORE_ID')

# MATCH THIS TO YOUR DJANGO URLS.PY
# Your code uses 'webhooks' (plural), so we use that here.
WEBHOOK_URL = "https://jhmotiv-shop-ltd-official-040e4cbd5800.herokuapp.com/products/webhooks/printful/"

def try_setup(version="v2", use_header=True):
    print(f"\n--- Attempting Setup: API {version.upper()} | Header: {use_header} ---")
    
    if not API_KEY:
        print("❌ Error: PRINTFUL_API_KEY not found.")
        return False

    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }
    
    # Add Store ID header only if requested
    if use_header and STORE_ID:
        headers["X-PF-Store-Id"] = str(STORE_ID)

    # Endpoint & Payload Config
    if version == "v2":
        url = "https://api.printful.com/v2/webhooks"
        # V2 uses 'events'
        payload = {
            "url": WEBHOOK_URL,
            "events": ["package_shipped", "order_failed", "order_canceled"]
        }
    else:
        url = "https://api.printful.com/webhooks"
        # V1 uses 'types'
        payload = {
            "url": WEBHOOK_URL,
            "types": ["package_shipped", "order_failed", "order_canceled"]
        }

    try:
        # 1. Try to DELETE existing to clear conflicts
        print(f"Cleaning up old webhooks at {url}...")
        try:
            requests.delete(url, headers=headers)
        except:
            pass

        # 2. Try to POST new
        print(f"Posting new configuration to {url}...")
        response = requests.post(url, json=payload, headers=headers)
        
        print(f"Status: {response.status_code}")
        
        if response.status_code in [200, 201]:
            data = response.json()
            # Extract Secret Key (Only available in V2)
            result = data.get('result', {})
            secret_key = result.get('secret_key') or data.get('secret_key') 
            
            if secret_key:
                print("\n✅ SUCCESS! Webhook Configured with Security.")
                print("="*60)
                print(f"PRINTFUL_WEBHOOK_SECRET = {secret_key}")
                print("="*60)
                print("👉 ACTION: Add this key to your Heroku Config Vars.")
                return True
            elif version == "v1":
                 print("\n⚠️  Success (V1 fallback), but NO Secret Key returned.")
                 print("ACTION REQUIRED: You MUST disable signature verification in products/views.py")
                 return True
            else:
                 print("⚠️  Success, but secret key missing.")
                 return True
        else:
            print(f"❌ Failed: {response.text}")
            return False

    except Exception as e:
        print(f"Exception: {e}")
        return False

if __name__ == "__main__":
    # ATTEMPT 1: V2 with Header (Standard)
    if try_setup("v2", use_header=True):
        exit()
        
    # ATTEMPT 2: V2 WITHOUT Header (If Token is already Store-Specific)
    if try_setup("v2", use_header=False):
        exit()

    # ATTEMPT 3: V1 (Fallback - Stable but no secret key)
    print("\n🛑 V2 Failed. Attempting V1 Fallback...")
    try_setup("v1", use_header=True)
