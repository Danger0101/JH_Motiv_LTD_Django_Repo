from decimal import Decimal
from django.conf import settings
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
            # --- LOGIC FIX: Prioritize 'STANDARD' shipping ---
            # Try to find the rate with ID 'STANDARD'
            standard_rate = next((r for r in rates if r['id'] == 'STANDARD'), None)
            
            if standard_rate:
                rate_cost = standard_rate['rate']
            else:
                # Fallback: Sort by price and take the cheapest
                # Printful rates usually look like: {'id': 'DPD...', 'rate': '5.50', ...}
                sorted_rates = sorted(rates, key=lambda x: float(x['rate']))
                rate_cost = sorted_rates[0]['rate']

            total_shipping += Decimal(str(rate_cost))

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

def get_shipping_rates(address_data, cart):
    """
    Returns a list of available shipping rates based on address and cart.
    Tries Printful first, falls back to Flat Rate.
    """
    rates = []
    
    # 1. Base Logic: Physical Items Check
    physical_items = [item for item in cart.items.all() if item.variant.product.product_type == 'physical']
    if not physical_items:
        # Digital only = Free Shipping
        return [], Decimal('0.00')

    # 2. Try Printful Calculation
    try:
        printful = PrintfulService()
        # Transform cart items for Printful API
        printful_items = []
        for item in physical_items:
            # Only include if it has a linked variant ID
            if item.variant.printful_variant_id:
                printful_items.append({
                    'variant_id': item.variant.printful_variant_id,
                    'quantity': item.quantity
                })
        
        # Call API if we have valid items
        if printful_items:
            # Map Stripe address fields to Printful expected format
            recipient = {
                'address1': address_data.get('line1'),
                'address2': address_data.get('line2', ''),
                'city': address_data.get('city'),
                'state_code': address_data.get('state'), 
                'country_code': address_data.get('country'),
                'zip': address_data.get('postal_code')
            }
            
            api_rates = printful.calculate_shipping_rates(recipient, printful_items)
            
            # Format for frontend
            if api_rates:
                for rate in api_rates:
                    rates.append({
                        'id': rate.get('id'), 
                        'label': rate.get('name', rate.get('id')),
                        'detail': f"{rate.get('minDeliveryDays','?')}-{rate.get('maxDeliveryDays','?')} Days",
                        'amount': Decimal(str(rate.get('rate', '0.00')))
                    })
                
    except Exception as e:
        # Log error if needed, but proceed to fallback
        pass

    # 3. Fallback: Flat Rates (Only if Printful returned nothing)
    if not rates:
        subtotal = cart.get_total_price()
        if subtotal >= 50:
            rates.append({'id': 'free', 'label': 'Free Shipping', 'detail': '3-5 Days', 'amount': Decimal('0.00')})
        else:
            rates.append({'id': 'std', 'label': 'Standard', 'detail': '3-5 Days', 'amount': Decimal('4.99')})

    # 4. Estimated Tax (Simple VAT Logic)
    tax_amount = Decimal('0.00')
    country = address_data.get('country', '')
    
    if country == 'GB':
        # Simple VAT calculation (20% of subtotal)
        tax_amount = subtotal * Decimal('0.20')

    return rates, tax_amount