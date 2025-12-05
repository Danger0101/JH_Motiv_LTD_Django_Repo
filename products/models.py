from django.db import models
from django.urls import reverse
from django.db.models import Min, Max, Sum

# =========================================================================
# NEW: StockPool Model for Modular Inventory
# =========================================================================

class StockPool(models.Model):
    """
    Manages a centralized pool of inventory shared across one or more Variants.
    Removes the need for individual Variant inventory counts.
    """
    name = models.CharField(max_length=100, unique=True, help_text="e.g., 'White T-Shirt Blanks'")
    available_stock = models.PositiveIntegerField(default=0)
    low_stock_threshold = models.PositiveIntegerField(default=10)

    def is_in_stock(self, quantity=1):
        """Checks if the stock pool has enough available units."""
        return self.available_stock >= quantity

    def __str__(self):
        return f"{self.name} ({self.available_stock} available)"

# =========================================================================
# Product Model Updates
# =========================================================================

class Product(models.Model):
    PRODUCT_TYPE_CHOICES = [
        ('physical', 'Physical'),
        ('digital', 'Digital'),
    ]
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    product_type = models.CharField(max_length=20, choices=PRODUCT_TYPE_CHOICES)
    printful_product_id = models.CharField(max_length=255, blank=True, null=True, help_text="ID from Printful Sync Product")
    featured_image = models.ImageField(upload_to='product_images/', blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse('products:product_detail', kwargs={'pk': self.pk})

    def get_price_range(self):
        return self.variants.aggregate(min_price=Min('price'), max_price=Max('price'))

    def get_stock_status(self):
        """
        Calculates the overall stock status based on the minimum stock
        available in all linked StockPools.
        """
        # Get the 'available_stock' for all unique StockPools linked to this product's variants
        pool_stocks = self.variants.filter(stock_pool__isnull=False) \
                                   .values_list('stock_pool__available_stock', flat=True) \
                                   .distinct()
        
        if not pool_stocks:
            return {'status': 'N/A', 'color': 'gray', 'count': None}
            
        # The product is limited by the pool with the minimum stock
        min_stock = min(pool_stocks) if pool_stocks else 0
        
        if min_stock > 20:
            return {'status': 'In Stock', 'color': 'green', 'count': min_stock}
        elif 1 <= min_stock <= 20:
            return {'status': 'Low Stock', 'color': 'orange', 'count': min_stock}
        else:
            return {'status': 'Out of Stock', 'color': 'red', 'count': 0}

# =========================================================================
# Variant Model Updates
# =========================================================================

class Variant(models.Model):
    product = models.ForeignKey(Product, related_name='variants', on_delete=models.CASCADE)
    name = models.CharField(max_length=255, blank=True)
    sku = models.CharField(max_length=100, unique=True, blank=True, null=True)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    
    # --- CHANGE 1: REMOVE old 'inventory' field ---
    # inventory = models.PositiveIntegerField(default=0) 
    
    # --- CHANGE 2: ADD ForeignKey to StockPool ---
    stock_pool = models.ForeignKey(
        StockPool, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        help_text="Select the shared pool of inventory this variant uses."
    )
    
    printful_variant_id = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    # Variant Option Fields (as requested) ---
    size = models.CharField(max_length=20, blank=True)
    color = models.CharField(max_length=50, blank=True)

    # --- NEW: Weight for Self-Fulfilled Shipping ---
    weight = models.DecimalField(
        max_digits=8, 
        decimal_places=2, 
        default=0.00, 
        help_text="Weight in grams (g). Required for self-fulfilled shipping calculation."
    )
    
    def get_image_url():
        """Returns the URL of the product's featured image for cart display."""
        if self.product.featured_image:
            return self.product.featured_image.url
        return 'https://via.placeholder.com/500'

    def get_inventory(self):
        """Returns the inventory from the linked StockPool."""
        return self.stock_pool.available_stock if self.stock_pool else 0

    def is_available(self, quantity=1):
        """
        Checks if the variant is available.
        - Digital products are always available.
        - Physical products depend on the linked StockPool.
        """
        if self.product.product_type == 'digital':
            return True
        return self.stock_pool.is_in_stock(quantity) if self.stock_pool else False

    def __str__(self):
        # Default name if not explicitly set
        if self.name:
            return f"{self.product.name} - {self.name}"
        return f"{self.product.name} - {self.color} / {self.size}"

    # Ensure uniqueness across product options (e.g., only one Large/Red variant per product)
    class Meta:
        unique_together = ('product', 'color', 'size')

# =========================================================================
# NEW: StockItem Model (Add this at the end of the file)
# =========================================================================

class StockItem(models.Model):
    """
    Represents the specific inventory connection between a Variant and a StockPool.
    This allows tracking the actual quantity of items.
    """
    variant = models.ForeignKey(
        'Variant',  # Use string reference to avoid circular import issues
        on_delete=models.CASCADE,
        related_name='stock_items'
    )
    pool = models.ForeignKey(
        'StockPool',
        on_delete=models.CASCADE,
        related_name='stock_items'
    )
    quantity = models.PositiveIntegerField(default=0)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('variant', 'pool')
        verbose_name = "Stock Item"
        verbose_name_plural = "Stock Items"

    def __str__(self):
        return f"{self.variant} in {self.pool} ({self.quantity})"