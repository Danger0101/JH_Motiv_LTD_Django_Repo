import requests
import os

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
            print("\n✅ SUCCESS! Webhook configured.")
            print("---------------------------------------------------")
            print("Please find your Printful Webhook Secret in your Printful dashboard (API/Store settings) and add it to your Heroku Config Vars as 'PRINTFUL_WEBHOOK_SECRET'.")
            print("---------------------------------------------------")
        else:
            print(f"\n❌ FAILED. Status: {response.status_code}")
            print(response.text)
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    setup_printful_webhook()