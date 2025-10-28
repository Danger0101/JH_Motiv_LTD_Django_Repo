from django.shortcuts import render, get_object_or_404
from .models import Order

def order_detail_guest(request, guest_order_token):
    """Displays a guest's order details using a secure token."""
    order = get_object_or_404(Order, guest_order_token=guest_order_token)
    return render(request, 'payments/order_detail.html', {'order': order})
