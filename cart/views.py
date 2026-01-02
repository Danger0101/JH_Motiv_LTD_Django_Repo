from django.shortcuts import redirect, render, get_object_or_404
from django.contrib import messages
from django.views.decorators.http import require_POST, require_GET
from decimal import Decimal
from payments.models import Coupon
from .utils import get_or_create_cart, get_cart_summary_data
from django.http import HttpResponse
from products.models import Variant
from .models import CartItem
import json

# --- MAIN PAGES ---

def cart_detail(request):
    """Renders the main cart page."""
    cart = get_or_create_cart(request)
    summary = get_cart_summary_data(cart)
    return render(request, 'cart/detail.html', {'cart': cart, 'summary': summary})

# --- HTMX FRAGMENTS (REQUIRED FOR YOUR HTML) ---

@require_GET
def cart_summary_fragment(request):
    """Refreshes the Mini Cart Icon in the Navbar."""
    cart = get_or_create_cart(request)
    summary = get_cart_summary_data(cart)
    
    # Check if this is an HTMX request to trigger animation
    should_shake = request.headers.get('HX-Request')
    
    # Renders JUST the icon file you uploaded
    return render(request, 'cart/partials/cart_summary.html', {'cart': cart, 'summary': summary, 'should_shake': should_shake})

@require_GET
def cart_item_list(request):
    """Refreshes the list of items on the Cart Page."""
    cart = get_or_create_cart(request)
    # You need to ensure 'cart/partials/cart_item_list.html' exists!
    return render(request, 'cart/partials/cart_item_list.html', {'cart': cart})

@require_GET
def cart_summary_panel(request):
    """Refreshes the order summary panel (subtotal, tax, total)."""
    cart = get_or_create_cart(request)
    summary = get_cart_summary_data(cart)
    return render(request, 'cart/partials/cart_summary_panel.html', {'cart': cart, 'summary': summary})

# --- ACTIONS ---

@require_POST
def apply_coupon(request):
    code = request.POST.get('code', '').strip()
    cart = get_or_create_cart(request)
    
    # 1. Validate Code
    if not code:
        return _htmx_toast(request, "Please enter a coupon code.", "error")

    try:
        coupon = Coupon.objects.filter(code__iexact=code, active=True).first()
        if not coupon:
            raise Coupon.DoesNotExist

        subtotal = sum(item.get_total_price() for item in cart.items.all())
        is_valid, message = coupon.is_valid(user=request.user, cart_value=subtotal)

        if is_valid:
            cart.coupon = coupon
            cart.save()
            # SUCCESS: Send 204 No Content + Trigger 'cartUpdated'
            # Your HTML 'hx-select' will catch this and refresh the totals automatically.
            return _htmx_response_with_trigger("Cheat Code Activated!", "success")
        else:
            return _htmx_toast(request, message, "error")

    except Coupon.DoesNotExist:
        return _htmx_toast(request, "Invalid or expired coupon code.", "error")

@require_POST
def remove_coupon(request):
    cart = get_or_create_cart(request)
    if cart.coupon:
        cart.coupon = None
        cart.save()
    return _htmx_response_with_trigger("Cheat Code Deactivated.", "info")

@require_POST
def add_to_cart(request, variant_id):
    cart = get_or_create_cart(request)
    variant = get_object_or_404(Variant, id=variant_id)
    
    try:
        quantity = int(request.POST.get('quantity', 1))
    except ValueError:
        quantity = 1

    # Stock Check
    stock_available = 0
    if variant.stock_pool:
         stock_available = variant.stock_pool.available_stock
    
    current_in_cart = 0
    try:
        existing_item = CartItem.objects.get(cart=cart, variant=variant)
        current_in_cart = existing_item.quantity
    except CartItem.DoesNotExist:
        pass

    if not variant.product.is_preorder and (current_in_cart + quantity) > stock_available:
        return _htmx_toast(request, f"Sorry, only {stock_available} available.", "error")

    # Add/Update Item
    cart_item, created = CartItem.objects.get_or_create(cart=cart, variant=variant)
    if not created:
        cart_item.quantity += quantity
    else:
        cart_item.quantity = quantity
    cart_item.save()

    return _htmx_response_with_trigger(f"Added {variant.product.name} to cart.", "success")

@require_POST
def update_cart_item(request, item_id):
    """
    Updates quantity or removes an item entirely.
    Triggered by the quantity input change or the delete button in the cart list.
    """
    cart = get_or_create_cart(request)
    cart_item = get_object_or_404(CartItem, id=item_id, cart=cart)
    
    # 1. Get new quantity from POST data
    try:
        quantity = int(request.POST.get('quantity'))
    except (TypeError, ValueError):
        # If invalid data, ignore and return current state
        return render(request, 'cart/partials/cart_item_list.html', {'cart': cart})

    # 2. Logic: If 0, delete. If > 0, update (checking stock).
    if quantity <= 0:
        cart_item.delete()
        msg = "Item removed from cart."
    else:
        # Stock Check
        if not cart_item.variant.product.is_preorder and cart_item.variant.stock_pool:
            available = cart_item.variant.stock_pool.available_stock
            if quantity > available:
                 return _htmx_toast(request, f"Sorry, only {available} available.", "error")
        
        cart_item.quantity = quantity
        cart_item.save()
        msg = "Cart updated."

    # 3. Return 204 No Content + Trigger Summary Refresh
    # This prevents the list from reloading twice (once from swap, once from event)
    return _htmx_response_with_trigger(msg, 'success')

# --- HELPER FUNCTIONS ---

def _htmx_response_with_trigger(message, type):
    """Returns 204 No Content but triggers a refresh on the frontend."""
    response = HttpResponse(status=204)
    response['HX-Trigger'] = json.dumps({
        'cartUpdated': None,  # Tells Navbar and Cart Page to refresh
        'show-toast': {'message': message, 'type': type} # Shows the popup
    })
    return response

def _htmx_toast(request, message, type):
    """Returns just the toast message (for errors where we don't refresh the cart)."""
    # Assuming you have a snippet for messages or just use the trigger method above
    # Using the trigger method is safer/easier for your setup:
    return _htmx_response_with_trigger(message, type)