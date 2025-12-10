from django.contrib import admin
from django.utils.html import format_html
from django.db.models import Min, Max, Sum, Count
# Added StockItem to imports
from .models import Product, Variant, StockPool, StockItem

# =======================================================
# 1. Stock Pool Admin
# =======================================================
@admin.register(StockPool)
class StockPoolAdmin(admin.ModelAdmin):
    """Admin interface for managing shared inventory pools."""
    list_display = ('name', 'available_stock', 'low_stock_threshold', 'is_low_stock')
    search_fields = ('name',)
    list_editable = ('available_stock',)
    fieldsets = (
        (None, {
            'fields': ('name', 'available_stock', 'low_stock_threshold'),
        }),
    )

    @admin.display(boolean=True, description='Low Stock?')
    def is_low_stock(self, obj):
        return obj.available_stock <= obj.low_stock_threshold

# =======================================================
# 2. Variant Inline (Used inside Product Admin)
# =======================================================
class VariantInline(admin.TabularInline):
    model = Variant
    extra = 0 # Cleaner UI, use 'Add another' if needed
    fields = ('name', 'color', 'size', 'price', 'weight', 'sku', 'stock_pool', 'printful_variant_id')
    
    # Optimization: link stock_pool lookup
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('stock_pool')


# =======================================================
# 3. Product Admin
# =======================================================
@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    """Main interface for managing Products and their Variants."""
    list_display = (
        'name', 
        'product_type',
        'is_active',
        'price_display', 
        'variant_count'
    )
    list_filter = ('product_type', 'is_active', 'created_at')
    search_fields = ('name', 'description', 'printful_product_id')
    list_editable = ('is_active',)
    readonly_fields = ('created_at', 'updated_at', 'printful_product_id')
    inlines = [VariantInline]
    
    # Optimization: Annotate min/max price and count variants in the main query
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.annotate(
            min_price=Min('variants__price'),
            max_price=Max('variants__price'),
            num_variants=Count('variants')
        )
    
    fieldsets = (
        ('Product Info', {
            'fields': ('name', 'description', 'featured_image')
        }),
        ('Settings', {
            'fields': ('product_type', 'is_active', 'printful_product_id')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )

    # Custom Admin Methods for Display

    @admin.display(description='Price Range', ordering='min_price')
    def price_display(self, obj):
        # Uses annotated data, zero extra DB hits
        if obj.min_price is None: 
            return "-"
        if obj.min_price == obj.max_price:
            return f"£{obj.min_price}"
        return f"£{obj.min_price} - £{obj.max_price}"

    @admin.display(description='Variants', ordering='num_variants')
    def variant_count(self, obj):
        return obj.num_variants

# =======================================================
# 4. Variant Admin (NEW - to support autocomplete_fields)
# =======================================================
@admin.register(Variant)
class VariantAdmin(admin.ModelAdmin):
    list_display = ('full_name', 'price', 'stock_status', 'sku')
    list_filter = ('product__product_type', 'stock_pool')
    search_fields = ('name', 'sku', 'product__name')
    autocomplete_fields = ('product', 'stock_pool')
    list_select_related = ('product', 'stock_pool') # Fixes N+1

    @admin.display(description='Variant Name')
    def full_name(self, obj):
        return str(obj)

    @admin.display(description='Stock')
    def stock_status(self, obj):
        if not obj.stock_pool:
            return "-"
        return f"{obj.stock_pool.available_stock} (Pool: {obj.stock_pool.name})"

# =======================================================
# 5. Stock Item Admin (NEW - Fixes Staff Dashboard Error)
# =======================================================
@admin.register(StockItem)
class StockItemAdmin(admin.ModelAdmin):
    """
    Admin interface for specific StockItems (Variant + Pool link).
    Required for the 'Low Stock Alerts' link in the Staff Dashboard.
    """
    list_display = ('variant', 'pool', 'quantity', 'updated_at')    
    list_select_related = ('variant', 'variant__product', 'pool') # Deep selection
    list_filter = ('pool', 'updated_at')    
    search_fields = ('variant__sku', 'variant__product__name')
    autocomplete_fields = ['variant', 'pool']
