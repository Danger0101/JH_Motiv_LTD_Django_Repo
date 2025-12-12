import logging
from decimal import Decimal
from django.conf import settings
from products.printful_service import PrintfulService

logger = logging.getLogger(__name__)

# --- 1. ROYAL MAIL RATES (For 'Local' Items) ---
# Weight (KG) -> Price (GBP)
ROYAL_MAIL_RATES_GB = [
    (0.100, Decimal('1.65')), # Large Letter
    (0.750, Decimal('3.50')), # Small Parcel
    (2.000, Decimal('5.50')), # Medium Parcel
    (10.00, Decimal('9.99')), # Heavy Parcel
]

# --- 2. PRINTFUL RATES (Keys match Product.shipping_category) ---
PRINTFUL_RATES_GB = {
    't-shirt':  (Decimal('3.59'), Decimal('1.20')),
    'hoodie':   (Decimal('6.09'), Decimal('2.00')),
    'jacket':   (Decimal('6.09'), Decimal('2.00')),
    'pant':     (Decimal('6.09'), Decimal('2.00')),
    'bag':      (Decimal('4.99'), Decimal('1.50')),
    'hat':      (Decimal('3.29'), Decimal('1.25')),
    'mug':      (Decimal('4.29'), Decimal('1.80')),
    'poster':   (Decimal('4.59'), Decimal('0.60')),
    'sticker':  (Decimal('1.49'), Decimal('0.10')),
    'default':  (Decimal('4.99'), Decimal('1.50')),
}

def get_shipping_rates(address_data, cart):
    """
    Calculates shipping cost based on the Hybrid Manual Model.
    """
    local_items = []
    printful_items = []
    
    # 1. Sort items into buckets
    for item in cart.items.all():
        product = item.variant.product
        # Use the new field if updated, otherwise default to local
        method = getattr(product, 'fulfillment_method', 'local')
        
        # Completely skip Digital/Service items (No shipping cost)
        if method == 'digital' or product.product_type in ['digital', 'service']:
            continue
        elif method == 'printful':
            printful_items.append(item)
        else:
            local_items.append(item)

    # 2. Check if cart has physical items
    has_physical = (len(local_items) + len(printful_items)) > 0
    if not has_physical:
        return [], Decimal('0.00')

    total_shipping = Decimal('0.00')

    # 3. Calculate Local (Weight Based)
    if local_items:
        total_weight = sum(item.variant.weight * item.quantity for item in local_items)
        total_shipping += calculate_royal_mail_cost(total_weight)

    # 4. Calculate Printful (Base + Extra)
    if printful_items:
        total_shipping += calculate_printful_manual_cost(printful_items)

    # 5. SAFETY CHECK: Never return 0.00 for physical goods
    if total_shipping == 0 and has_physical:
        logger.warning("Shipping calculated to 0 for physical items. Applying fallback.")
        total_shipping = Decimal('4.99')

    # 6. Generate Options
    rates = []
    
    rates.append({
        'id': 'standard',
        'label': 'Standard Shipping',
        'detail': 'Royal Mail / Courier (3-5 Days)',
        'amount': total_shipping
    })
    
    rates.append({
        'id': 'express',
        'label': 'Express / Priority',
        'detail': 'Tracked & Prioritized (1-3 Days)',
        'amount': total_shipping + Decimal('6.00') # Fixed surcharge
    })

    # 7. Tax (Estimated VAT 20% for UK)
    tax_amount = Decimal('0.00')
    if address_data.get('country') == 'GB':
        tax_amount = cart.get_total_price() * Decimal('0.20')

    return rates, tax_amount


def calculate_royal_mail_cost(weight):
    """Returns price based on weight tier."""
    if weight <= 0: weight = Decimal('0.100')
    
    for max_weight, price in ROYAL_MAIL_RATES_GB:
        if weight <= Decimal(str(max_weight)):
            return price
    return Decimal('15.00') # Heavy fallback


def calculate_printful_manual_cost(items):
    """
    Logic: The single item with the HIGHEST Base Price pays that Base Price.
    EVERY other item (including subsequent qty of the first item) pays its 'Additional' price.
    """
    all_units = []

    # Flatten the cart into individual units
    for item in items:
        # LOOKUP from Database Field
        category = getattr(item.variant.product, 'shipping_category', 'default')
        
        if category not in PRINTFUL_RATES_GB:
            category = 'default'
            
        base_price, add_price = PRINTFUL_RATES_GB[category]
        
        # Add 1 unit for every quantity
        for _ in range(item.quantity):
            all_units.append({
                'base': base_price,
                'add': add_price
            })

    if not all_units:
        return Decimal('0.00')

    # Sort units by Base Price descending (Highest first)
    all_units.sort(key=lambda x: x['base'], reverse=True)

    # 1st Item pays Base
    total = all_units[0]['base']

    # Remaining items pay Additional
    for unit in all_units[1:]:
        total += unit['add']

    return total

def calculate_cart_shipping(cart, address_data):
    """Wrapper used by older views/services."""
    rates, _ = get_shipping_rates(address_data, cart)
    return rates[0]['amount'] if rates else Decimal('0.00')