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
    physical_items = [item for item in cart.items.all() if item.variant.product.product_type == 'physical']
    
    if not physical_items:
        return [], Decimal('0.00')

    # 2. Try Printful Calculation
    try:
        printful = PrintfulService()
        printful_items = []
        for item in physical_items:
            if item.variant.printful_variant_id:
                printful_items.append({
                    'variant_id': item.variant.printful_variant_id,
                    'quantity': item.quantity
                })
        
        if printful_items:
            # Map Stripe address fields to Printful expected format
            # Handles both Stripe Elements ('line1') and legacy/manual forms ('address1')
            recipient = {
                'address1': address_data.get('line1') or address_data.get('address1'),
                'address2': address_data.get('line2') or address_data.get('address2', ''),
                'city': address_data.get('city'),
                'state_code': address_data.get('state') or address_data.get('state_code'), 
                'country_code': address_data.get('country') or address_data.get('country_code'),
                'zip': address_data.get('postal_code') or address_data.get('zip')
            }
            
            # Filter out empty values to comply with API optional fields
            recipient = {k: v for k, v in recipient.items() if v}
            
            logger.info(f"Requesting Printful Rates. Recipient: {recipient}, Items: {printful_items}")
            
            api_rates = printful.calculate_shipping_rates(recipient, printful_items, currency='GBP')
            
            if api_rates:
                for rate in api_rates:
                    rates.append({
                        'id': rate.get('id'), 
                        'label': rate.get('name', rate.get('id')),
                        'detail': f"{rate.get('minDeliveryDays','?')}-{rate.get('maxDeliveryDays','?')} Days",
                        'amount': Decimal(str(rate.get('rate', '0.00')))
                    })
                
    except Exception as e:
        logger.error(f"Printful API Error: {e}", exc_info=True)

    # 3. Fallback: Flat Rates (Only if Printful returned nothing)
    if not rates:
        subtotal = cart.get_total_price()
        
        # Determine delivery estimates based on country
        country_code = address_data.get('country') or address_data.get('country_code')
        
        if country_code in ['US', 'CA']:
            std_detail = 'Standard (3-4 Business Days)'
            exp_detail = 'Express (1-3 Business Days)'
        elif country_code == 'GB':
            std_detail = 'Standard (3-7 Business Days)'
            exp_detail = 'Express (1-3 Business Days)'
        else:
            std_detail = 'Standard (5-20 Business Days)'
            exp_detail = 'Express (1-3 Business Days)'

        if subtotal >= 50:
            rates.append({
                'id': 'free_shipping',
                'label': 'Free Shipping',
                'detail': std_detail,
                'amount': Decimal('0.00')
            })
        else:
            rates.append({
                'id': 'standard',
                'label': 'Standard Shipping',
                'detail': std_detail,
                'amount': Decimal('4.99')
            })
            rates.append({
                'id': 'express',
                'label': 'Express Shipping',
                'detail': exp_detail,
                'amount': Decimal('9.99')
            })

    # 4. Estimated Tax (Simple VAT Logic)
    tax_amount = Decimal('0.00')
    country = address_data.get('country') or address_data.get('country_code')
    
    if country == 'GB':
        # VAT Nor Needed for now
        tax_amount = cart.get_total_price() * Decimal('0.0')
        # VAT Once Needed
        # tax_amount = cart.get_total_price() * Decimal('0.20')

    return rates, tax_amount

def calculate_cart_shipping(cart, address_data):
    """
    Wrapper for backward compatibility. Returns the amount of the first available rate.
    """
    rates, _ = get_shipping_rates(address_data, cart)
    return rates[0]['amount'] if rates else Decimal('0.00')