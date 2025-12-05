from decimal import Decimal
from django.conf import settings
from products.printful_service import PrintfulService

def calculate_cart_shipping(cart, address_data):
    """
    Calculates total shipping for a cart based on:
    1. Printful items (API quote)
    2. Self-fulfilled items (Weight-based table)
    3. Digital items (Free)
    """
    total_shipping = Decimal('0.00')
    printful_items = []
    self_fulfilled_weight = 0
    
    # 1. Sort Items
    for item in cart.items.all():
        product = item.variant.product
        
        # Skip digital products/Coaching
        if product.product_type != 'physical':
            continue
            
        if item.variant.printful_variant_id:
            # It's a Printful Item
            printful_items.append({
                'variant_id': item.variant.printful_variant_id,
                'quantity': item.quantity
            })
        else:
            # It's Self-Fulfilled - Add to weight stack
            # Default to 100g if weight is 0 to ensure some shipping cost applies
            item_weight = item.variant.weight if item.variant.weight > 0 else Decimal('100.00')
            self_fulfilled_weight += (item_weight * item.quantity)

    # 2. Calculate Printful Shipping
    if printful_items and address_data:
        service = PrintfulService()
        # Ensure address has minimum required fields for calculation
        recipient = {
            'address1': address_data.get('line1', ''),
            'city': address_data.get('city', ''),
            'country_code': address_data.get('country', ''),
            'state_code': address_data.get('state', ''),
            'zip': address_data.get('postal_code', ''),
        }
        
        rates = service.calculate_shipping_rates(recipient, printful_items)
        if rates:
            # Find 'STANDARD' rate or default to the first one
            rate = next((r for r in rates if r['id'] == 'STANDARD'), rates[0])
            total_shipping += Decimal(str(rate['rate']))

    # 3. Calculate Self-Fulfilled Shipping (Royal Mail logic)
    if self_fulfilled_weight > 0:
        shipping_cost = get_weight_based_shipping_cost(self_fulfilled_weight, address_data.get('country'))
        total_shipping += shipping_cost

    return total_shipping

def get_weight_based_shipping_cost(weight_grams, country_code):
    """
    Simple tiered shipping based on weight.
    Mimics Royal Mail Letters/Parcels.
    """
    # Convert Decimal to float for comparison if needed, or keep Decimal
    weight = float(weight_grams)
    
    # Base rates (GBP) - You can move these to settings.py
    # Example: Royal Mail 1st Class / International Standard
    is_international = country_code != 'GB'
    
    if weight <= 100: # Large Letter
        return Decimal('4.20') if is_international else Decimal('1.65')
    elif weight <= 750: # Small Parcel
        return Decimal('10.00') if is_international else Decimal('3.50')
    elif weight <= 2000: # Medium Parcel
        return Decimal('18.00') if is_international else Decimal('5.50')
    else: # Large Parcel / Courier
        return Decimal('30.00') if is_international else Decimal('10.00')