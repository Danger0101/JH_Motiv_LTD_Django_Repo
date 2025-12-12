import logging
from decimal import Decimal
from django.conf import settings
from products.printful_service import PrintfulService

logger = logging.getLogger(__name__)

def get_shipping_rates(address_data, cart):
    """
    Returns a list of shipping rates and a tax estimate based on the address.
    """
    rates = []
    
    # 1. Filter for Physical Items
    physical_items = [item for item in cart.items.all() if getattr(item.variant.product, 'product_type', 'physical') == 'physical']
    
    if not physical_items:
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
                    'address1': address_data.get('line1'),
                    'address2': address_data.get('line2', ''),
                    'city': address_data.get('city'),
                    'state_code': address_data.get('state'), 
                    'country_code': address_data.get('country'),
                    'zip': address_data.get('postal_code'),
                    'phone': address_data.get('phone', '') # Capture phone if available
                }
                
                api_rates = printful.calculate_shipping_rates(recipient, printful_items, currency='GBP')
                
                for rate in api_rates:
                    rates.append({
                        'id': rate.get('id'), 
                        'label': rate.get('name', rate.get('id')),
                        'detail': f"{rate.get('minDeliveryDays','?')}-{rate.get('maxDeliveryDays','?')} Days",
                        'amount': Decimal(str(rate.get('rate', '0.00')))
                    })
                
    except Exception as e:
        logger.error(f"Printful Rate Error: {e}")

    # 3. Fallback: Flat Rates (Only if Printful returned nothing)
    if not rates:
        subtotal = cart.get_total_price()
        country = address_data.get('country')
        
        if subtotal >= 50:
            rates.append({
                'id': 'free_shipping',
                'label': 'Free Shipping',
                'detail': '3-5 Days',
                'amount': Decimal('0.00')
            })
        else:
            cost = Decimal('4.99') if country == 'GB' else Decimal('9.99')
            rates.append({
                'id': 'standard',
                'label': 'Standard Shipping',
                'detail': 'Royal Mail / International',
                'amount': cost
            })

    # 4. Estimated Tax (Simple VAT Logic)
    tax_amount = Decimal('0.00')
    if address_data.get('country') == 'GB':
        # Example: 20% VAT
        tax_amount = cart.get_total_price() * Decimal('0.20')

    return rates, tax_amount

def calculate_cart_shipping(cart, address_data):
    """
    Wrapper for backward compatibility or simple totals.
    Returns the cost of the first/cheapest available rate.
    """
    rates, _ = get_shipping_rates(address_data, cart)
    if rates:
        # Sort by amount to find cheapest
        cheapest = sorted(rates, key=lambda x: x['amount'])[0]
        return cheapest['amount']
    return Decimal('0.00')