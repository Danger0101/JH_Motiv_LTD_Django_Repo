import requests
import json
from django.conf import settings

class PrintfulService:
    BASE_URL = "https://api.printful.com"

    def __init__(self):
        self.api_key = getattr(settings, 'PRINTFUL_API_KEY', None)
        self.store_id = getattr(settings, 'PRINTFUL_STORE_ID', None)
        print(f"PrintfulService initialized.")
        print(f"API Key found: {'Yes' if self.api_key else 'No'}")
        print(f"Store ID found: {self.store_id if self.store_id else 'No'}")

        if not self.api_key:
            print("CRITICAL: PRINTFUL_API_KEY not found in settings. Service will not work.")

        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        if self.store_id:
            self.headers["X-Printful-Store-Id"] = str(self.store_id)
        
        print(f"Request Headers: {self.headers}")

    def get_store_products(self):
        """Fetches all sync products from the Printful store."""
        url = f"{self.BASE_URL}/store/products"
        print(f"--- Fetching Products from Printful ---")
        print(f"URL: {url}")
        
        try:
            print("Making request to Printful API...")
            response = requests.get(url, headers=self.headers)
            print(f"Response Status Code: {response.status_code}")
            if response.status_code == 200:
                data = response.json().get('result', [])
                print(f"Successfully fetched {len(data)} products.")
                return data
            else:
                print(f"Error fetching products: {response.text}")
                return []
        except Exception as e:
            print(f"An exception occurred: {e}")
            return []

    def get_product_variants(self, product_id):
        """Fetches variants for a specific sync product."""
        url = f"{self.BASE_URL}/store/products/{product_id}"
        print(f"--- Fetching Variants for Product ID {product_id} ---")
        print(f"URL: {url}")

        try:
            print("Making request to Printful API...")
            response = requests.get(url, headers=self.headers)
            print(f"Response Status Code: {response.status_code}")
            if response.status_code == 200:
                variants = response.json().get('result', {}).get('sync_variants', [])
                print(f"Successfully fetched {len(variants)} variants.")
                return variants
            else:
                print(f"Error fetching variants: {response.text}")
                return []
        except Exception as e:
            print(f"An exception occurred: {e}")
            return []
    
    def create_order(self, recipient, items):
        """
        Creates an order in Printful.
        recipient: dict with name, address1, city, etc.
        items: list of dicts with variant_id, quantity
        """
        url = f"{self.BASE_URL}/orders"
        payload = {
            "recipient": recipient,
            "items": items
        }
        print(f"--- Creating Printful Order ---")
        print(f"URL: {url}")
        print(f"Payload: {json.dumps(payload, indent=2)}")
        
        try:
            print("Making request to Printful API...")
            response = requests.post(url, json=payload, headers=self.headers)
            print(f"Response Status Code: {response.status_code}")
            response_data = response.json()
            if response.status_code != 200:
                print(f"Error creating order: {response.text}")
            else:
                print("Order created successfully.")
            return response_data
        except Exception as e:
            print(f"An exception occurred: {e}")
            return {'error': str(e)}