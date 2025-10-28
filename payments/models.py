import uuid
from django.db import models
from django.contrib.auth import get_user_model
from products.models import Variant

User = get_user_model()

class Order(models.Model):
    # User is now nullable to allow for guest checkouts
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    # Secure token for guest order tracking - generated in save()
    guest_order_token = models.UUIDField(unique=True, null=True, blank=True, editable=False)
    total_paid = models.DecimalField(max_digits=10, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

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