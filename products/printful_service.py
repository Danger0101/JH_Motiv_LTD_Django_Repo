import requests
import json
from django.conf import settings

class PrintfulService:
    BASE_URL = "https://api.printful.com"

    def __init__(self):
        self.api_key = getattr(settings, 'PRINTFUL_API_KEY', None)
        if not self.api_key:
            print("WARNING: PRINTFUL_API_KEY not found in settings.")
        
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

    def get_store_products(self):
        """Fetches all sync products from the Printful store."""
        url = f"{self.BASE_URL}/store/products"
        print(f"Fetching Products from: {url}")
        
        try:
            response = requests.get(url, headers=self.headers)
            if response.status_code == 200:
                data = response.json().get('result', [])
                print(f"Successfully fetched {len(data)} products.")
                return data
            else:
                print(f"Error fetching products: {response.status_code} - {response.text}")
                return []
        except Exception as e:
            print(f"Exception fetching products: {e}")
            return []

    def get_product_variants(self, product_id):
        """Fetches variants for a specific sync product."""
        url = f"{self.BASE_URL}/store/products/{product_id}"
        # print(f"Fetching Variants for Product ID {product_id}...") 
        
        try:
            response = requests.get(url, headers=self.headers)
            if response.status_code == 200:
                return response.json().get('result', {}).get('sync_variants', [])
            else:
                print(f"Error fetching variants for {product_id}: {response.status_code} - {response.text}")
                return []
        except Exception as e:
            print(f"Exception fetching variants for {product_id}: {e}")
            return []
    
    def create_order(self, recipient, items):
        """
        Creates an order in Printful.
        recipient: dict with name, address1, city, etc.
        items: list of dicts with variant_id, quantity
        """
        payload = {
            "recipient": recipient,
            "items": items
        }
        print(f"Creating Printful Order with payload: {json.dumps(payload, indent=2)}")
        
        try:
            response = requests.post(f"{self.BASE_URL}/orders", json=payload, headers=self.headers)
            if response.status_code != 200:
                print(f"Error creating order: {response.status_code} - {response.text}")
            return response.json()
        except Exception as e:
            print(f"Exception creating order: {e}")
            return {'error': str(e)}