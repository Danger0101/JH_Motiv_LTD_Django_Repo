from decimal import Decimal
from django.conf import settings
from .models import Cart

def get_or_create_cart(request):
    """
    Retrieves the cart for the current session or authenticated user.
    If a user is authenticated, it retrieves or creates their associated cart.
    If the user is anonymous, it uses the session to get or create a cart.
    """
    if request.user.is_authenticated:
        cart, created = Cart.objects.get_or_create(user=request.user, defaults={'status': 'Open'})
    else:
        cart_id = request.session.get('cart_id')
        if cart_id:
            try:
                cart = Cart.objects.get(id=cart_id, status='Open')
            except Cart.DoesNotExist:
                cart = Cart.objects.create(status='Open')
                request.session['cart_id'] = cart.id
        else:
            cart = Cart.objects.create(status='Open')
            request.session['cart_id'] = cart.id
    return cart

def get_cart_summary_data(cart):
    """
    Calculates summary data for a given cart.
    - Subtotal: Sum of (item.quantity * item.variant.price)
    - Item Count: Total number of items in the cart.
    - Tax: A basic tax calculation (e.g., a fixed percentage).
    - Shipping: A placeholder for shipping costs.
    """
    subtotal = sum(item.get_total_price() for item in cart.items.all())
    item_count = sum(item.quantity for item in cart.items.all())

    # Basic tax and shipping calculation (can be expanded later)
    tax_rate = settings.TAX_RATE if hasattr(settings, 'TAX_RATE') else Decimal('0.10') # Example 10%
    tax = subtotal * tax_rate
    shipping = Decimal('0.00') # Placeholder

    total = subtotal + tax + shipping

    return {
        'subtotal': subtotal,
        'item_count': item_count,
        'tax': tax,
        'shipping': shipping,
        'total': total,
    }