from django.contrib import admin
from .models import Order, OrderItem, CoachingOrder, CoachingOrderItem, Coupon, CouponUsage

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


class CouponUsageInline(admin.TabularInline):
    model = CouponUsage
    fields = ['user', 'order', 'email', 'used_at']
    readonly_fields = ['user', 'order', 'email', 'used_at']
    extra = 0
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False

@admin.register(Coupon)
class CouponAdmin(admin.ModelAdmin):
    list_display = ['code', 'discount_type', 'value_display', 'active', 'valid_from', 'valid_to', 'times_used', 'usage_limit']
    list_filter = ['active', 'discount_type', 'valid_from', 'valid_to']
    search_fields = ['code']
    inlines = [CouponUsageInline]
    fieldsets = (
        (None, {'fields': ('code', 'active')}),
        ('Discount Logic', {'fields': ('discount_type', 'discount_value', 'free_shipping')}),
        ('Scope & Constraints', {'fields': ('limit_to_product_type', 'min_cart_value', 'valid_from', 'valid_to', 'usage_limit', 'one_per_customer')}),
        ('Scope (Leave blank to apply to all)', {'fields': ('specific_products', 'specific_offerings')}),
        ('Tracking', {'fields': ('referrer',)}),
    )
    filter_horizontal = ('specific_products', 'specific_offerings',)

    @admin.display(description='Value', ordering='discount_value')
    def value_display(self, obj):
        return f"{obj.discount_value}%" if obj.discount_type == 'percent' else f"£{obj.discount_value}"

    @admin.display(description='Times Used')
    def times_used(self, obj):
        return obj.usages.count()