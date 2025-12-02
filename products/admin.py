from django.contrib import admin
from django.utils.html import format_html
from django.db.models import Sum
# Added StockItem to imports
from .models import Product, Variant, StockPool, StockItem

# =======================================================
# 1. Stock Pool Admin
# =======================================================
@admin.register(StockPool)
class StockPoolAdmin(admin.ModelAdmin):
    """Admin interface for managing shared inventory pools."""
    list_display = ('name', 'available_stock', 'low_stock_threshold')
    search_fields = ('name',)
    list_editable = ('available_stock', 'low_stock_threshold')
    fieldsets = (
        (None, {
            'fields': ('name', 'available_stock', 'low_stock_threshold'),
        }),
    )

# =======================================================
# 2. Variant Inline (Used inside Product Admin)
# =======================================================
class VariantInline(admin.TabularInline):
    model = Variant
    extra = 1
    
    # Group fields for clarity
    fieldsets = (
        (None, {
            'fields': ('name', ('color', 'size'), 'price', 'stock_pool', 'get_inventory_display', 'sku', 'printful_variant_id'),
        }),
    )
    
    # Display stock information directly in the inline
    readonly_fields = ['get_inventory_display']
    
    def get_inventory_display(self, obj):
        """Displays the inventory value from the linked StockPool."""
        inventory = obj.get_inventory()
        if obj.stock_pool and inventory <= obj.stock_pool.low_stock_threshold:
            return format_html(f'<strong style="color: orange;">{inventory}</strong>')
        elif inventory == 0:
            return format_html(f'<strong style="color: red;">0</strong>')
        return inventory
        
    get_inventory_display.short_description = 'Pool Stock'


# =======================================================
# 3. Product Admin
# =======================================================
@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    """Main interface for managing Products and their Variants."""
    inlines = [VariantInline]
    
    list_display = (
        'name', 
        'product_type', 
        'current_price_range',
        'current_stock_status',
    )
    list_filter = ('product_type',)
    search_fields = ('name', 'description')
    
    fieldsets = (
        (None, {
            'fields': ('name', 'description', 'product_type', 'featured_image'),
        }),
    )

    # Custom Admin Methods for Display

    def current_price_range(self, obj):
        """Displays the price range across all variants."""
        price_range = obj.get_price_range()
        min_p = price_range['min_price']
        max_p = price_range['max_price']
        if min_p == max_p:
            return f'£{min_p}' # Fixed currency: £
        return f'£{min_p} - £{max_p}' # Fixed currency: £
    current_price_range.short_description = 'Price'

    def current_stock_status(self, obj):
        """Displays the stock status based on the Product model logic."""
        status_data = obj.get_stock_status()
        return format_html(f'<span style="color: {status_data["color"]};">● {status_data["status"]}</span>')
        
    current_stock_status.short_description = 'Stock Status'

# =======================================================
# 4. Stock Item Admin (NEW - Fixes Staff Dashboard Error)
# =======================================================
@admin.register(StockItem)
class StockItemAdmin(admin.ModelAdmin):
    """
    Admin interface for specific StockItems (Variant + Pool link).
    Required for the 'Low Stock Alerts' link in the Staff Dashboard.
    """
    list_display = ('variant', 'pool', 'quantity', 'updated_at')
    list_filter = ('pool', 'updated_at')
    search_fields = ('variant__name', 'variant__product__name', 'pool__name')
    autocomplete_fields = ['variant', 'pool'] # Optional: improves UI if you have many products
