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

# --- 1b. ROYAL MAIL RATES (Rest of World) ---
ROYAL_MAIL_RATES_ROW = [
    (0.100, Decimal('4.50')), 
    (0.750, Decimal('10.50')), 
    (2.000, Decimal('19.00')), 
    (10.00, Decimal('40.00')), 
]

EU_COUNTRIES = {
    'AT', 'BE', 'BG', 'HR', 'CY', 'CZ', 'DK', 'EE', 'FI', 'FR', 'DE', 'GR', 'HU', 'IE', 'IT', 'LV', 'LT', 'LU', 'MT', 'NL', 'PL', 'PT', 'RO', 'SK', 'SI', 'ES', 'SE'
}

FREE_SHIPPING_THRESHOLD = Decimal('50.00')

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

# --- 2b. PRINTFUL RATES (Rest of World) ---
PRINTFUL_RATES_ROW = {
    't-shirt':  (Decimal('6.99'), Decimal('1.50')),
    'shirt':    (Decimal('6.99'), Decimal('1.50')), 
    'tank':     (Decimal('6.99'), Decimal('1.50')),
    'crop':     (Decimal('6.99'), Decimal('1.50')),
    'hoodie':   (Decimal('10.99'), Decimal('2.50')),
    'sweat':    (Decimal('10.99'), Decimal('2.50')),
    'jacket':   (Decimal('10.99'), Decimal('2.50')),
    'pant':     (Decimal('10.99'), Decimal('2.50')),
    'jogger':   (Decimal('10.99'), Decimal('2.50')),
    'legging':  (Decimal('6.99'), Decimal('1.50')),
    'bag':      (Decimal('8.99'), Decimal('2.00')),
    'tote':     (Decimal('6.99'), Decimal('1.50')),
    'hat':      (Decimal('6.99'), Decimal('1.50')),
    'beanie':   (Decimal('6.99'), Decimal('1.50')),
    'mug':      (Decimal('7.99'), Decimal('2.50')),
    'bottle':   (Decimal('8.99'), Decimal('2.50')),
    'sticker':  (Decimal('2.99'), Decimal('0.20')),
    'poster':   (Decimal('7.99'), Decimal('1.00')),
    'canvas':   (Decimal('15.99'), Decimal('5.00')),
    'default':  (Decimal('8.99'), Decimal('2.00')),
}

def calculate_batch_cost(items, country_code='GB'):
    """Calculates shipping cost for a specific list of items."""
    local_items = []
    printful_items = []
    
    for item in items:
        product = item.variant.product
        method = getattr(product, 'fulfillment_method', 'local')
        
        if method == 'printful':
            printful_items.append(item)
        else:
            local_items.append(item)

    cost = Decimal('0.00')
    
    if local_items:
        total_weight = sum(item.variant.weight * item.quantity for item in local_items)
        cost += calculate_royal_mail_cost(total_weight, country_code)
        
    if printful_items:
        cost += calculate_printful_manual_cost(printful_items, country_code)
        
    return cost

def get_shipping_rates(address_data, cart):
    # 1. Identify all physical items (to determine if shipping applies at all)
    all_physical_items = [
        item for item in cart.items.all()
        if item.variant.product.product_type not in ['digital', 'service'] 
        and item.variant.product.fulfillment_method != 'digital'
    ]

    if not all_physical_items:
        return [], Decimal('0.00')

    # 2. Filter for items that actually cost money to ship
    dest_country = address_data.get('country', 'GB')
    chargeable_items = []
    for item in all_physical_items:
        if not item.variant.product.shipping_included:
            chargeable_items.append(item)
        else:
            # Shipping included only applies to GB and EU
            if dest_country == 'GB' or dest_country in EU_COUNTRIES:
                continue
            else:
                chargeable_items.append(item)

    # 3. Split into shipments (Immediate vs Preorder)
    immediate_items = [i for i in chargeable_items if not i.variant.product.is_preorder]
    preorder_items = [i for i in chargeable_items if i.variant.product.is_preorder]
    
    # 4. Calculate cost for each batch separately (Split Shipment Logic)
    # This naturally charges "extra" because base fees apply to both batches.
    total_shipping = calculate_batch_cost(immediate_items, dest_country) + calculate_batch_cost(preorder_items, dest_country)

    # 5. Fallback / Safety Net
    # Only apply fallback if we have chargeable items but cost is 0 (e.g. missing weights)
    # Do NOT apply if cost is 0 because everything is "shipping_included"
    if total_shipping == 0 and chargeable_items:
        logger.warning("Shipping calculated to 0 for chargeable physical items. Applying fallback.")
        total_shipping = Decimal('4.99')

    # --- COUPON OVERRIDE: FREE SHIPPING ---
    # If the applied coupon allows free shipping, we force the base rate to 0.00
    if cart.coupon and cart.coupon.free_shipping:
        total_shipping = Decimal('0.00')
    
    # --- FREE SHIPPING THRESHOLD ---
    elif cart.get_total_price() >= FREE_SHIPPING_THRESHOLD:
        total_shipping = Decimal('0.00')

    # Determine Label
    shipping_label = 'Standard Shipping'
    if total_shipping == 0 and (
        (cart.coupon and cart.coupon.free_shipping) or 
        (all_physical_items and not chargeable_items)
    ):
        shipping_label = 'Free Shipping'

    rates = []
    # Option 1: Standard (Lowest)
    # This will be £0.00 if the coupon is active
    rates.append({
        'id': 'standard',
        'label': shipping_label,
        'detail': 'Royal Mail / Courier (3-5 Days)',
        'amount': total_shipping
    })
    
    # Option 2: Express
    # If coupon is active, this becomes just the upgrade fee (£6.00)
    rates.append({
        'id': 'express',
        'label': 'Express / Priority',
        'detail': 'Tracked & Prioritized (1-3 Days)',
        'amount': total_shipping + Decimal('6.00')
    })

    tax_amount = Decimal('0.00')
    if address_data.get('country') == 'GB':
        tax_amount = cart.get_total_price() * Decimal('0.00')

    return rates, tax_amount


def calculate_royal_mail_cost(weight, country_code='GB'):
    if weight <= 0: weight = Decimal('0.100')
    
    rates = ROYAL_MAIL_RATES_GB
    fallback = Decimal('15.00')
    
    if country_code != 'GB':
        rates = ROYAL_MAIL_RATES_ROW
        fallback = Decimal('45.00')

    for max_weight, price in rates:
        if weight <= Decimal(str(max_weight)):
            return price
    return fallback


def calculate_printful_manual_cost(items, country_code='GB'):
    rates_source = PRINTFUL_RATES_GB
    if country_code != 'GB':
        rates_source = PRINTFUL_RATES_ROW

    all_units = []
    for item in items:
        name = item.variant.product.name.lower()
        category = 'default'
        for key in rates_source:
            if key in name:
                category = key
                break
        
        base_price, add_price = rates_source.get(category, rates_source['default'])
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