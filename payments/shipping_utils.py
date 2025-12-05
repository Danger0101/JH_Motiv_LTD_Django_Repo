from decimal import Decimal
from products.printful_service import PrintfulService

def calculate_cart_shipping(cart, address_data):
    """
    Calculates total shipping for a cart based on:
    1. Printful items (API quote)
    2. Self-fulfilled items (Weight-based table)
    """
    total_shipping = Decimal('0.00')
    printful_items = []
    self_fulfilled_weight = Decimal('0.00')
    
    # 1. Sort Items
    for item in cart.items.all():
        product = item.variant.product
        
        # Skip digital/coaching
        if product.product_type != 'physical':
            continue
            
        if item.variant.printful_variant_id:
            # Printful Item
            printful_items.append({
                'variant_id': item.variant.printful_variant_id,
                'quantity': item.quantity
            })
        else:
            # Self-Fulfilled: Add to weight stack
            # Default to 100g if weight is 0 to ensure cost applies
            # Ensure 'weight' exists on Variant model (see Action Item below)
            weight = getattr(item.variant, 'weight', Decimal('0.10')) 
            self_fulfilled_weight += (weight * item.quantity)

    # 2. Calculate Printful Shipping
    if printful_items and address_data:
        service = PrintfulService()
        recipient = {
            'address1': address_data.get('address1', ''),
            'city': address_data.get('city', ''),
            'country_code': address_data.get('country_code', ''),
            'state_code': address_data.get('state_code', ''),
            'zip': address_data.get('zip', ''),
        }
        
        rates = service.calculate_shipping_rates(recipient, printful_items)
        if rates:
            # Use the first available rate (usually standard/cheapest)
            rate = rates[0]
            total_shipping += Decimal(str(rate['rate']))

    # 3. Calculate Self-Fulfilled Shipping (Royal Mail Logic)
    if self_fulfilled_weight > 0:
        shipping_cost = get_weight_based_shipping_cost(self_fulfilled_weight, address_data.get('country_code'))
        total_shipping += shipping_cost

    return total_shipping

def get_weight_based_shipping_cost(weight_kg, country_code):
    """
    Simple tiered shipping based on weight (in KG).
    """
    weight = float(weight_kg)
    is_domestic = (country_code == 'GB')
    
    if is_domestic:
        if weight <= 0.1: return Decimal('1.65')  # Large Letter
        elif weight <= 0.75: return Decimal('3.50') # Small Parcel
        elif weight <= 2.0: return Decimal('5.50')  # Medium Parcel
        else: return Decimal('10.00')
    else:
        if weight <= 0.1: return Decimal('4.20')
        elif weight <= 0.75: return Decimal('10.00')
        elif weight <= 2.0: return Decimal('18.00')
        else: return Decimal('30.00')