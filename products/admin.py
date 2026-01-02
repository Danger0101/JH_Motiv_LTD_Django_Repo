from django.contrib import admin
from unfold.admin import ModelAdmin
from .models import Product, Variant, StockPool, StockItem

class VariantInline(admin.TabularInline):
    model = Variant
    extra = 0
    fields = ('name', 'sku', 'price', 'stock_pool', 'weight', 'color', 'size', 'printful_variant_id')

@admin.register(Product)
class ProductAdmin(ModelAdmin):
    list_display = ('name', 'product_type', 'fulfillment_method', 'shipping_category', 'is_preorder', 'dice_rating', 'is_active', 'created_at')
    list_filter = ('product_type', 'fulfillment_method', 'shipping_category', 'is_active', 'is_preorder')
    list_editable = ('is_active', 'fulfillment_method', 'shipping_category', 'is_preorder', 'dice_rating')
    search_fields = ('name', 'description', 'printful_product_id')
    inlines = [VariantInline]

@admin.register(StockPool)
class StockPoolAdmin(ModelAdmin):
    list_display = ('name', 'available_stock', 'low_stock_threshold')
    list_editable = ('available_stock',)
    search_fields = ('name',)

@admin.register(StockItem)
class StockItemAdmin(ModelAdmin):
    list_display = ('variant', 'pool', 'quantity', 'updated_at')
    list_filter = ('pool',)
    search_fields = ('variant__name', 'pool__name')