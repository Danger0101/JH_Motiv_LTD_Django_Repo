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

    def validate_recipient(self, recipient):
        """
        Validates the recipient dictionary to ensure required fields for Printful are present.
        Returns (bool, error_message).
        """
        required_fields = ['name', 'address1', 'city', 'country_code', 'zip']
        # State code is mandatory for US, CA, AU, etc., but we'll warn rather than block strictly if missing
        
        missing = [field for field in required_fields if not recipient.get(field)]
        if missing:
            return False, f"Missing required shipping fields: {', '.join(missing)}"
        
        return True, ""

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
                error_json = response.json()
                error_msg = error_json.get('error', {}).get('message', '')
                if "Manual Order / API platform" in error_msg:
                    logger.critical("CRITICAL ERROR: Store Type Incorrect. Please use a 'Manual order platform / API' store.")
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
                # The 'sync_variants' list contains the variant details
                return response.json().get('result', {}).get('sync_variants', [])
            else:
                logger.error(f"Error fetching variants for {product_id}: {response.status_code} - {response.text}")
                return []
        except Exception as e:
            logger.exception(f"Exception fetching variants for {product_id}: {e}")
            return []
    
    def calculate_shipping_rates(self, recipient, items):
        """
        Calculates shipping rates for a list of items to a specific recipient.
        
        Args:
            recipient (dict): { 'address1': ..., 'city': ..., 'country_code': ..., 'zip': ... }
            items (list): [{ 'variant_id': 123, 'quantity': 1 }, ...]
        """
        url = f"{self.BASE_URL}/shipping/rates"
        payload = {
            "recipient": recipient,
            "items": items
        }
        
        try:
            response = requests.post(url, json=payload, headers=self.headers)
            if response.status_code == 200:
                result = response.json().get('result', [])
                # Return the cheapest or 'STANDARD' rate
                # Printful returns a list of available rates (Standard, Express, etc.)
                # We default to the first one (usually cheapest) or look for 'STANDARD'
                return result
            else:
                logger.error(f"Printful Shipping Calc Error: {response.status_code} - {response.text}")
                return []
        except Exception as e:
            logger.exception(f"Exception calculating shipping: {e}")
            return []
    
    def create_order(self, recipient, items):
        """
        Creates an order in Printful.
        """
        # 1. Validate Payload locally before sending
        is_valid, error_msg = self.validate_recipient(recipient)
        if not is_valid:
            logger.error(f"Validation Failed: {error_msg}")
            return {'error': error_msg, 'code': 400}

        payload = {
            "recipient": recipient,
            "items": items
        }
        logger.info(f"Creating Printful Order with payload: {json.dumps(payload, indent=2)}")
        
        try:
            response = requests.post(f"{self.BASE_URL}/orders", json=payload, headers=self.headers)
            if response.status_code not in [200, 201]:
                logger.error(f"Printful API Error: {response.status_code} - {response.text}")
                return {'error': response.text, 'code': response.status_code}
            
            return response.json()
        except Exception as e:
            logger.exception(f"Exception creating order: {e}")
            return {'error': str(e)}