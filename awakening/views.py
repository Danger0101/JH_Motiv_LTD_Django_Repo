import random
import string
import stripe
import json
import uuid
from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse
from django.utils import timezone
from django.conf import settings
from django.views.decorators.csrf import csrf_exempt
from django.template.loader import render_to_string
from django.core.mail import send_mail
from products.models import Product, Variant
from accounts.models import User
from cart.utils import get_or_create_cart
from coaching_core.models import Offering, ClientProfile
from coaching_booking.models import ClientOfferingEnrollment
from .models import FunnelTier, OrderBump
from payments.models import Order, OrderItem

# --- THE CONTAINER ---
def funnel_landing(request):
    """
    Renders the 'Terminal' container.
    The actual content (Step 1) is loaded via HTMX trigger on page load.
    """
    return render(request, 'awakening/partials/funnel_container.html')

# --- STEP 1: THE HOOK (Booklet) ---
def render_hook(request):
    """
    Returns ONLY the booklet HTML fragment.
    Triggered via HTMX when the page loads or user clicks 'Back'.
    """
    # Optional: Fetch product if you need dynamic data
    # product = Product.objects.filter(name__icontains="Stop Being an NPC").first()
    return render(request, 'awakening/partials/step_1_hook.html')

# --- STEP 2: THE OFFERS (Tiers) ---
def render_offers(request):
    """
    Returns ONLY the pricing cards (Single, Multi, Co-Op).
    Now fetched dynamically from the FunnelTier model.
    """
    active_tiers = FunnelTier.objects.filter(is_active=True).select_related('variant').prefetch_related('perks')
    
    tiers_data = []
    
    for tier in active_tiers:
        # Construct dictionary to match the template's expected structure
        tiers_data.append({
            'id': tier.slug,                  # Maps to HTML ID
            'name': tier.name,
            'quantity': tier.quantity,
            'price': tier.total_price,        # Calculated property from model
            'variant_id': tier.variant.id,
            'perks': [p.text for p in tier.perks.all()], # Flatten perks to list of strings
            'class': tier.css_class           # Maps to styling hook
        })

    return render(request, 'awakening/partials/step_2_offers.html', {'tiers': tiers_data})

# --- STEP 3: THE CHECKOUT (Embedded) ---
def render_checkout(request, variant_id):
    """
    1. Adds item to cart (background).
    2. Returns the STRIPE FORM fragment.
    """
    variant = get_object_or_404(Variant, id=variant_id)
    # Get quantity from the hx-vals POST data
    quantity = int(request.POST.get('quantity', 1))
    total_price = variant.price * quantity
    
    # Fetch the two active order bump offers
    order_bumps = OrderBump.objects.filter(is_active=True).select_related('variant')[:2]

    cart = get_or_create_cart(request)
    
    # STRICT FUNNEL RULE: Empty cart first
    # This ensures they aren't buying a t-shirt + the book accidentally
    cart.items.all().delete() 
    
    # Add the selected bundle with the correct quantity
    cart_item, created = cart.items.get_or_create(variant=variant)
    cart_item.quantity = quantity
    cart_item.save()
        
    # Context for the template
    context = {
        'cart': cart,
        'total': total_price,
        'variant': variant,
        'quantity': quantity, # Pass quantity to the template
        'order_bumps': order_bumps, # Pass the bump offers to the template
        'stripe_public_key': getattr(settings, 'STRIPE_PUBLISHABLE_KEY', ''),
    }
    
    return render(request, 'awakening/partials/step_3_checkout.html', context)

# --- AJAX ENDPOINT: CREATE PAYMENT INTENT ---
def create_payment_intent(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            variant_id = data.get('variant_id')
            quantity = int(data.get('quantity', 1)) # Get quantity from JS
            bump_variant_id = data.get('bump_variant_id') # Get ID of selected bump offer

            variant = get_object_or_404(Variant, id=variant_id)
            
            # Get the cart for the webhook safety net
            cart = get_or_create_cart(request)

            # Calculate total amount including the optional order bump
            total_amount = variant.price * quantity
            if bump_variant_id:
                bump_variant = get_object_or_404(Variant, id=bump_variant_id)
                total_amount += bump_variant.price

            stripe.api_key = settings.STRIPE_SECRET_KEY

            intent = stripe.PaymentIntent.create(
                amount=int(total_amount * 100),  # Amount in pence
                currency='gbp',
                automatic_payment_methods={'enabled': True},
                # The metadata is the CRITICAL part for the webhook safety net.
                # It must contain everything the handle_payment_intent_checkout service needs.
                metadata={
                    # For the webhook to identify the cart and create the order
                    'product_type': 'ecommerce_cart', 
                    'cart_id': cart.id,
                    'bump_variant_id': bump_variant_id, # Pass bump to webhook
                    
                    # To link the order to the correct user
                    'user_id': request.user.id if request.user.is_authenticated else None,

                    # Funnel-specific tracking
                    'integration_check': 'accept_a_payment',
                    'funnel_name': 'awakening_npc_book',
                }
            )

            return JsonResponse({
                'client_secret': intent.client_secret
            })

        except Exception as e:
            return JsonResponse({'error': str(e)}, status=403)
            
    return JsonResponse({'error': 'Invalid request method'}, status=405)

# --- AJAX ENDPOINT: CREATE ORDER ---
@csrf_exempt # Use exempt for this API endpoint for simplicity, consider CSRF tokens for production
def create_order(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            variant = get_object_or_404(Variant, id=data.get('variant_id'))
            email = data.get('email')
            quantity = int(data.get('quantity', 1))
            bump_variant_id = data.get('bump_variant_id')

            payment_intent_id = data.get('payment_intent_id')

            # --- IDEMPOTENCY CHECK ---
            # Check if an order has already been created by the webhook safety net.
            # If so, use that order instead of creating a duplicate.
            existing_order = Order.objects.filter(stripe_checkout_id=payment_intent_id).first()
            if existing_order:
                # The webhook beat the client. Log it and use the existing order.
                return JsonResponse({'success': True, 'redirect_url': f'/awakening/order-success/{existing_order.id}/'})

            # Store donation details in shipping_data
            shipping_data = {
                'name': data.get('name'),
                'address': data.get('address'),
                'city': data.get('city'),
                'postcode': data.get('postcode'),
                'distribution': {
                    'keep': data.get('keep_count', 1),
                    'donate': quantity - int(data.get('keep_count', 1))
                }
            }
            
            # --- User Handling for Guests vs. Logged-in Users ---
            target_user = None
            if request.user.is_authenticated:
                target_user = request.user
            else:
                # For guests, find or create a user account to attach perks to.
                # This is crucial for high-value tiers.
                target_user, created = User.objects.get_or_create(
                    email=email,
                    defaults={
                        'username': email, 
                        'full_name': data.get('name', ''),
                        'is_client': True,
                    }
                )
                if created:
                    target_user.set_unusable_password()
                    target_user.save()
                # If user existed but name was blank, update it with the new data.
                elif not target_user.full_name and data.get('name'):
                    target_user.full_name = data.get('name')
                    target_user.save(update_fields=['full_name'])

            # Calculate total paid, including the bump
            total_paid = variant.price * quantity
            if bump_variant_id:
                bump_variant = get_object_or_404(Variant, id=bump_variant_id)
                total_paid += bump_variant.price

            # Create the order
            order = Order.objects.create(
                user=target_user,
                email=email,
                total_paid=total_paid,
                stripe_checkout_id=payment_intent_id, # Using stripe_checkout_id to store PI
                status=Order.STATUS_PAID,
                shipping_data=shipping_data,
            )
            
            # Create the order item
            OrderItem.objects.create(
                order=order,
                variant=variant,
                price=variant.price,
                quantity=quantity
            )

            # Create order item for the bump, if it exists
            if bump_variant_id:
                OrderItem.objects.create(
                    order=order,
                    variant=bump_variant,
                    price=bump_variant.price,
                    quantity=1
                )

            # --- DYNAMIC PERK ENROLLMENT (Works for Guests & Users) ---
            enrolled_offerings = []
            try:
                # Find the FunnelTier corresponding to the purchase
                purchased_tier = FunnelTier.objects.prefetch_related('perks__linked_offering').get(variant=variant, quantity=quantity)
                
                if purchased_tier and hasattr(target_user, 'client_profile'):
                    for perk in purchased_tier.perks.all():
                        if perk.linked_offering:
                            # Use get_or_create for idempotency, preventing duplicate enrollments
                            enrollment, created = ClientOfferingEnrollment.objects.get_or_create(
                                client=target_user.client_profile,
                                offering=perk.linked_offering,
                                defaults={'status': 'ACTIVE'}
                            )
                            if created:
                                enrolled_offerings.append(perk.linked_offering)
            except FunnelTier.DoesNotExist:
                # No specific tier matched, so no automatic enrollments.
                pass

            # If a new guest account was created AND they were enrolled in offerings, send access email.
            if not request.user.is_authenticated and enrolled_offerings:
                token = uuid.uuid4().hex
                target_user.billing_notes = token # Store token for verification
                target_user.save()

                mail_subject = "Your Access to the Inner Circle is Confirmed"
                message = render_to_string('awakening/emails/guest_enrollment_email.html', {
                    'user': target_user,
                    'enrolled_offerings': enrolled_offerings,
                    'token': token,
                })
                send_mail(mail_subject, message, settings.DEFAULT_FROM_EMAIL, [target_user.email], html_message=message)

            # Clear the cart
            cart = get_or_create_cart(request)
            cart.items.all().delete()

            # Return success and a redirect URL
            return JsonResponse({
                'success': True,
                'redirect_url': f'/awakening/order-success/{order.id}/'
            })

        except Exception as e:
            return JsonResponse({'error': str(e)}, status=400)
            
    return JsonResponse({'error': 'Invalid request method'}, status=405)


# --- ORDER SUCCESS PAGE ---
def order_success(request, order_number):
    """
    Renders different content/videos based on the Tier purchased.
    """
    order = get_object_or_404(Order, id=order_number)
    
    # Identify the main item quantity to determine Tier
    main_item = order.items.first()
    qty = main_item.quantity if main_item else 1

    # Default: Lone Wolf
    tier_data = {
        'title': "INITIATE PROTOCOL ACCEPTED",
        'message': "You have taken the first step. The manual is being dispatched to your coordinates. Do not share this information with unawakened NPCs.",
        'video_id': "dQw4w9WgXcQ", # REPLACE WITH REAL YOUTUBE ID
        'color_class': "text-green-500",
        'border_class': "border-green-900"
    }

    # Guild Member (Qty 100)
    if qty >= 100 and qty < 250:
        tier_data = {
            'title': "GUILD ACCESS GRANTED",
            'message': "Welcome to the inner circle. Your bulk distribution package is being prepared. The 'UI Optimization Protocol' has been unlocked in your account.",
            'video_id': "dQw4w9WgXcQ", # REPLACE WITH REAL GUILD VIDEO ID
            'color_class': "text-blue-400",
            'border_class': "border-blue-900"
        }

    # Raid Leader (Qty 250+)
    elif qty >= 250:
        tier_data = {
            'title': "SERVER ADMIN PRIVILEGES DETECTED",
            'message': "You have altered the simulation parameters. VIP Status confirmed. We are contacting you directly regarding the 'London Speedrun' logistics.",
            'video_id': "dQw4w9WgXcQ", # REPLACE WITH REAL VIP VIDEO ID
            'color_class': "text-purple-500", # Purple/Glitch Effect
            'border_class': "border-purple-900"
        }

    context = {'order': order, 'tier': tier_data}

    return render(request, 'awakening/success.html', context)
    
# --- SYSTEM LOG LORE API ---
def generate_agent_id():
    """Generates a cool looking ID like 'AGT-992' or 'USR-X7'"""
    prefix = random.choice(['AGT', 'USR', 'PLR', 'NOD', 'SYS'])
    nums = "".join(random.choices(string.digits, k=3))
    return f"{prefix}-{nums}"

def simulation_log_api(request):
    """
    Returns a random 'Server Event' for the frontend terminal.
    Includes the 'Both Pills' lore mechanic.
    """
    # 1. The "Awakening" Events (Sales/Conversions)
    success_events = [
        "PLAYER {id} HAS TAKEN THE RED PILL.",
        "NEW AGENT {id} RECRUITED TO THE GUILD.",
        "SOURCE CODE DOWNLOADED BY {id}.",
        "AWAKENING PROTOCOL INITIATED FOR {id}.",
        "{id} UNLOCKED: MAIN CHARACTER ENERGY.",
        "{id} EQUIPPED: 'THE COMBAT LOG'.",
    ]

    # 2. The "Failure" Events (Blue Pill / Staying Asleep)
    failure_events = [
        "NPC {id} CHOSE THE BLUE PILL.",
        "CONNECTION LOST: {id} REMAINED ASLEEP.",
        "SYSTEM: PLAYER {id} CHOSE TO STAY IN THE SIMULATION.",
        "ALERT: {id} FAILED TO WAKE UP.",
        "{id} RETURNED TO AUTO-PILOT MODE.",
    ]

    # 3. System Noise (Flavor Text)
    system_events = [
        "GLITCH DETECTED IN SECTOR 7...",
        "UPDATING GLOBAL PLAYER STATS...",
        "DECRYPTING MATRIX ARCHIVES...",
        "SERVER LOAD: 99% CAPACITY.",
        "ESTABLISHING SECURE UPLINK...",
    ]

    # 4. The "Both Pills" Events (Rare/High Status - Purple)
    infiltration_events = [
        "AGENT {id} SWALLOWED BOTH PILLS.",
        "SYSTEM ALERT: {id} IS RUNNING DUAL-BOOT PROTOCOL.",
        "{id} INFILTRATION SUCCESSFUL: MAPPING THE LEVEL.",
        "PLAYER {id} EQUIPPED: 'THE STEALTH GRIND'.", 
    ]

    # Weighted Randomness
    event_type = random.choices(
        ['success', 'failure', 'system', 'infiltration'], 
        weights=[35, 15, 40, 10], # 10% chance for Purple Lore
        k=1
    )[0]

    if event_type == 'success':
        msg = random.choice(success_events).format(id=generate_agent_id())
        color = "text-green-400" # Matrix Green
    elif event_type == 'failure':
        msg = random.choice(failure_events).format(id=generate_agent_id())
        color = "text-red-500" # Alert Red
    elif event_type == 'infiltration':
        msg = random.choice(infiltration_events).format(id=generate_agent_id())
        color = "text-purple-400" # Purple (Red + Blue)
    else:
        msg = random.choice(system_events)
        color = "text-gray-500" # Dim System Text

    return JsonResponse({
        'timestamp': timezone.now().strftime('%H:%M:%S'),
        'message': msg,
        'color': color
    })