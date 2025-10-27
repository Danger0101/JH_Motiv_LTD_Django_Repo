
from .models import Cart

def get_or_create_cart(request):
    if request.user.is_authenticated:
        cart, created = Cart.objects.get_or_create(user=request.user)
    else:
        session_key = request.session.session_key
        if not session_key:
            request.session.create()
            session_key = request.session.session_key
        cart, created = Cart.objects.get_or_create(session_key=session_key)
    return cart

def get_cart_summary_data(cart):
    subtotal = sum(item.variant.price * item.quantity for item in cart.items.all())
    item_count = sum(item.quantity for item in cart.items.all())
    # Basic tax and shipping estimates
    tax = subtotal * 0.1  # 10% tax
    shipping = 5.00 if subtotal > 0 else 0
    total = subtotal + tax + shipping
    return {
        'subtotal': subtotal,
        'item_count': item_count,
        'tax': tax,
        'shipping': shipping,
        'total': total,
    }
