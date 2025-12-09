from django.shortcuts import redirect, render
from django.contrib import messages
from django.views.decorators.http import require_POST
from decimal import Decimal
from payments.models import Coupon
from .utils import get_or_create_cart, get_cart_summary_data
from django.http import HttpResponse

def cart_detail(request):
    """Renders the main cart page."""
    cart = get_or_create_cart(request)
    summary = get_cart_summary_data(cart)
    # The template path should be 'cart/detail.html'
    return render(request, 'cart/detail.html', {'cart': cart, 'summary': summary})

@require_POST
def apply_coupon(request):
    """
    Validates a coupon code and applies it to the session.
    """
    code = request.POST.get('code', '').strip()
    cart = get_or_create_cart(request)

    if not code:
        messages.error(request, "Please enter a coupon code.")
        if request.htmx:
            # For HTMX, return the message partial
            return render(request, 'cart/partials/coupon_message.html')
        else:
            return redirect('cart:cart_detail')

    try:
        coupon = Coupon.objects.get(code__iexact=code)
        # Pre-calculate subtotal to check min_spend requirement
        subtotal = sum(item.get_total_price() for item in cart.items.all())
        
        is_valid, message = coupon.is_valid(user=request.user, cart_value=subtotal)

        if is_valid:
            cart.coupon = coupon
            cart.save()
            messages.success(request, f"Coupon '{coupon.code}' applied.")
            # For HTMX, trigger a cart update event
            if request.htmx:
                response = HttpResponse(status=204)
                response['HX-Trigger'] = 'cartUpdated'
                return response
        else:
            messages.error(request, message) # Use the specific error message
    except Coupon.DoesNotExist:
        messages.error(request, "Invalid coupon code.")

    if request.htmx:
        # On failure, just return the error message partial
        summary = get_cart_summary_data(cart) # Get fresh summary data
        return render(request, 'cart/partials/coupon_message.html', {'summary': summary})
    else:
        return redirect('cart:cart_detail')