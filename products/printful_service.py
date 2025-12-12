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
        Validates the recipient dictionary.
        """
        required_fields = ['address1', 'city', 'country_code', 'zip']
        # 'name' is often required for Orders but not necessarily for Rates, 
        # but we'll check it to be safe if creating an order.
        
        missing = [field for field in required_fields if not recipient.get(field)]
        if missing:
            return False, f"Missing required fields: {', '.join(missing)}"
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
    
    def calculate_shipping_rates(self, recipient, items, currency='GBP', locale='en_US'):
        """
        Calculates live shipping rates.
        """
        url = f"{self.BASE_URL}/shipping/rates"
        
        # Ensure payload strictly follows API specs
        payload = {
            "recipient": {
                "address1": recipient.get('address1'),
                "address2": recipient.get('address2', ''),
                "city": recipient.get('city'),
                "state_code": recipient.get('state_code', ''),
                "country_code": recipient.get('country_code'),
                "zip": recipient.get('zip'),
                "phone": recipient.get('phone', '') # Optional but recommended
            },
            "items": items,
            "currency": currency,
            "locale": locale
        }
        
        try:
            response = requests.post(url, json=payload, headers=self.headers)
            response.raise_for_status() # Raise error for 4xx/5xx
            
            result = response.json().get('result', [])
            return result
            
        except requests.exceptions.HTTPError as e:
            logger.error(f"Printful API Error: {e.response.text}")
            return []
        except Exception as e:
            logger.exception(f"Printful Service Error: {e}")
            return []
    
    def create_order(self, recipient, items):
        """
        Creates an order in Printful.
        """
        url = f"{self.BASE_URL}/orders"
        
        # Add phone to recipient for orders (highly recommended)
        payload = {
            "recipient": recipient,
            "items": items
        }
        
        try:
            response = requests.post(url, json=payload, headers=self.headers)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Failed to create Printful order: {e}")
            if hasattr(e, 'response'):
                return {'error': e.response.text, 'code': e.response.status_code}
            return {'error': str(e)}