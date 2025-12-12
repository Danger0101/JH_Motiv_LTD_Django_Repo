from django.contrib import admin
from .models import Product, Variant, StockPool, StockItem

class VariantInline(admin.TabularInline):
    model = Variant
    extra = 0
    fields = ('name', 'sku', 'price', 'stock_pool', 'weight', 'color', 'size', 'printful_variant_id')

@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ('name', 'product_type', 'fulfillment_method', 'is_active', 'created_at')
    list_filter = ('product_type', 'fulfillment_method', 'is_active')
    search_fields = ('name', 'description', 'printful_product_id')
    inlines = [VariantInline]

@admin.register(StockPool)
class StockPoolAdmin(admin.ModelAdmin):
    list_display = ('name', 'available_stock', 'low_stock_threshold')
    search_fields = ('name',)

@admin.register(StockItem)
class StockItemAdmin(admin.ModelAdmin):
    list_display = ('variant', 'pool', 'quantity', 'updated_at')
    list_filter = ('pool',)
    search_fields = ('variant__name', 'pool__name')