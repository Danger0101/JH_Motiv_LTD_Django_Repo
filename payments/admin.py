import csv
from django.contrib import admin
from django.db.models import Sum, Q
from django.http import HttpResponse
from .models import Order, OrderItem, CoachingOrder, CoachingOrderItem, Coupon, CouponUsage
from django.utils.html import format_html

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
    list_display = ('id', 'client_name', 'coach_name', 'referrer_name', 'amount_gross', 'amount_coach', 'amount_referrer', 'payout_status', 'created_at')
    list_filter = ('payout_status', 'referrer', 'enrollment__coach', 'created_at')
    search_fields = ('enrollment__client__email', 'enrollment__offering__name', 'referrer__name')
    date_hierarchy = 'created_at'
    actions = ['mark_as_paid', 'export_payouts_csv']

    @admin.display(description='Client', ordering='enrollment__client')
    def client_name(self, obj):
        return obj.enrollment.client.get_full_name()

    @admin.display(description='Coach', ordering='enrollment__coach__user__last_name')
    def coach_name(self, obj):
        if obj.enrollment.coach:
            return obj.enrollment.coach.user.get_full_name()
        return "-"
        
    @admin.display(description='Referrer', ordering='referrer__name')
    def referrer_name(self, obj):
        return obj.referrer.name if obj.referrer else "-"

    @admin.action(description='Mark selected commissions as PAID')
    def mark_as_paid(self, request, queryset):
        queryset.update(payout_status='paid')

    @admin.action(description='Export Unpaid Payouts to CSV')
    def export_payouts_csv(self, request, queryset):
        """Generates a CSV file of selected orders for banking/accounting."""
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="payouts.csv"'
        
        writer = csv.writer(response)
        writer.writerow(['Order ID', 'Date', 'Type', 'Recipient Name', 'Amount', 'Reference'])

        # We only want to export unpaid items from the selection
        unpaid_queryset = queryset.filter(payout_status='unpaid')

        for order in unpaid_queryset:
            # Row for Coach Payout
            if order.amount_coach > 0:
                writer.writerow([
                    order.id, 
                    order.created_at.date(), 
                    'Coach', 
                    order.enrollment.coach.user.get_full_name(), 
                    order.amount_coach, 
                    f"Coach Fee Order #{order.id}"
                ])
            
            # Row for Dreamer/Referrer Payout
            if order.amount_referrer > 0 and order.referrer:
                writer.writerow([
                    order.id, 
                    order.created_at.date(), 
                    'Referrer', 
                    order.referrer.name, 
                    order.amount_referrer, 
                    f"Ref Fee Order #{order.id}"
                ])
        
        return response

    # This is a placeholder. You'll need to create this template file.
    # See the note below for its content.
    change_list_template = "admin/payments/coachingorder/change_list.html"


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
    search_fields = ['code', 'affiliate_dreamer__name', 'user_specific__email']
    readonly_fields = ['qr_code_preview']
    inlines = [CouponUsageInline]
    fieldsets = (
        (None, {'fields': ('code', 'active')}),
        ('Discount Logic', {'fields': ('coupon_type', 'discount_type', 'discount_value', 'free_shipping')}),
        ('Scope & Constraints', {'fields': ('limit_to_product_type', 'min_cart_value', 'valid_from', 'valid_to', 'usage_limit', 'one_per_customer', 'new_customers_only', 'user_specific', 'qr_code_preview')}),
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

    def qr_code_preview(self, obj):
        if obj.code:
            qr_url = obj.get_qr_code_url()
            return format_html(
                '<img src="{}" width="150" height="150" /><br>'
                '<a href="{}" target="_blank" download="qr_code_{}.png">Download QR</a>',
                qr_url,
                qr_url,
                obj.code
            )
        return "-"