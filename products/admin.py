from django.contrib import admin
from django.db.models import Sum
from django.utils.html import format_html
from .models import Product, Variant

class LowStockFilter(admin.SimpleListFilter):
    title = 'stock status'
    parameter_name = 'stock_status'

    def lookups(self, request, model_admin):
        return (
            ('low', 'Low stock'),
        )

    def queryset(self, request, queryset):
        if self.value() == 'low':
            return queryset.annotate(total_inventory=Sum('variants__inventory')).filter(total_inventory__lte=10)

class VariantInline(admin.TabularInline):
    model = Variant
    fields = ('name', 'sku', 'price', 'inventory', 'printful_variant_id')
    extra = 1

@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    inlines = [VariantInline]
    list_display = ('name', 'product_type', 'current_stock_status')
    list_filter = ('product_type', LowStockFilter)

    def current_stock_status(self, obj):
        total_inventory = obj.variants.aggregate(total=Sum('inventory'))['total'] or 0
        if total_inventory > 20:
            return format_html('<span style="color: green;">● In Stock</span>')
        elif 1 <= total_inventory <= 20:
            return format_html('<span style="color: orange;">● Low Stock</span>')
        else:
            return format_html('<span style="color: red;">● Out of Stock</span>')
    current_stock_status.short_description = 'Stock Status'

@admin.register(Variant)
class VariantAdmin(admin.ModelAdmin):
    list_display = ('product', 'name', 'sku', 'price', 'inventory')
    list_filter = ('product',)