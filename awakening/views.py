import random
import string
from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse, HttpResponse
from django.utils import timezone
from django.conf import settings
from products.models import Product, Variant
from cart.utils import get_or_create_cart

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
    """
    # Fetch your 3 variants for the book
    # Ensure you have created these in Admin!
    product = Product.objects.filter(name__icontains="Stop Being an NPC").first()
    
    if product:
        variants = product.variants.filter(is_active=True).order_by('price')
    else:
        variants = []

    return render(request, 'awakening/partials/step_2_offers.html', {'variants': variants})

# --- STEP 3: THE CHECKOUT (Embedded) ---
def render_checkout(request, variant_id):
    """
    1. Adds item to cart (background).
    2. Returns the STRIPE FORM fragment.
    """
    variant = get_object_or_404(Variant, id=variant_id)
    cart = get_or_create_cart(request)
    
    # STRICT FUNNEL RULE: Empty cart first
    # This ensures they aren't buying a t-shirt + the book accidentally
    cart.items.all().delete() 
    
    # Add the selected bundle
    cart_item, created = cart.items.get_or_create(variant=variant)
    if not created:
        cart_item.quantity = 1
        cart_item.save()
        
    # Context for the template
    context = {
        'cart': cart,
        'total': variant.price,
        'variant': variant,
        'stripe_public_key': settings.STRIPE_PUBLIC_KEY,
        # Note: You would normally generate a PaymentIntent client_secret here
        # For now, we will let your existing payments JS handle the intent creation via AJAX
    }
    
    return render(request, 'awakening/partials/step_3_checkout.html', context)

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