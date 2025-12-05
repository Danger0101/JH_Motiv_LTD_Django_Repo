import requests
import os
import json

# --- CONFIGURATION ---
# Ensure your API Key is set here or in your environment
# API_KEY = "YOUR_PRINTFUL_API_KEY" 
API_KEY = os.environ.get('PRINTFUL_API_KEY')

# Your Production URL (Must be HTTPS and match your Django urls.py)
WEBHOOK_URL = "https://jhmotiv-shop-ltd-official-040e4cbd5800.herokuapp.com/products/webhook/printful/"

def setup_printful_webhook_v2():
    if not API_KEY:
        print("❌ Error: PRINTFUL_API_KEY not found. Set it in your .env or terminal.")
        return

    print(f"🚀 Setting up V2 Webhook at: {WEBHOOK_URL}")
    
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }

    # V2 Endpoint
    v2_url = "https://api.printful.com/v2/webhooks"

    # 1. Payload with 'events' (Correct for V2)
    payload = {
        "url": WEBHOOK_URL,
        "events": [             # <--- CHANGED from 'types' to 'events'
            "package_shipped",
            "order_failed",
            "order_canceled"
        ]
    }

    # 2. Send Request
    try:
        # First, try to create/update configuration
        response = requests.post(v2_url, json=payload, headers=headers)
        
        # If it fails because one exists, try PUT to update
        if response.status_code == 400 and "already exists" in response.text:
             print("Webhook already exists, updating...")
             response = requests.put(v2_url, json=payload, headers=headers)

        print(f"Status Code: {response.status_code}")
        
        if response.status_code in [200, 201]:
            data = response.json()
            result = data.get('result', {})
            
            # V2 returns the secret key in the result object
            secret_key = result.get('secret_key')
            
            if secret_key:
                print("\n✅ SUCCESS! V2 Webhook configured.")
                print("="*60)
                print(f"PRINTFUL_WEBHOOK_SECRET = {secret_key}")
                print("="*60)
                print("👉 ACTION: Add this key to your Heroku Config Vars immediately.")
            else:
                print("\n⚠️ Webhook created, but NO Secret Key returned.")
                print("Full Response:", json.dumps(data, indent=2))
        else:
            print(f"\n❌ FAILED. Response: {response.text}")
            
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    setup_printful_webhook_v2()