from django.contrib import admin
from .models import Order, OrderItem, CoachingOrder, CoachingOrderItem

class OrderItemInline(admin.TabularInline):
    model = OrderItem
    fields = ('variant', 'quantity', 'price')
    readonly_fields = ('variant', 'quantity', 'price')
    extra = 0

    def has_add_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    inlines = [OrderItemInline]
    list_display = ('id', 'user', 'total_paid', 'created_at', 'list_products_names')
    list_filter = ('created_at',)
    date_hierarchy = 'created_at'

    def list_products_names(self, obj):
        return ", ".join([item.variant.product.name for item in obj.items.all()])
    list_products_names.short_description = 'Products'

    # Sales tracking can be implemented by adding a referral_source field to the Order model.
    # This field can be populated from a hidden form field or session data during checkout.
    # It can then be added to the list_display here to track sales channels.

class CoachingOrderItemInline(admin.TabularInline):
    model = CoachingOrderItem
    fields = ('offering', 'price')
    readonly_fields = ('offering', 'price')
    extra = 0

    def has_add_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

@admin.register(CoachingOrder)
class CoachingOrderAdmin(admin.ModelAdmin):
    inlines = [CoachingOrderItemInline]
    list_display = ('id', 'client_name', 'offering_name', 'total_paid', 'created_at')
    list_filter = ('created_at', 'enrollment__offering')
    search_fields = ('enrollment__client__email', 'enrollment__offering__name')
    date_hierarchy = 'created_at'

    @admin.display(description='Client', ordering='enrollment__client')
    def client_name(self, obj):
        return obj.enrollment.client.get_full_name()

    @admin.display(description='Offering', ordering='enrollment__offering')
    def offering_name(self, obj):
        return obj.enrollment.offering.name