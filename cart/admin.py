from django.contrib import admin
from .models import Cart, CartItem

class CartItemInline(admin.TabularInline):
    model = CartItem
    extra = 0
    readonly_fields = ('variant', 'quantity', 'get_price')
    can_delete = False

    @admin.display(description='Unit Price')
    def get_price(self, obj):
        return obj.variant.price

@admin.register(Cart)
class CartAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'status', 'item_count', 'total_value', 'updated_at', 'abandoned_cart_sent')
    list_filter = ('status', 'abandoned_cart_sent', 'updated_at')
    search_fields = ('user__email', 'user__username', 'session_key')
    readonly_fields = ('created_at', 'updated_at')
    inlines = [CartItemInline]
    actions = ['mark_abandoned_email_sent']

    def get_queryset(self, request):
        # Optimization: Prefetch items and variants to calculate totals efficiently
        return super().get_queryset(request).prefetch_related('items__variant')

    @admin.display(description='Items')
    def item_count(self, obj):
        return obj.items.count()

    @admin.display(description='Est. Value')
    def total_value(self, obj):
        # Python-side calculation is acceptable here as carts usually have few items
        # and we prefetched the data.
        total = sum(item.get_total_price() for item in obj.items.all())
        return f"£{total:.2f}"

    @admin.action(description="Mark selected as Abandoned Email Sent")
    def mark_abandoned_email_sent(self, request, queryset):
        queryset.update(abandoned_cart_sent=True)
