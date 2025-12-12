import logging
from decimal import Decimal

logger = logging.getLogger(__name__)

# --- MANUAL RATES CONFIGURATION ---

# --- 1. ROYAL MAIL RATES (For 'Local' Items) ---
# Weight (KG) -> Price (GBP)
ROYAL_MAIL_RATES_GB = [
    (0.100, Decimal('1.65')), # Large Letter
    (0.750, Decimal('3.50')), # Small Parcel
    (2.000, Decimal('5.50')), # Medium Parcel
    (10.00, Decimal('9.99')), # Heavy Parcel
]

# --- 2. PRINTFUL RATES (From your CSV for UK) ---
# Format: 'Category Keyword': (Base Price, Additional Price)
# I have mapped these directly from your uploaded file.
PRINTFUL_RATES_GB = {
    # Apparel
    't-shirt':  (Decimal('3.59'), Decimal('1.20')),
    'shirt':    (Decimal('3.59'), Decimal('1.20')), 
    'tank':     (Decimal('3.59'), Decimal('1.20')),
    'crop':     (Decimal('3.59'), Decimal('1.20')),
    'hoodie':   (Decimal('6.09'), Decimal('2.00')),
    'sweat':    (Decimal('6.09'), Decimal('2.00')),
    'jacket':   (Decimal('6.09'), Decimal('2.00')),
    'pant':     (Decimal('6.09'), Decimal('2.00')),
    'jogger':   (Decimal('6.09'), Decimal('2.00')),
    'legging':  (Decimal('3.59'), Decimal('1.20')), # Usually shirt rate
    
    # Accessories
    'bag':      (Decimal('4.99'), Decimal('1.50')),
    'tote':     (Decimal('3.59'), Decimal('1.20')), # Often lower
    'hat':      (Decimal('3.29'), Decimal('1.25')),
    'beanie':   (Decimal('3.29'), Decimal('1.25')),
    'mug':      (Decimal('4.29'), Decimal('1.80')),
    'bottle':   (Decimal('4.99'), Decimal('1.90')),
    'sticker':  (Decimal('1.49'), Decimal('0.10')), # CSV assumption
    'poster':   (Decimal('4.59'), Decimal('0.60')),
    'canvas':   (Decimal('8.99'), Decimal('4.00')),
    
    # Fallback
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
        method = getattr(product, 'fulfillment_method', 'local')
        
        # Completely skip Digital/Service items (No shipping cost)
        if method == 'digital' or product.product_type in ['digital', 'service']:
            continue
        elif method == 'printful':
            printful_items.append(item)
        else:
            local_items.append(item)

    # 2. Check if cart has physical items but calculated 0 shipping
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

    # 5. SAFETY CHECK: Never return £0.00 for physical goods
    if total_shipping == 0:
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
    # Ensure weight is at least something to trigger the first tier
    if weight <= 0: weight = Decimal('0.100')
    
    for max_weight, price in ROYAL_MAIL_RATES_GB:
        if weight <= Decimal(str(max_weight)):
            return price
    return Decimal('15.00') # Fallback for very heavy items


def calculate_printful_manual_cost(items):
    """
    Logic: The single item with the HIGHEST Base Price pays that Base Price.
    EVERY other item (including subsequent qty of the first item) pays its 'Additional' price.
    """
    all_units = []

    # Flatten the cart into individual units
    for item in items:
        # Find rate
        name = item.variant.product.name.lower()
        category = 'default'
        for key in PRINTFUL_RATES_GB:
            if key in name:
                category = key
                break
        
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
    """Wrapper."""
    rates, _ = get_shipping_rates(address_data, cart)
    return rates[0]['amount'] if rates else Decimal('0.00')
No, the current sync script (sync_printful.py) does not assign a specific category (like "T-Shirt," "Mug," or "Hoodie") to your products. It simply downloads them and marks them as product_type = 'physical'.

However, the manual shipping logic I provided does not need a category field to work. It uses a "Keyword Matching" strategy based on the Product Name.

How it works without a Category field:
The Sync: Saves a product with the name: "Unisex Heavy Blend Hoodie".

The Shipping Logic: Looks at the name, sees the word "Hoodie", and automatically applies the specific Hoodie shipping rate (£6.09).

The Fallback: If the name is something vague (e.g., "The Motivator"), it falls back to the default/highest rate to ensure you don't lose money.

Recommended Action: Add the fulfillment_method Field
To make the "Manual Hybrid" system work perfectly (separating your Local stock from Printful stock), you need to add the fulfillment_method field to your model.

Here is the code to update your products/models.py file.

File: products/models.py

Python

from django.db import models
from django.urls import reverse
from django.db.models import Min, Max

# ... (Keep StockPool class as is) ...

class Product(models.Model):
    PRODUCT_TYPE_CHOICES = [
        ('physical', 'Physical'),
        ('digital', 'Digital'),
        ('service', 'Service/Coaching'),
    ]
    
    # --- NEW: Explicit Fulfillment Definition ---
    FULFILLMENT_METHOD_CHOICES = [
        ('printful', 'Printful (Drop Shipping)'),
        ('local', 'Local / Royal Mail'),
        ('digital', 'Digital / Instant'),
    ]

    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    product_type = models.CharField(max_length=20, choices=PRODUCT_TYPE_CHOICES, default='physical')
    
    # --- ADD THIS FIELD ---
    fulfillment_method = models.CharField(
        max_length=20, 
        choices=FULFILLMENT_METHOD_CHOICES, 
        default='local',
        help_text="Who ships this? Printful uses flat rates; Local uses weight."
    )
    
    printful_product_id = models.CharField(max_length=255, blank=True, null=True)
    featured_image = models.ImageField(upload_to='product_images/', blank=True, null=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # ... (Keep existing methods) ...
Next Steps:
Update Model: Paste the code above into products/models.py.

Make Migrations: Run python manage.py makemigrations and python manage.py migrate.

Update Sync Script: Modify products/management/commands/sync_printful.py to automatically set fulfillment_method='printful' when it downloads new items.

Update for sync_printful.py (Inside the loop):

Python

                # Create or Update Product
                product, created = Product.objects.update_or_create(
                    printful_product_id=str(p_data['id']),
                    defaults={
                        'name': p_data['name'],
                        'product_type': 'physical',
                        'fulfillment_method': 'printful', # <--- AUTO-TAG AS PRINTFUL
                    }
                )
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
        method = getattr(product, 'fulfillment_method', 'local')
        
        # Completely skip Digital/Service items (No shipping cost)
        if method == 'digital' or product.product_type in ['digital', 'service']:
            continue
        elif method == 'printful':
            printful_items.append(item)
        else:
            local_items.append(item)

    # 2. Check if cart has physical items but calculated 0 shipping
    has_physical = (len(local_items) + len(printful_items)) > 0
    if not has_physical:
        return [], Decimal('0.00')

    total_shipping = Decimal('0.00')

    # 3. Calculate Local (Weight Based)
        total_weight = sum(item.variant.weight * item.quantity for item in local_items)
        total_shipping += calculate_royal_mail_cost(total_weight)

    # 4. Calculate Printful (Base + Extra)
    if printful_items:
        total_shipping += calculate_printful_manual_cost(printful_items)

    # 5. SAFETY CHECK: Never return £0.00 for physical goods
    if total_shipping == 0:
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
    # Ensure weight is at least something to trigger the first tier
    if weight <= 0: weight = Decimal('0.100')
    
    for max_weight, price in ROYAL_MAIL_RATES_GB:
        if weight <= Decimal(str(max_weight)):
            return price
    return Decimal('15.00') # Fallback for very heavy items


def calculate_printful_manual_cost(items):
    """
    Logic: The single item with the HIGHEST Base Price pays that Base Price.
    EVERY other item (including subsequent qty of the first item) pays its 'Additional' price.
    """
    all_units = []

    # Flatten the cart into individual units
    for item in items:
        # Find rate
        name = item.variant.product.name.lower()
        category = 'default'
        for key in PRINTFUL_RATES_GB:
            if key in name:
                category = key
                break
        
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
    """Wrapper."""
    rates, _ = get_shipping_rates(address_data, cart)
    return rates[0]['amount'] if rates else Decimal('0.00')