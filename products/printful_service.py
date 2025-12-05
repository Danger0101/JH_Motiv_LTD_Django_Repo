import requests
import json
import logging
from django.conf import settings

logger = logging.getLogger(__name__)

class PrintfulService:
    BASE_URL = "https://api.printful.com"

    def __init__(self):
        self.api_key = getattr(settings, 'PRINTFUL_API_KEY', None)
        if not self.api_key:
            logger.warning("PRINTFUL_API_KEY not found in settings.")
        
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

    def get_store_products(self):
        """Fetches all sync products from the Printful store."""
        url = f"{self.BASE_URL}/store/products"
        logger.info(f"Fetching Products from: {url}")
        
        try:
            response = requests.get(url, headers=self.headers)
            
            if response.status_code == 200:
                data = response.json().get('result', [])
                logger.info(f"Successfully fetched {len(data)} products.")
                return data
            
            elif response.status_code == 400:
                # Specific check for the "Store Type" error
                error_json = response.json()
                error_msg = error_json.get('error', {}).get('message', '')
                if "Manual Order / API platform" in error_msg:
                    logger.critical("\n" + "="*60)
                    logger.critical("CRITICAL ERROR: INCORRECT STORE TYPE")
                    logger.critical("="*60)
                    logger.critical(f"The Store ID you are using is connected to an integration (e.g., WooCommerce).")
                    logger.critical(f"Printful forbids fetching products via API for integration stores.")
                    logger.critical(f"SOLUTION: Create a new 'Manual order platform / API' store in Printful")
                    logger.critical(f"and use that Store ID/API Key for this Django app.")
                    logger.critical("="*60 + "\n")
                else:
                    logger.error(f"Error fetching products: {response.status_code} - {response.text}")
                return []
            
            else:
                logger.error(f"Error fetching products: {response.status_code} - {response.text}")
                return []
                
        except Exception as e:
            logger.exception(f"Exception fetching products: {e}")
            return []

    def get_product_variants(self, product_id):
        """Fetches variants for a specific sync product."""
        url = f"{self.BASE_URL}/store/products/{product_id}"
        
        try:
            response = requests.get(url, headers=self.headers)
            if response.status_code == 200:
                return response.json().get('result', {}).get('sync_variants', [])
            else:
                logger.error(f"Error fetching variants for {product_id}: {response.status_code} - {response.text}")
                return []
        except Exception as e:
            logger.exception(f"Exception fetching variants for {product_id}: {e}")
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
        logger.info(f"Creating Printful Order with payload: {json.dumps(payload, indent=2)}")
        
        try:
            response = requests.post(f"{self.BASE_URL}/orders", json=payload, headers=self.headers)
            if response.status_code != 200:
                logger.error(f"Error creating order: {response.status_code} - {response.text}")
            return response.json()
        except Exception as e:
            logger.exception(f"Exception creating order: {e}")
            return {'error': str(e)}