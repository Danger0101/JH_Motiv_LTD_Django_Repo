from decimal import Decimal
from django.conf import settings
from .models import Cart
from payments.models import Coupon

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
    - Discount: Calculated based on the cart's coupon, with re-validation.
    - Total: Final price after discounts.
    """
    subtotal = sum(item.get_total_price() for item in cart.items.all())
    item_count = sum(item.quantity for item in cart.items.all())
    discount_amount = Decimal('0.00')
    coupon_message = None

    if cart.coupon:
        # Re-validate the coupon every time summary is calculated
        is_valid, message = cart.coupon.is_valid(user=cart.user, cart_value=subtotal)
        if is_valid:
            discount_amount = calculate_discount(cart.coupon, cart=cart)
            coupon_message = f"Coupon '{cart.coupon.code}' applied."
        else:
            # Silently remove the invalid coupon from the cart
            cart.coupon = None
            cart.save()
            coupon_message = message # Pass the reason for invalidity

    total = subtotal - discount_amount

    return {
        'subtotal': subtotal,
        'item_count': item_count,
        'discount_amount': discount_amount,
        'coupon': cart.coupon,
        'coupon_message': coupon_message,
        'total': max(total, Decimal('0.00')), # Ensure total doesn't go below zero
    }

def calculate_discount(coupon, cart=None, offering=None):
    """
    Calculates the discount amount for a given coupon and cart/offering.
    """
    discount_amount = Decimal('0.00')
    eligible_total = Decimal('0.00')

    # 1. Determine Eligible Total
    # First, check the "Smart Scope"
    if (cart and coupon.limit_to_product_type == Coupon.LIMIT_TYPE_COACHING) or \
       (offering and coupon.limit_to_product_type == Coupon.LIMIT_TYPE_PHYSICAL):
        return Decimal('0.00')

    if cart:
        # If coupon has no specific product restrictions, all items are eligible
        if not coupon.specific_products.exists():
            # FIX: Still check if the product is explicitly excluded
            eligible_items = [
                item for item in cart.items.all() 
                if not getattr(item.variant.product, 'exclude_from_coupons', False)
            ]
            eligible_total = sum(item.get_total_price() for item in eligible_items)
        else:
            # Otherwise, only sum up eligible items
            eligible_product_ids = coupon.specific_products.values_list('id', flat=True)
            for item in cart.items.all():
                # ADDED: Check for 'exclude_from_coupons' flag
                exclude_flag = getattr(item.variant.product, 'exclude_from_coupons', False)
                
                if not exclude_flag and item.variant.product.id in eligible_product_ids:
                    eligible_total += item.get_total_price()
    elif offering:
        # Similar logic for coaching offerings
        if not coupon.specific_offerings.exists() or offering in coupon.specific_offerings.all():
            eligible_total = offering.price

    # 2. Apply Discount if minimum value is met
    if eligible_total >= coupon.min_cart_value:
        if coupon.discount_type == Coupon.DISCOUNT_TYPE_FIXED:
            discount_amount = min(coupon.discount_value, eligible_total)
        elif coupon.discount_type == Coupon.DISCOUNT_TYPE_PERCENT:
            discount_amount = eligible_total * (coupon.discount_value / Decimal('100'))
    
    return discount_amount.quantize(Decimal('0.01'))