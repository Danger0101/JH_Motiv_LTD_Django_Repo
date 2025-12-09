from django.db import models
from django.conf import settings
from products.models import Variant
from decimal import Decimal # ADDED: Import Decimal for safe currency calculations
from payments.models import Coupon

class Cart(models.Model):
    STATUS_CHOICES = (
        ('open', 'Open'),
        ('submitted', 'Submitted'),
    )

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, null=True, blank=True)
    session_key = models.CharField(max_length=40, null=True, blank=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='open')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    abandoned_cart_sent = models.BooleanField(default=False, help_text="True if an abandoned cart reminder has been sent for this cart.")
    coupon = models.ForeignKey(Coupon, on_delete=models.SET_NULL, null=True, blank=True)

    def __str__(self):
        if self.user:
            return f"Cart for {self.user}"
        return f"Anonymous cart {self.session_key}"

    def get_total_price(self):
        """Calculates the total price of all items in the cart."""
        return sum(item.get_total_price() for item in self.items.all())

class CartItem(models.Model):
    cart = models.ForeignKey(Cart, related_name='items', on_delete=models.CASCADE)
    variant = models.ForeignKey(Variant, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(default=1)

    def get_total_price(self):
        """Calculates the total price for this cart item (quantity * variant price)."""
        # FIX: Added this method to resolve the AttributeError
        return self.quantity * self.variant.price

    def __str__(self):
        return f"{self.quantity} of {self.variant.product.name} ({self.variant.name})"