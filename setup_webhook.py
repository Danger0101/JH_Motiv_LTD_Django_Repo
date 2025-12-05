import requests
import os

# --- CONFIGURATION ---
# 1. Ensure your API Key is set here or in your environment
API_KEY = os.getenv('PRINTFUL_API_KEY', 'YOUR_PRINTFUL_API_KEY_HERE_IF_NOT_IN_ENV')

# 2. Your Production URL (Heroku or custom domain)
# MUST BE HTTPS
WEBHOOK_URL = os.getenv('PRINTFUL_PUBLIC_WEBHOOK_URL', "https://jhmotiv-shop-ltd-official-040e4cbd5800.herokuapp.com/products/webhook/printful/")

# Ensure WEBHOOK_URL is set
if not WEBHOOK_URL or WEBHOOK_URL == 'YOUR_PRINTFUL_PUBLIC_WEBHOOK_URL_HERE':
    print("CRITICAL: WEBHOOK_URL is not set. Please set the PRINTFUL_PUBLIC_WEBHOOK_URL environment variable.")
    exit(1)

# ---------------------

def setup_printful_webhook():
    print(f"Setting up webhook at: {WEBHOOK_URL}")
    
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }

    # 1. Check existing webhooks (optional cleanup)
    # response = requests.get("https://api.printful.com/webhooks", headers=headers)
    # print("Current Webhooks:", response.json())

    # 2. Set the Webhook
    payload = {
        "url": WEBHOOK_URL,
        "types": [
            "package_shipped",  # Trigger tracking emails
            "order_failed",     # Alert on failure
            "order_canceled"
        ]
    }

    response = requests.post("https://api.printful.com/webhooks", json=payload, headers=headers)

    if response.status_code == 200:
        data = response.json()
        print("\n✅ SUCCESS! Webhook configured.")
        print("---------------------------------------------------")
        print(f"Secret Key: {data['result']['secret_key']}")
        print("---------------------------------------------------")
        print("ACTION REQUIRED: Copy the 'Secret Key' above and add it to your Heroku Config Vars as 'PRINTFUL_WEBHOOK_SECRET'.")
    else:
        print(f"\n❌ FAILED. Status: {response.status_code}")
        print(response.text)

if __name__ == "__main__":
    setup_printful_webhook()
