from django.shortcuts import render, get_object_or_404
from django.views.decorators.http import require_POST
from django.http import HttpResponse
from .models import CartItem
from products.models import Variant
from .utils import get_or_create_cart, get_cart_summary_data

def cart_item_list(request):
    """Refreshes the list of items in the cart."""
    cart = get_or_create_cart(request)
    return render(request, 'cart/partials/cart_item_list.html', {'cart': cart})

def cart_summary_panel(request):
    """Refreshes the order summary panel (subtotal, tax, total)."""
    cart = get_or_create_cart(request)
    summary = get_cart_summary_data(cart)
    return render(request, 'cart/partials/cart_summary_panel.html', {'summary': summary})

def cart_summary_fragment(request):
    """Refreshes the cart icon/badge in the navbar."""
    cart = get_or_create_cart(request)
    summary = get_cart_summary_data(cart)
    return render(request, 'cart/partials/cart_summary.html', {'summary': summary})

@require_POST
def add_to_cart(request, variant_id):
    """Adds an item to the cart."""
    cart = get_or_create_cart(request)
    quantity = int(request.POST.get('quantity', 1))
    variant = get_object_or_404(Variant, id=variant_id)
    
    item, created = CartItem.objects.get_or_create(cart=cart, variant=variant)
    if not created:
        item.quantity += quantity
    else:
        item.quantity = quantity
    item.save()
    
    # Return 204 No Content but trigger an event to update the cart badge
    response = HttpResponse(status=204)
    response['HX-Trigger'] = 'cartUpdated'
    return response

@require_POST
def update_cart_item(request, item_id):
    """Updates quantity of an item."""
    cart = get_or_create_cart(request)
    item = get_object_or_404(CartItem, id=item_id, cart=cart)
    quantity = int(request.POST.get('quantity', item.quantity))
    
    if quantity > 0:
        item.quantity = quantity
        item.save()
    else:
        item.delete()
        
    # Return the updated list AND trigger a summary update
    response = render(request, 'cart/partials/cart_item_list.html', {'cart': cart})
    response['HX-Trigger'] = 'cartUpdated'
    return response

@require_POST
def remove_from_cart(request, item_id):
    """Removes an item completely."""
    cart = get_or_create_cart(request)
    CartItem.objects.filter(id=item_id, cart=cart).delete()
    
    response = render(request, 'cart/partials/cart_item_list.html', {'cart': cart})
    response['HX-Trigger'] = json.dumps({
        'cartUpdated': None,
        'showToast': {'message': "Item Dropped from Inventory", 'type': 'warning'}
    })
    return response