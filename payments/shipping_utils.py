import logging
from decimal import Decimal

logger = logging.getLogger(__name__)

# --- 1. ROYAL MAIL RATES (For 'Local' Items) ---
ROYAL_MAIL_RATES_GB = [
    (0.100, Decimal('1.65')), 
    (0.750, Decimal('3.50')), 
    (2.000, Decimal('5.50')), 
    (10.00, Decimal('9.99')), 
]

# --- 2. PRINTFUL RATES (Manual Hybrid Model) ---
PRINTFUL_RATES_GB = {
    't-shirt':  (Decimal('3.59'), Decimal('1.20')),
    'shirt':    (Decimal('3.59'), Decimal('1.20')), 
    'tank':     (Decimal('3.59'), Decimal('1.20')),
    'crop':     (Decimal('3.59'), Decimal('1.20')),
    'hoodie':   (Decimal('6.09'), Decimal('2.00')),
    'sweat':    (Decimal('6.09'), Decimal('2.00')),
    'jacket':   (Decimal('6.09'), Decimal('2.00')),
    'pant':     (Decimal('6.09'), Decimal('2.00')),
    'jogger':   (Decimal('6.09'), Decimal('2.00')),
    'legging':  (Decimal('3.59'), Decimal('1.20')),
    'bag':      (Decimal('4.99'), Decimal('1.50')),
    'tote':     (Decimal('3.59'), Decimal('1.20')),
    'hat':      (Decimal('3.29'), Decimal('1.25')),
    'beanie':   (Decimal('3.29'), Decimal('1.25')),
    'mug':      (Decimal('4.29'), Decimal('1.80')),
    'bottle':   (Decimal('4.99'), Decimal('1.90')),
    'sticker':  (Decimal('1.49'), Decimal('0.10')),
    'poster':   (Decimal('4.59'), Decimal('0.60')),
    'canvas':   (Decimal('8.99'), Decimal('4.00')),
    'default':  (Decimal('4.99'), Decimal('1.50')),
}

def get_shipping_rates(address_data, cart):
    local_items = []
    printful_items = []
    
    for item in cart.items.all():
        product = item.variant.product
        method = getattr(product, 'fulfillment_method', 'local')
        
        if method == 'digital' or product.product_type in ['digital', 'service']:
            continue
        elif method == 'printful':
            printful_items.append(item)
        else:
            local_items.append(item)

    has_physical = (len(local_items) + len(printful_items)) > 0
    if not has_physical:
        return [], Decimal('0.00')

    total_shipping = Decimal('0.00')

    if local_items:
        total_weight = sum(item.variant.weight * item.quantity for item in local_items)
        total_shipping += calculate_royal_mail_cost(total_weight)

    if printful_items:
        total_shipping += calculate_printful_manual_cost(printful_items)

    if total_shipping == 0 and has_physical:
        logger.warning("Shipping calculated to 0 for physical items. Applying fallback.")
        total_shipping = Decimal('4.99')

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
        'amount': total_shipping + Decimal('6.00')
    })

    tax_amount = Decimal('0.00')
    if address_data.get('country') == 'GB':
        tax_amount = cart.get_total_price() * Decimal('0.20')

    return rates, tax_amount


def calculate_royal_mail_cost(weight):
    if weight <= 0: weight = Decimal('0.100')
    for max_weight, price in ROYAL_MAIL_RATES_GB:
        if weight <= Decimal(str(max_weight)):
            return price
    return Decimal('15.00') 


def calculate_printful_manual_cost(items):
    all_units = []
    for item in items:
        name = item.variant.product.name.lower()
        category = 'default'
        for key in PRINTFUL_RATES_GB:
            if key in name:
                category = key
                break
        
        base_price, add_price = PRINTFUL_RATES_GB[category]
        for _ in range(item.quantity):
            all_units.append({'base': base_price, 'add': add_price})

    if not all_units:
        return Decimal('0.00')

    all_units.sort(key=lambda x: x['base'], reverse=True)
    total = all_units[0]['base']
    for unit in all_units[1:]:
        total += unit['add']

    return total

def calculate_cart_shipping(cart, address_data):
    rates, _ = get_shipping_rates(address_data, cart)
    return rates[0]['amount'] if rates else Decimal('0.00')