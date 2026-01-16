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
from coaching_core.models import Offering
from coaching_booking.models import ClientOfferingEnrollment
from .models import FunnelTier, OrderBump
from payments.models import Order, OrderItem

# --- THE CONTAINER ---
def funnel_landing(request):
    return render(request, 'awakening/partials/funnel_container.html')

# --- STEP 1: THE HOOK (Booklet) ---
def render_hook(request):
    return render(request, 'awakening/partials/step_1_hook.html')

# --- STEP 2: THE OFFERS (Tiers) ---
def render_offers(request):
    """
    Returns ONLY the pricing cards (Single, Multi, Co-Op).
    Filters out any active tiers that are missing a linked Variant to prevent NoReverseMatch errors.
    """
    # Fetch active tiers, ensuring they have a variant to prevent downstream errors.
    # Optimize DB queries with select_related and prefetch_related.
    active_tiers = FunnelTier.objects.filter(is_active=True)\
        .select_related('variant__product')\
        .prefetch_related('perks')
    
    # Pass the QuerySet directly. The template expects model instances.
    return render(request, 'awakening/partials/step_2_offers.html', {'tiers': active_tiers})

# --- STEP 3: THE CHECKOUT (Embedded) ---
def render_checkout(request, variant_id):
    variant = get_object_or_404(Variant, id=variant_id)
    # Get values from POST (sent via HTMX hx-include)
    quantity = int(request.POST.get('quantity', 1))
    keep_count = int(request.POST.get('keep_count', quantity)) 
    total_price = variant.price * quantity
    
    # Fetch the two active order bump offers
    order_bumps = OrderBump.objects.filter(is_active=True).select_related('variant')[:2]

    cart = get_or_create_cart(request)
    cart.items.all().delete() 
    
    cart_item, created = cart.items.get_or_create(variant=variant)
    cart_item.quantity = quantity
    cart_item.save()
        
    context = {
        'cart': cart,
        'total': total_price,
        'variant': variant,
        'quantity': quantity, # Pass quantity to the template
        'keep_count': keep_count, # Pass keep_count to the template
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
            quantity = int(data.get('quantity', 1))
            bump_variant_id = data.get('bump_variant_id')
            keep_count = int(data.get('keep_count', quantity)) # Captured for metadata

            variant = get_object_or_404(Variant, id=variant_id)
            cart = get_or_create_cart(request)

            # Calculate total amount including the optional order bump
            total_amount = variant.price * quantity
            if bump_variant_id:
                bump_variant = get_object_or_404(Variant, id=bump_variant_id)
                total_amount += bump_variant.price

            stripe.api_key = settings.STRIPE_SECRET_KEY

            intent = stripe.PaymentIntent.create(
                amount=int(total_amount * 100),
                currency='gbp',
                automatic_payment_methods={'enabled': True},
                metadata={
                    'product_type': 'ecommerce_cart', 
                    'cart_id': cart.id,
                    'bump_variant_id': bump_variant_id,
                    'user_id': request.user.id if request.user.is_authenticated else None,

                    'integration_check': 'accept_a_payment',
                    'funnel_name': 'awakening_npc_book',
                    'keep_count': keep_count, # Crucial: Stored for webhook fulfillment
                }
            )

            return JsonResponse({'client_secret': intent.client_secret})

        except Exception as e:
            return JsonResponse({'error': str(e)}, status=403)
            
    return JsonResponse({'error': 'Invalid request method'}, status=405)

# --- AJAX ENDPOINT: CREATE ORDER ---
@csrf_exempt
def create_order(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            variant = get_object_or_404(Variant, id=data.get('variant_id'))
            email = data.get('email')
            quantity = int(data.get('quantity', 1))
            bump_variant_id = data.get('bump_variant_id')
            payment_intent_id = data.get('payment_intent_id')

            existing_order = Order.objects.filter(stripe_checkout_id=payment_intent_id).first()
            if existing_order:
                return JsonResponse({'success': True, 'redirect_url': f'/awakening/order-success/{existing_order.id}/'})

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
            
            target_user = None
            if request.user.is_authenticated:
                target_user = request.user
            else:
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
                elif not target_user.full_name and data.get('name'):
                    target_user.full_name = data.get('name')
                    target_user.save(update_fields=['full_name'])

            total_paid = variant.price * quantity
            if bump_variant_id:
                bump_variant = get_object_or_404(Variant, id=bump_variant_id)
                total_paid += bump_variant.price

            order = Order.objects.create(
                user=target_user,
                email=email,
                total_paid=total_paid,
                stripe_checkout_id=payment_intent_id,
                status=Order.STATUS_PAID,
                shipping_data=shipping_data,
            )
            
            OrderItem.objects.create(
                order=order,
                variant=variant,
                price=variant.price,
                quantity=quantity
            )

            if bump_variant_id:
                OrderItem.objects.create(
                    order=order,
                    variant=bump_variant,
                    price=bump_variant.price,
                    quantity=1
                )

            # --- DYNAMIC PERK ENROLLMENT ---
            enrolled_offerings = []
            try:
                purchased_tier = FunnelTier.objects.prefetch_related('perks__linked_offering').get(variant=variant, quantity=quantity)                
                from coaching_client.models import ClientProfile
                client_profile, _ = ClientProfile.objects.get_or_create(user=target_user)

                from coaching_client.models import ClientProfile
                
                # Ensure ClientProfile exists for the user
                client_profile, _ = ClientProfile.objects.get_or_create(user=target_user)

                if purchased_tier:
                    for perk in purchased_tier.perks.all():
                        if perk.linked_offering:
                            enrollment, created = ClientOfferingEnrollment.objects.get_or_create(
                                client=client_profile,
                                offering=perk.linked_offering,
                                defaults={'status': 'ACTIVE'}
                            )
                            if created:
                                enrolled_offerings.append(perk.linked_offering)
            except FunnelTier.DoesNotExist:
                pass

            if not request.user.is_authenticated and enrolled_offerings:
                token = uuid.uuid4().hex
                target_user.billing_notes = token 
                target_user.save()

                mail_subject = "Your Access to the Inner Circle is Confirmed"
                message = render_to_string('awakening/emails/guest_enrollment_email.html', {
                    'user': target_user,
                    'enrolled_offerings': enrolled_offerings,
                    'token': token,
                })
                send_mail(mail_subject, message, settings.DEFAULT_FROM_EMAIL, [target_user.email], html_message=message)

            cart = get_or_create_cart(request)
            cart.items.all().delete()

            return JsonResponse({
                'success': True,
                'redirect_url': f'/awakening/order-success/{order.id}/'
            })

        except Exception as e:
            return JsonResponse({'error': str(e)}, status=400)
            
    return JsonResponse({'error': 'Invalid request method'}, status=405)


# (Remaining views: order_success, generate_agent_id, simulation_log_api remain unchanged)
def order_success(request, order_number):
    order = get_object_or_404(Order, id=order_number)
    main_item = None
    bump_item = None
    linked_perks = []
    
    all_items = order.items.all()
    for item in all_items:
        is_main_tier_item = FunnelTier.objects.filter(variant=item.variant, quantity=item.quantity).exists()
        if is_main_tier_item and not main_item:
            main_item = item
        else:
            bump_item = item

    if not main_item and all_items:
        main_item = all_items.first()

    if main_item:
        try:
            purchased_tier = FunnelTier.objects.get(variant=main_item.variant, quantity=main_item.quantity)
            linked_perks = purchased_tier.perks.filter(link_url__isnull=False).exclude(link_url__exact='')
        except FunnelTier.DoesNotExist:
            pass

    qty = main_item.quantity if main_item else 0
    tier_data = {
        'title': "INITIATE PROTOCOL ACCEPTED",
        'message': "Manual dispatched. Do not share with NPCs.",
        'video_id': "dQw4w9WgXcQ", 
        'color_class': "text-green-500",
        'border_class': "border-green-900"
    }

    if qty >= 100 and qty < 250:
        tier_data = {
            'title': "GUILD ACCESS GRANTED",
            'message': "Welcome to the inner circle. Distribution package prepared.",
            'video_id': "dQw4w9WgXcQ", 
            'color_class': "text-blue-400",
            'border_class': "border-blue-900"
        }
    elif qty >= 250:
        tier_data = {
            'title': "SERVER ADMIN PRIVILEGES",
            'message': "Simulation parameters altered. VIP Status confirmed.",
            'video_id': "dQw4w9WgXcQ", 
            'color_class': "text-purple-500", 
            'border_class': "border-purple-900"
        }

    context = {
        'order': order,
        'tier': tier_data,
        'main_item': main_item,
        'bump_item': bump_item,
        'linked_perks': linked_perks,
    }

    return render(request, 'awakening/success.html', context)
    
def generate_agent_id():
    prefix = random.choice(['AGT', 'USR', 'PLR', 'NOD', 'SYS'])
    nums = "".join(random.choices(string.digits, k=3))
    return f"{prefix}-{nums}"

def simulation_log_api(request):
    """
    Returns a random 'Server Event' for the frontend terminal.
    """
    success_events = [
        "PLAYER {id} HAS TAKEN THE RED PILL.",
        "NEW AGENT {id} RECRUITED TO THE GUILD.",
        "SOURCE CODE DOWNLOADED BY {id}.",
        "AWAKENING PROTOCOL INITIATED FOR {id}.",
        "{id} UNLOCKED: MAIN CHARACTER ENERGY.",
        "{id} EQUIPPED: 'THE COMBAT LOG'.",
    ]
    failure_events = [
        "NPC {id} CHOSE THE BLUE PILL.",
        "CONNECTION LOST: {id} REMAINED ASLEEP.",
        "SYSTEM: PLAYER {id} CHOSE TO STAY IN THE SIMULATION.",
        "ALERT: {id} FAILED TO WAKE UP.",
        "{id} RETURNED TO AUTO-PILOT MODE.",
    ]
    system_events = [
        "GLITCH DETECTED IN SECTOR 7...",
        "UPDATING GLOBAL PLAYER STATS...",
        "DECRYPTING MATRIX ARCHIVES...",
        "SERVER LOAD: 99% CAPACITY.",
        "ESTABLISHING SECURE UPLINK...",
    ]
    infiltration_events = [
        "AGENT {id} SWALLOWED BOTH PILLS.",
        "SYSTEM ALERT: {id} IS RUNNING DUAL-BOOT PROTOCOL.",
        "{id} INFILTRATION SUCCESSFUL: MAPPING THE LEVEL.",
        "PLAYER {id} EQUIPPED: 'THE STEALTH GRIND'.", 
    ]

    event_type = random.choices(
        ['success', 'failure', 'system', 'infiltration'], 
        weights=[35, 15, 40, 10], 
        k=1
    )[0]

    if event_type == 'success':
        msg = random.choice(success_events).format(id=generate_agent_id())
        color = "text-green-400"
    elif event_type == 'failure':
        msg = random.choice(failure_events).format(id=generate_agent_id())
        color = "text-red-500"
    elif event_type == 'infiltration':
        msg = random.choice(infiltration_events).format(id=generate_agent_id())
        color = "text-purple-400"
    else:
        msg = random.choice(system_events)
        color = "text-gray-500"

    return JsonResponse({
        'timestamp': timezone.now().strftime('%H:%M:%S'),
        'message': msg,
        'color': color
    })