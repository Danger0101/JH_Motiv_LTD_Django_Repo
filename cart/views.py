from django.contrib import messages
from django.shortcuts import render, get_object_or_404
from django.template.loader import render_to_string
from django.http import HttpResponse, HttpResponseRedirect
from django.views.decorators.http import require_POST
from django.urls import reverse
from django.conf import settings  # Imported settings

from .utils import get_or_create_cart, get_cart_summary_data
from .models import CartItem
from products.models import Variant

def cart_summary_fragment(request):
    cart = get_or_create_cart(request)
    summary_data = get_cart_summary_data(cart)
    return render(request, 'cart/partials/cart_summary.html', {'cart': cart, 'summary': summary_data})

@require_POST
def add_to_cart(request, variant_id):
    cart = get_or_create_cart(request)
    variant = get_object_or_404(Variant, id=variant_id)
    quantity = int(request.POST.get('quantity', 1))

    # Check variant availability (optional but recommended before saving)
    if not variant.is_available(quantity):
        # Optionally, handle out-of-stock error here, e.g., using Django messages
        messages.error(request, "Sorry, this item is out of stock.")
        return HttpResponseRedirect(reverse('products:product_detail', args=[variant.product.id]))

    cart_item, created = CartItem.objects.get_or_create(
        cart=cart,
        variant=variant,
        defaults={'quantity': quantity}
    )

    if not created:
        cart_item.quantity += quantity
        cart_item.save()

    # Use a standard Django redirect (302 Found) to force navigation to the cart detail page.
    response = HttpResponseRedirect(reverse('cart:cart_detail'))
    
    # Send the HX-Trigger header to ensure the cart icon in the navbar updates immediately.
    response['HX-Trigger'] = 'cartUpdated'
    
    return response

@require_POST
def update_cart_item(request, item_id):
    cart_item = get_object_or_404(CartItem, id=item_id)
    quantity = int(request.POST.get('quantity', 0))

    if quantity <= 0:
        cart_item.delete()
    else:
        cart_item.quantity = quantity
        cart_item.save()

    # Get the cart and summary data for rendering the item list
    cart = get_or_create_cart(request)
    summary_data = get_cart_summary_data(cart)
    
    # Render the item list to a string
    html = render_to_string('cart/partials/cart_item_list.html', {'cart': cart, 'summary': summary_data}, request=request)
    
    # Create an HTTP response and trigger a global event for the summary to update
    response = HttpResponse(html)
    response['HX-Trigger'] = 'cartUpdated'
    return response

def cart_detail(request):
    """
    Unified One-Step Cart & Checkout View.
    """
    cart = get_or_create_cart(request)
    summary_data = get_cart_summary_data(cart)
    
    context = {
        'cart': cart,
        'summary': summary_data,
        'STRIPE_PUBLISHABLE_KEY': settings.STRIPE_PUBLISHABLE_KEY  # Pass key for embedded checkout
    }
    return render(request, 'cart/detail.html', context)

# NEW VIEW: Renders the summary panel content for HTMX reloading
def cart_summary_panel(request):
    cart = get_or_create_cart(request)
    summary_data = get_cart_summary_data(cart)
    return render(request, 'cart/partials/cart_summary_panel.html', {'cart': cart, 'summary': summary_data})


def cart_item_list(request):
    cart = get_or_create_cart(request)
    summary_data = get_cart_summary_data(cart)
    return render(request, 'cart/partials/cart_item_list.html', {'cart': cart, 'summary': summary_data})