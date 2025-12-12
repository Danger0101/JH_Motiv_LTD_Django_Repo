import uuid
from decimal import Decimal  # <--- ADDED THIS IMPORT
from django.db import models
from django.db.models import JSONField
from django.contrib.auth import get_user_model
from django.utils import timezone
from products.models import Variant
from products.models import Product
from coaching_booking.models import ClientOfferingEnrollment
from dreamers.models import DreamerProfile
from coaching_core.models import Offering

User = get_user_model()

class Order(models.Model):
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    email = models.EmailField(null=True, blank=True)
    guest_order_token = models.UUIDField(unique=True, null=True, blank=True, editable=False)
    printful_order_id = models.CharField(max_length=255, null=True, blank=True)
    stripe_checkout_id = models.CharField(max_length=255, null=True, blank=True, unique=True, help_text="Stripe Checkout Session ID for idempotency.")
    printful_order_status = models.CharField(max_length=100, null=True, blank=True)
    shipping_data = JSONField(null=True, blank=True)
    total_paid = models.DecimalField(max_digits=10, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # --- UPDATED STATUS CHOICES ---
    STATUS_PENDING = 'pending'
    STATUS_PAID = 'paid'
    STATUS_PREPARING = 'preparing'  # New
    STATUS_SHIPPED = 'shipped'      # New
    STATUS_DELIVERED = 'delivered'  # New
    STATUS_CANCELLED = 'cancelled'
    STATUS_REFUNDED = 'refunded'    # New

    STATUS_CHOICES = [
        (STATUS_PENDING, 'Pending'),
        (STATUS_PAID, 'Paid'),
        (STATUS_PREPARING, 'Preparing'),
        (STATUS_SHIPPED, 'Shipped'),
        (STATUS_DELIVERED, 'Delivered'),
        (STATUS_CANCELLED, 'Cancelled'),
        (STATUS_REFUNDED, 'Refunded'),
    ]
    
    status = models.CharField(
        max_length=20, 
        choices=STATUS_CHOICES,
        default=STATUS_PENDING,
    )

    # --- NEW CARRIER & TRACKING FIELDS ---
    CARRIER_CHOICES = [
        ('royal_mail', 'Royal Mail'),
        ('dpd', 'DPD'),
        ('evri', 'Evri'),
        ('dhl', 'DHL'),
        ('ups', 'UPS'),
        ('fedex', 'FedEx'),
        ('other', 'Other'),
    ]
    carrier = models.CharField(max_length=50, choices=CARRIER_CHOICES, null=True, blank=True)
    tracking_number = models.CharField(max_length=100, null=True, blank=True)
    tracking_url = models.URLField(max_length=500, null=True, blank=True, help_text="Optional direct link to tracking")

    coupon = models.ForeignKey('Coupon', on_delete=models.SET_NULL, null=True, blank=True, related_name='orders')
    # --- IMMUTABLE ORDER HISTORY (SNAPSHOT) ---
    coupon_code_snapshot = models.CharField(max_length=50, null=True, blank=True, help_text="The code used (e.g. SUMMER20)")
    discount_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    coupon_data_snapshot = models.JSONField(null=True, blank=True, help_text="A snapshot of the coupon's rules at time of purchase.")

    def save(self, *args, **kwargs):
        if not self.pk and self.user is None and self.guest_order_token is None:
            self.guest_order_token = uuid.uuid4()
        super().save(*args, **kwargs)

    def __str__(self):
        if self.user:
            return f"Order {self.id} for {self.user.username}"
        return f"Guest Order {self.id} ({self.guest_order_token})"

class OrderItem(models.Model):
    order = models.ForeignKey(Order, related_name='items', on_delete=models.CASCADE)
    variant = models.ForeignKey(Variant, on_delete=models.CASCADE)
    price = models.DecimalField(max_digits=10, decimal_places=2) # Denormalized price
    quantity = models.PositiveIntegerField(default=1)

    def __str__(self):
        return f"{self.quantity} of {self.variant.product.name} ({self.variant.name})"

class CoachingOrder(models.Model):
    enrollment = models.OneToOneField(ClientOfferingEnrollment, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    stripe_checkout_id = models.CharField(max_length=255, null=True, blank=True, unique=True, help_text="Stripe Checkout Session ID for idempotency.")
    updated_at = models.DateTimeField(auto_now=True)

    # Referral Tracking
    referrer = models.ForeignKey(
        DreamerProfile, on_delete=models.SET_NULL, null=True, blank=True,
        help_text="The Dreamer who referred this sale."
    )
    
    # The Financial Split (Recorded at time of purchase)
    # FIX: Added default=0.00 here to solve the migration error
    amount_gross = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, help_text="Total paid by client")
    amount_coach = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, help_text="Owed to Coach")
    amount_referrer = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, help_text="Owed to Dreamer")
    amount_company = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, help_text="Retained by JH Motiv")
    
    # Coupon & Discount Snapshot
    coupon_code = models.CharField(max_length=50, null=True, blank=True)
    discount_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)

    # Status
    payout_status = models.CharField(
        max_length=20, 
        choices=[('unpaid', 'Unpaid'), ('paid', 'Paid'), ('void', 'Void')], 
        default='unpaid'
    )

    def __str__(self):
        return f"Coaching Order for {self.enrollment.client.get_full_name()}"
    
    @property
    def total_paid(self):
        return self.amount_gross

class CoachingOrderItem(models.Model):
    order = models.ForeignKey(CoachingOrder, related_name='items', on_delete=models.CASCADE)
    offering = models.ForeignKey(Offering, on_delete=models.CASCADE)
    price = models.DecimalField(max_digits=10, decimal_places=2) # Denormalized price

    def __str__(self):
        return f"Coaching Order Item for {self.offering.name}"


class Coupon(models.Model):
    code = models.CharField(max_length=50, unique=True)

    # Discount Logic
    DISCOUNT_TYPE_PERCENT = 'percent'
    DISCOUNT_TYPE_FIXED = 'fixed'
    DISCOUNT_TYPES = [
        (DISCOUNT_TYPE_PERCENT, 'Percentage Off'),
        (DISCOUNT_TYPE_FIXED, 'Fixed Amount Off'),
    ]
    discount_type = models.CharField(max_length=10, choices=DISCOUNT_TYPES)
    discount_value = models.DecimalField(max_digits=10, decimal_places=2, help_text="e.g., 10.00 for fixed amount, or 15 for 15%")

    # --- NEW: GIFT CARD VS. DISCOUNT ---
    COUPON_TYPE_DISCOUNT = 'discount'
    COUPON_TYPE_GIFT_CARD = 'gift_card'
    COUPON_TYPE_CHOICES = [
        (COUPON_TYPE_DISCOUNT, 'Discount (Reduces subtotal, affects tax)'),
        (COUPON_TYPE_GIFT_CARD, 'Gift Card (Acts as payment, reduces grand total)'),
    ]
    coupon_type = models.CharField(max_length=10, choices=COUPON_TYPE_CHOICES, default=COUPON_TYPE_DISCOUNT)
    free_shipping = models.BooleanField(default=False)

    # Scope
    specific_products = models.ManyToManyField(Product, blank=True, help_text="Applies only to these products.")
    specific_offerings = models.ManyToManyField(Offering, blank=True, help_text="Applies only to these coaching packages.")

    # "Smart Scope"
    LIMIT_TYPE_ALL = 'all'
    LIMIT_TYPE_PHYSICAL = 'physical'
    LIMIT_TYPE_COACHING = 'coaching'
    LIMIT_CHOICES = [
        (LIMIT_TYPE_ALL, 'All Products & Coaching'),
        (LIMIT_TYPE_PHYSICAL, 'Physical Products Only'),
        (LIMIT_TYPE_COACHING, 'Coaching Only'),
    ]
    limit_to_product_type = models.CharField(max_length=20, choices=LIMIT_CHOICES, default=LIMIT_TYPE_ALL)

    # Constraints
    min_cart_value = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    valid_from = models.DateTimeField(default=timezone.now)
    valid_to = models.DateTimeField()
    active = models.BooleanField(default=True)
    usage_limit = models.PositiveIntegerField(null=True, blank=True, help_text="Total times this code can be used.")
    one_per_customer = models.BooleanField(default=False, help_text="Limit to one use per customer.")
    new_customers_only = models.BooleanField(default=False, help_text="Can only be used on a customer's first order.")
    user_specific = models.ForeignKey(User, null=True, blank=True, on_delete=models.CASCADE, related_name='coupons', help_text="If set, only this user can use this coupon.")

    # Referral Tracking
    referrer = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='referred_coupons', help_text="The user who 'owns' this coupon (for affiliate tracking).")
    affiliate_dreamer = models.ForeignKey(DreamerProfile, null=True, blank=True, on_delete=models.SET_NULL, related_name='coupons', help_text="Link this coupon to a Dreamer for affiliate tracking.")

    def is_valid(self, user=None, cart_value=Decimal('0.00')):
        now = timezone.now()
        if not self.active or not (self.valid_from <= now <= self.valid_to):
            return False, "This coupon is not active or has expired."
        if self.usage_limit is not None and self.usages.count() >= self.usage_limit:
            return False, "This coupon has reached its usage limit."
        if cart_value < self.min_cart_value:
            # "The Nudge" logic
            amount_needed = self.min_cart_value - cart_value
            return False, f"You are only £{amount_needed:.2f} away from using this coupon!"
        if self.one_per_customer and user and user.is_authenticated:
            if self.usages.filter(user=user).exists():
                return False, "You have already used this coupon."
        if self.new_customers_only and user and user.is_authenticated:
            has_prior_orders = Order.objects.filter(
                user=user, status__in=[Order.STATUS_PAID, Order.STATUS_SHIPPED, Order.STATUS_DELIVERED]
            ).exists()
            if has_prior_orders:
                return False, "This code is for new customers only."
        if self.user_specific and self.user_specific != user:
            return False, "This coupon is not valid for your account."
        return True, "Valid"

    def __str__(self):
        return self.code

    @property
    def description(self):
        if self.discount_type == self.DISCOUNT_TYPE_PERCENT:
            return f"{int(self.discount_value)}% off"
        elif self.discount_type == self.DISCOUNT_TYPE_FIXED:
            return f"£{self.discount_value} off"
        return "Discount"

    def get_qr_code_url(self):
        """
        Returns a URL to a dynamically generated QR code for this coupon.
        Uses a free and simple QR code API.
        Format: Scans to https://jhmotiv.shop/?coupon=CODE
        """
        # Note: Ensure your frontend can handle the '?coupon=CODE' query parameter.
        target_url = f"https://jhmotiv.shop/?coupon={self.code}"
        return f"https://api.qrserver.com/v1/create-qr-code/?size=200x200&data={target_url}"


class CouponUsage(models.Model):
    coupon = models.ForeignKey(Coupon, on_delete=models.CASCADE, related_name='usages')
    order = models.ForeignKey(Order, on_delete=models.CASCADE, null=True, blank=True)
    coaching_order = models.ForeignKey(CoachingOrder, on_delete=models.CASCADE, null=True, blank=True, related_name='coupon_usages')
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    email = models.EmailField(blank=True, null=True) # For guest checkouts
    used_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Coupon {self.coupon.code} used on {self.used_at.strftime('%Y-%m-%d')}"