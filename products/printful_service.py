import requests
from django.conf import settings

class PrintfulService:
    BASE_URL = "https://api.printful.com"

    def __init__(self):
        self.api_key = settings.PRINTFUL_API_KEY
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

    def get_store_products(self):
        """Fetches all sync products from the Printful store."""
        response = requests.get(f"{self.BASE_URL}/store/products", headers=self.headers)
        if response.status_code == 200:
            return response.json().get('result', [])
        return []

    def get_product_variants(self, product_id):
        """Fetches variants for a specific sync product."""
        response = requests.get(f"{self.BASE_URL}/store/products/{product_id}", headers=self.headers)
        if response.status_code == 200:
            return response.json().get('result', {}).get('sync_variants', [])
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
        response = requests.post(f"{self.BASE_URL}/orders", json=payload, headers=self.headers)
        return response.json()
