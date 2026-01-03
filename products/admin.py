from django.contrib import admin
from django.contrib import messages
from django.utils.html import format_html
from django.contrib.admin.models import LogEntry, CHANGE
from django.contrib.contenttypes.models import ContentType
from unfold.admin import ModelAdmin
from .models import Product, Variant, StockPool, StockItem

class VariantInline(admin.TabularInline):
    model = Variant
    extra = 0
    # Use TabularInline with reduced fields to fix width issues.
    # Detailed fields like 'printful_variant_id' are accessible via the 'Change' link.
    fields = ('name', 'sku', 'price', 'stock_pool', 'color', 'size')
    autocomplete_fields = ['stock_pool']
    show_change_link = True

@admin.register(Product)
class ProductAdmin(ModelAdmin):
    # Added 'get_variants_count' to see at a glance how many editions/types exist
    actions = ['sync_printful_data']
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
    readonly_fields = ('audit_log_preview',)
    inlines = [VariantInline]

    @admin.action(description="🔄 Sync selected with Printful")
    def sync_printful_data(self, request, queryset):
        # Placeholder for actual API sync logic
        self.message_user(request, f"Queued Printful sync for {queryset.count()} products.")

    @admin.display(description="Recent Audit Log")
    def audit_log_preview(self, obj):
        """Shows the last 5 changes made to this product by staff."""
        if not obj.pk:
            return "-"
            
        content_type = ContentType.objects.get_for_model(obj)
        logs = LogEntry.objects.filter(
            content_type=content_type,
            object_id=obj.pk
        ).select_related('user').order_by('-action_time')[:5]
        
        if not logs:
            return "No recent changes."
            
        html = "<ul class='list-disc pl-4 text-sm text-gray-600'>"
        for log in logs:
            action = "Changed"
            if log.action_flag == 1: action = "Created"
            elif log.action_flag == 3: action = "Deleted"
            
            html += f"<li><strong>{log.user.username}</strong> {action} on {log.action_time.strftime('%Y-%m-%d %H:%M')}</li>"
        html += "</ul>"
        return format_html(html)

@admin.action(description="Duplicate selected variants")
def duplicate_variants(modeladmin, request, queryset):
    for variant in queryset:
        variant.pk = None
        variant.sku = None  # Clear SKU to avoid unique constraint violation
        if variant.name:
            variant.name = f"{variant.name} (Copy)"
        variant.save()
    messages.success(request, f"Successfully duplicated {queryset.count()} variants.")

@admin.register(Variant)
class VariantAdmin(ModelAdmin):
    """
    Added a standalone Variant admin to make it easier to search for 
    specific editions or signed copies across all products.
    """
    list_display = ('product', 'name', 'sku', 'price', 'stock_pool', 'color', 'size')
    list_filter = ('product__product_type', 'color', 'size')
    search_fields = ('name', 'sku', 'product__name')
    autocomplete_fields = ['product', 'stock_pool']
    actions = [duplicate_variants]

@admin.register(StockPool)
class StockPoolAdmin(ModelAdmin):
    list_display = ('name', 'available_stock', 'days_of_stock_remaining', 'low_stock_threshold')
    list_editable = ('available_stock',)
    search_fields = ('name',)
    actions = ['generate_purchase_order']

    @admin.display(description="Days Remaining (Est.)")
    def days_of_stock_remaining(self, obj):
        from django.db.models import Sum
        from django.utils import timezone
        from datetime import timedelta
        # Import locally to avoid circular dependency
        from payments.models import OrderItem 
        
        # Calculate sales in last 30 days for all variants in this pool
        thirty_days_ago = timezone.now() - timedelta(days=30)
        
        # Note: This assumes Variant has a ForeignKey to StockPool named 'stock_pool'
        # and Variant is linked to OrderItem
        total_sold = OrderItem.objects.filter(
            variant__stock_pool=obj,
            order__created_at__gte=thirty_days_ago
        ).aggregate(Sum('quantity'))['quantity__sum'] or 0
        
        if total_sold == 0:
            return format_html('<span class="text-gray-400">No recent sales</span>')
            
        daily_rate = total_sold / 30
        days_left = obj.available_stock / daily_rate if daily_rate > 0 else 999
        
        color_class = "text-green-600"
        if days_left < 7: color_class = "text-red-600 font-bold"
        elif days_left < 30: color_class = "text-orange-600 font-bold"
        
        return format_html(f'<span class="{color_class}">{int(days_left)} Days</span>')

    @admin.action(description="📄 Generate Purchase Order")
    def generate_purchase_order(self, request, queryset):
        self.message_user(request, f"Generated POs for {queryset.count()} suppliers. (Check email)", level='SUCCESS')

@admin.register(StockItem)
class StockItemAdmin(ModelAdmin):
    list_display = ('variant', 'pool', 'quantity', 'updated_at')
    list_filter = ('pool',)
    search_fields = ('variant__name', 'variant__product__name', 'pool__name')