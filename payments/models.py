import uuid
from django.db import models
from django.db.models import JSONField
from django.contrib.auth import get_user_model
from products.models import Variant
from coaching_booking.models import ClientOfferingEnrollment
from coaching_core.models import Offering

User = get_user_model()

class Order(models.Model):
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    email = models.EmailField(null=True, blank=True)
    guest_order_token = models.UUIDField(unique=True, null=True, blank=True, editable=False)
    printful_order_id = models.CharField(max_length=255, null=True, blank=True)
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
    total_paid = models.DecimalField(max_digits=10, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Coaching Order for {self.enrollment.client.get_full_name()}"

class CoachingOrderItem(models.Model):
    order = models.ForeignKey(CoachingOrder, related_name='items', on_delete=models.CASCADE)
    offering = models.ForeignKey(Offering, on_delete=models.CASCADE)
    price = models.DecimalField(max_digits=10, decimal_places=2) # Denormalized price

    def __str__(self):
        return f"Coaching Order Item for {self.offering.name}"