from django.contrib import admin
from unfold.admin import ModelAdmin
from .models import Product, Variant, StockPool, StockItem

class VariantInline(admin.TabularInline):
    model = Variant
    extra = 0
    fields = ('name', 'sku', 'price', 'stock_pool', 'weight', 'color', 'size', 'printful_variant_id')

@admin.register(Product)
class ProductAdmin(ModelAdmin):
    # Added 'get_variants_count' to see at a glance how many editions/types exist
    list_display = (
        'name', 
        'product_type', 
        'dice_rating', 
        'is_preorder', 
        'fulfillment_method', 
        'shipping_category', 
        'shipping_included', 
        'is_active', 
        'created_at'
    )
    list_filter = (
        'product_type', 
        'is_preorder', 
        'fulfillment_method', 
        'shipping_category', 
        'shipping_included', 
        'is_active'
    )
    list_editable = (
        'is_active', 
        'fulfillment_method', 
        'shipping_category', 
        'dice_rating', 
        'is_preorder', 
        'shipping_included'
    )
    search_fields = ('name', 'description', 'printful_product_id')
    inlines = [VariantInline]

@admin.register(Variant)
class VariantAdmin(ModelAdmin):
    """
    Added a standalone Variant admin to make it easier to search for 
    specific editions or signed copies across all products.
    """
    list_display = ('product', 'name', 'sku', 'price', 'stock_pool', 'color', 'size')
    list_filter = ('product__product_type', 'color', 'size')
    search_fields = ('name', 'sku', 'product__name')

@admin.register(StockPool)
class StockPoolAdmin(ModelAdmin):
    list_display = ('name', 'available_stock', 'low_stock_threshold')
    list_editable = ('available_stock',)
    search_fields = ('name',)

@admin.register(StockItem)
class StockItemAdmin(ModelAdmin):
    list_display = ('variant', 'pool', 'quantity', 'updated_at')
    list_filter = ('pool',)
    search_fields = ('variant__name', 'variant__product__name', 'pool__name')