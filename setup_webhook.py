import requests
import os
import json

# --- CONFIGURATION ---
# We use the env variable for the API key so you don't have to paste it
API_KEY = os.environ.get('PRINTFUL_API_KEY')

# IMPORTANT: Ensure this matches your ACTUAL Heroku URL
WEBHOOK_URL = "https://jhmotiv-shop-ltd-official-040e4cbd5800.herokuapp.com/products/webhook/printful/"

def setup_printful_webhook():
    if not API_KEY:
        print("❌ Error: PRINTFUL_API_KEY environment variable is not set.")
        return

    print(f"Setting up webhook at: {WEBHOOK_URL}")
    
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }

    # Set the Webhook
    payload = {
        "url": WEBHOOK_URL,
        "types": [
            "package_shipped",  # Trigger tracking emails
            "order_failed",     # Alert on failure
            "order_canceled"
        ]
    }

    try:
        response = requests.post("https://api.printful.com/webhooks", json=payload, headers=headers)

        if response.status_code == 200:
            data = response.json()
            print(f"Full Printful API Response: {json.dumps(data, indent=2)}")
            print("\n✅ SUCCESS! Webhook configured.")
            print("---------------------------------------------------")
            secret_key = data.get('result', {}).get('secret_key')
            if secret_key:
                print(f"Secret Key: {secret_key}")
            else:
                print("Secret Key not found in Printful response. Please inspect the 'Full Printful API Response' above.")
            print("---------------------------------------------------")
            print("ACTION REQUIRED: Copy the 'Secret Key' above and add it to your Heroku Config Vars as 'PRINTFUL_WEBHOOK_SECRET'.")
        else:
            print(f"\n❌ FAILED. Status: {response.status_code}")
            print(response.text)
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    setup_printful_webhook()