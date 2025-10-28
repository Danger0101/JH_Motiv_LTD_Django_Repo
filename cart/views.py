from django.shortcuts import render, get_object_or_404
from django.template.loader import render_to_string
from django.http import HttpResponse
from django.views.decorators.http import require_POST
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

    cart_item, created = CartItem.objects.get_or_create(
        cart=cart,
        variant=variant,
        defaults={'quantity': quantity}
    )

    if not created:
        cart_item.quantity += quantity
        cart_item.save()

    # Prepare the response to just update the summary, but also trigger a global event
    response = cart_summary_fragment(request)
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
    cart = get_or_create_cart(request)
    summary_data = get_cart_summary_data(cart)
    return render(request, 'cart/detail.html', {'cart': cart, 'summary': summary_data})


def cart_item_list(request):
    cart = get_or_create_cart(request)
    summary_data = get_cart_summary_data(cart)
    return render(request, 'cart/partials/cart_item_list.html', {'cart': cart, 'summary': summary_data})
