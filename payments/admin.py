import csv
from django.contrib import admin
from django.db.models import Count, Prefetch
from unfold.admin import ModelAdmin
from django.http import HttpResponse
from .models import Order, OrderItem, CoachingOrder, CoachingOrderItem, Coupon, CouponUsage
from django.utils.html import format_html
from django.urls import reverse
from django.conf import settings

class OrderItemInline(admin.TabularInline):
    model = OrderItem
    fields = ('get_product_name', 'get_variant_name', 'get_item_type', 'quantity', 'price')
    readonly_fields = ('get_product_name', 'get_variant_name', 'get_item_type', 'price', 'quantity')
    extra = 0
    can_delete = False

    # Optimization: preventing N+1 within the inline itself
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('variant__product')

    @admin.display(description='Product')
    def get_product_name(self, obj):
        return obj.variant.product.name

    @admin.display(description='Variant')
    def get_variant_name(self, obj):
        return obj.variant.name

    @admin.display(description='Type')
    def get_item_type(self, obj):
        if obj.variant.weight == 0:
            return format_html('<span style="color: blue;">Digital</span>')
        return "Physical"

@admin.register(Order)
class OrderAdmin(ModelAdmin):
    list_display = ('id', 'user_link', 'email', 'status', 'total_paid', 'created_at', 'item_count', 'stripe_payment_link')
    list_filter = ('status', 'created_at', 'carrier')
    search_fields = ('id', 'user__email', 'email', 'guest_order_token', 'stripe_checkout_id')
    readonly_fields = ('id', 'created_at', 'updated_at', 'stripe_checkout_id', 'guest_order_token', 'total_paid', 'discount_amount', 'coupon_code_snapshot', 'coupon_data_snapshot', 'stripe_payment_link')
    inlines = [OrderItemInline]
    date_hierarchy = 'created_at'
    
    # Optimization: Fetch user and prefetch items+variants+products in one go
    list_select_related = ('user',) 

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        # Prefetch items to avoid N+1 in the item_count or detail view
        return qs.prefetch_related(
            Prefetch('items', queryset=OrderItem.objects.select_related('variant__product'))
        )

    @admin.display(description='User', ordering='user')
    def user_link(self, obj):
        if obj.user:
            url = reverse("admin:accounts_user_change", args=[obj.user.pk])
            return format_html('<a href="{}">{}</a>', url, obj.user.email or obj.user.username)
        return "Guest"

    @admin.display(description='Items')
    def item_count(self, obj):
        # Because we prefetched, this doesn't hit the DB again
        return sum(item.quantity for item in obj.items.all())

    fieldsets = (
        ('Order Identity', {
            'fields': ('id', 'user_link', 'email', 'status', 'guest_order_token')
        }),
        ('Financials', {
            'fields': ('total_paid', 'discount_amount', 'coupon_code_snapshot', 'coupon_data_snapshot', 'stripe_checkout_id', 'stripe_payment_link')
        }),
        ('Shipping & Fulfillment', {
            'fields': ('shipping_data', 'carrier', 'tracking_number', 'tracking_url', 'printful_order_id', 'printful_order_status')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    def get_readonly_fields(self, request, obj=None):
        # Make user_link readonly
        return self.readonly_fields + ('user_link',)

    @admin.display(description='Stripe Payment')
    def stripe_payment_link(self, obj):
        if not obj.stripe_checkout_id:
            return "-"
        
        is_live = settings.STRIPE_SECRET_KEY and not settings.STRIPE_SECRET_KEY.startswith('sk_test_')
        
        base_url = "https://dashboard.stripe.com"
        path = "" if is_live else "/test"
        url = f"{base_url}{path}/payments/{obj.stripe_checkout_id}"
        return format_html('<a href="{}" target="_blank">View on Stripe</a>', url)

class CoachingOrderItemInline(admin.TabularInline):
    model = CoachingOrderItem
    fields = ('offering', 'price')
    readonly_fields = ('offering', 'price')
    extra = 0
    can_delete = False

@admin.register(CoachingOrder)
class CoachingOrderAdmin(ModelAdmin):
    inlines = [CoachingOrderItemInline]
    list_display = ('id', 'client_link', 'coach_link', 'amount_gross', 'amount_coach', 'amount_referrer', 'amount_company', 'payout_status', 'created_at')
    list_editable = ('payout_status',)
    list_filter = ('payout_status', 'created_at', 'enrollment__offering')
    search_fields = ('enrollment__client__email', 'enrollment__client__first_name', 'stripe_checkout_id')
    date_hierarchy = 'created_at'
    actions = ['mark_as_paid', 'export_payouts_csv']

    # Critical Optimization for Foreign Key lookups
    list_select_related = (
        'enrollment', 
        'enrollment__client', 
        'enrollment__coach', 
        'enrollment__coach__user',
        'referrer'
    )

    @admin.display(description='Client', ordering='enrollment__client__first_name')
    def client_link(self, obj):
        return obj.enrollment.client.get_full_name()

    @admin.display(description='Coach', ordering='enrollment__coach__user__last_name')
    def coach_link(self, obj):
        if obj.enrollment.coach:
            return obj.enrollment.coach.user.get_full_name()
        return "-"

    @admin.action(description='Mark selected commissions as PAID')
    def mark_as_paid(self, request, queryset):
        rows_updated = queryset.update(payout_status='paid')
        self.message_user(request, f"{rows_updated} orders marked as paid.")

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
    fields = ['user_link', 'order_link', 'email', 'used_at']
    readonly_fields = ['user_link', 'order_link', 'email', 'used_at']
    extra = 0
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False
        
    @admin.display(description='User')
    def user_link(self, obj):
        if obj.user:
            url = reverse("admin:accounts_user_change", args=[obj.user.pk])
            return format_html('<a href="{}">{}</a>', url, obj.user.username)
        return "-"

    @admin.display(description='Order')
    def order_link(self, obj):
        if obj.order:
            url = reverse("admin:payments_order_change", args=[obj.order.pk])
            return format_html('<a href="{}">#{}</a>', url, obj.order.pk)
        return "-"

@admin.register(Coupon)
class CouponAdmin(ModelAdmin):
    list_display = ['code', 'discount_display', 'active', 'times_used', 'valid_until', 'qr_code_preview']
    list_filter = ['active', 'discount_type', 'coupon_type']
    search_fields = ['code', 'user_specific__email', 'referrer__name']
    readonly_fields = ['qr_code_preview', 'times_used_display']
    inlines = [CouponUsageInline]
    fieldsets = (
        (None, {'fields': ('code', 'active')}),
        ('Discount Logic', {'fields': ('coupon_type', 'discount_type', 'discount_value', 'free_shipping')}),
        ('Scope & Constraints', {'fields': ('limit_to_product_type', 'min_cart_value', 'valid_from', 'valid_to', 'usage_limit', 'one_per_customer', 'new_customers_only', 'user_specific', 'qr_code_preview', 'times_used_display')}),
        ('Scope (Leave blank to apply to all)', {'fields': ('specific_products', 'specific_offerings')}),
        ('Tracking', {'fields': ('referrer',)}),
    )
    filter_horizontal = ('specific_products', 'specific_offerings',)

    @admin.display(description='Value', ordering='discount_value')
    def value_display(self, obj):
        # Renamed to discount_display in the request, but value_display is what's in list_display in the original file.
        # I will keep the original name to avoid breaking list_display.
        # The request has `discount_display` in `list_display`, so I will rename it.
        pass

    # Optimization: Annotate the count so we can sort by it AND avoid N+1 queries
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.annotate(usage_count=Count('usages'))

    @admin.display(description='Value', ordering='discount_value')
    def discount_display(self, obj):
        return f"{obj.discount_value}%" if obj.discount_type == 'percent' else f"£{obj.discount_value}"

    @admin.display(description='Times Used', ordering='usage_count')
    def times_used(self, obj):
        return obj.usage_count

    @admin.display(description='Times Used')
    def times_used_display(self, obj):
        return obj.usages.count()

    @admin.display(description='Valid Until', ordering='valid_to')
    def valid_until(self, obj):
        if obj.valid_to:
            return obj.valid_to.date()
        return "-"

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