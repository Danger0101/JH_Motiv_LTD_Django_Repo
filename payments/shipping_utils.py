import logging
from decimal import Decimal
from django.conf import settings
from products.printful_service import PrintfulService

logger = logging.getLogger(__name__)

def get_shipping_rates(address_data, cart):
    """
    Returns shipping rates and tax. 
    Prioritizes Printful, falls back to flat rates if API fails or IDs are invalid.
    """
    rates = []
    
    # 1. Filter for Physical Items
    physical_items = [item for item in cart.items.all() if getattr(item.variant.product, 'product_type', 'physical') == 'physical']
    
    if not physical_items and cart.items.exists():
         # Digital-only cart = No shipping
        return [], Decimal('0.00')

    # 2. Try Printful Calculation
    try:
        # Only attempt if API key is set
        if getattr(settings, 'PRINTFUL_API_KEY', None):
            printful = PrintfulService()
            printful_items = []
            
            for item in physical_items:
                if item.variant.printful_variant_id:
                    printful_items.append({
                        'variant_id': item.variant.printful_variant_id,
                        'quantity': item.quantity
                    })
            
            if printful_items:
                # Map Stripe Element address format to Printful
                recipient = {
                    'address1': address_data.get('line1') or address_data.get('address1'),
                    'address2': address_data.get('line2') or address_data.get('address2', ''),
                    'city': address_data.get('city'),
                    'state_code': address_data.get('state') or address_data.get('state_code'), 
                    'country_code': address_data.get('country') or address_data.get('country_code'),
                    'zip': address_data.get('postal_code') or address_data.get('zip'),
                    'phone': address_data.get('phone', '')
                }
                # Clean empty values
                recipient = {k: v for k, v in recipient.items() if v}
                
                api_rates = printful.calculate_shipping_rates(recipient, printful_items, currency='GBP')
                
                for rate in api_rates:
                    rates.append({
                        'id': rate.get('id'), 
                        'label': rate.get('name', rate.get('id')),
                        'detail': f"{rate.get('minDeliveryDays','?')}-{rate.get('maxDeliveryDays','?')} Days",
                        'amount': Decimal(str(rate.get('rate', '0.00')))
                    })
                
    except Exception as e:
        logger.error(f"Printful Rate Calc Failed: {e}")

    # 3. Fallback (If Printful failed or return no rates)
    if not rates:
        logger.warning("Using Fallback Shipping Rates (Printful failed or skipped)")
        subtotal = cart.get_total_price()
        country = address_data.get('country') or address_data.get('country_code')
        
        # Always add Paid Options so checkout never looks broken
        std_cost = Decimal('4.99') if country == 'GB' else Decimal('9.99')
        rates.append({
            'id': 'standard',
            'label': 'Standard Shipping',
            'detail': 'Royal Mail / International',
            'amount': std_cost
        })
        
        rates.append({
            'id': 'express',
            'label': 'Express Shipping',
            'detail': 'Priority Dispatch',
            'amount': Decimal('14.99')
        })

        # Insert Free Shipping at top if eligible
        if subtotal >= 50:
             rates.insert(0, {
                'id': 'free_shipping',
                'label': 'Free Shipping',
                'detail': 'Special Offer',
                'amount': Decimal('0.00')
             })

    # 4. Estimated Tax (Simple VAT Logic)
    tax_amount = Decimal('0.00')
    country = address_data.get('country') or address_data.get('country_code')
    if country == 'GB':
        tax_amount = cart.get_total_price() * Decimal('0.0')

    return rates, tax_amount

def calculate_cart_shipping(cart, address_data):
    """Legacy wrapper for older views."""
    rates, _ = get_shipping_rates(address_data, cart)
    # Return the amount of the first available rate
    return rates[0]['amount'] if rates else Decimal('0.00')