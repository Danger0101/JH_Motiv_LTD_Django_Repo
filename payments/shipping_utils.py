import logging
from decimal import Decimal

logger = logging.getLogger(__name__)

# --- MANUAL RATES CONFIGURATION ---

# Royal Mail Tiers (Weight in KG -> Price in GBP)
ROYAL_MAIL_RATES_GB = [
    (0.100, Decimal('1.65')), # Large Letter
    (0.750, Decimal('3.50')), # Small Parcel
    (2.000, Decimal('5.50')), # Medium Parcel
    (10.00, Decimal('9.99')), # Heavy Parcel
]

# Printful Manual Rates (Approximate Base Costs)
# Format: 'Category Keyword': (Base Price, Additional Price)
PRINTFUL_RATES_GB = {
    'shirt':    (Decimal('3.69'), Decimal('1.25')),
    'hoodie':   (Decimal('6.09'), Decimal('2.00')),
    'sweat':    (Decimal('6.09'), Decimal('2.00')),
    'bag':      (Decimal('4.99'), Decimal('1.50')),
    'mug':      (Decimal('4.29'), Decimal('1.80')),
    'hat':      (Decimal('3.29'), Decimal('1.25')),
    'beanie':   (Decimal('3.29'), Decimal('1.25')),
    'poster':   (Decimal('4.59'), Decimal('0.60')),
    'default':  (Decimal('4.99'), Decimal('1.50')),
}

def get_shipping_rates(address_data, cart):
    """
    Calculates shipping options manually.
    Returns: List of rate options, Tax amount
    """
    local_items = []
    printful_items = []
    
    # 1. Bucket Items
    for item in cart.items.all():
        product = item.variant.product
        # Use the new field if it exists, otherwise guess based on type
        method = getattr(product, 'fulfillment_method', 'local')
        
        # Skip digital services
        if method == 'digital' or product.product_type in ['digital', 'service']:
            continue
        elif method == 'printful':
            printful_items.append(item)
        else:
            # Local / Manual Stock
            local_items.append(item)

    # If cart has items but no physical ones (all digital/coaching)
    if not local_items and not printful_items and cart.items.exists():
        return [], Decimal('0.00')

    total_shipping = Decimal('0.00')

    # 2. Calculate Local Cost (Weight Based)
    if local_items:
        total_weight = sum(item.variant.weight * item.quantity for item in local_items)
        total_shipping += calculate_royal_mail_cost(total_weight)

    # 3. Calculate Printful Cost (Base + Additional)
    if printful_items:
        total_shipping += calculate_printful_manual_cost(printful_items)

    # 4. Define Options
    rates = []
    
    # Standard Option
    rates.append({
        'id': 'standard',
        'label': 'Standard Shipping',
        'detail': 'Royal Mail / Courier (3-5 Days)',
        'amount': total_shipping
    })
    
    # Express Option (Standard + Surcharge)
    rates.append({
        'id': 'express',
        'label': 'Express / Priority',
        'detail': 'Tracked & Prioritized (1-3 Days)',
        'amount': total_shipping + Decimal('6.00') # £6 surcharge for Express
    })

    # 5. Tax (Estimated)
    tax_amount = Decimal('0.00')
    if address_data.get('country') == 'GB':
        tax_amount = cart.get_total_price() * Decimal('0.20')

    return rates, tax_amount


def calculate_royal_mail_cost(weight):
    """Finds the correct tier for the total weight."""
    for max_weight, price in ROYAL_MAIL_RATES_GB:
        if weight <= Decimal(str(max_weight)):
            return price
    return Decimal('15.00') # Fallback for very heavy items


def calculate_printful_manual_cost(items):
    """
    Calculates cost using Highest Base + (Rest * Additional).
    """
    base_costs = []
    
    # Flatten items into a list of costs
    # e.g. 2 Shirts = [Base_Shirt, Add_Shirt]
    all_unit_costs = []

    for item in items:
        # Identify Category
        name = item.variant.product.name.lower()
        category = 'default'
        for key in PRINTFUL_RATES_GB:
            if key in name:
                category = key
                break
        
        base_price, add_price = PRINTFUL_RATES_GB[category]
        
        # Add to pool
        for _ in range(item.quantity):
            all_unit_costs.append({
                'base': base_price,
                'add': add_price
            })

    if not all_unit_costs:
        return Decimal('0.00')

    # Sort so the most expensive BASE price is first
    all_unit_costs.sort(key=lambda x: x['base'], reverse=True)

    # First item pays Base price
    total = all_unit_costs[0]['base']

    # All subsequent items pay their Additional price
    for unit in all_unit_costs[1:]:
        total += unit['add']

    return total

def calculate_cart_shipping(cart, address_data):
    """Wrapper for backward compatibility."""
    rates, _ = get_shipping_rates(address_data, cart)
    return rates[0]['amount'] if rates else Decimal('0.00')