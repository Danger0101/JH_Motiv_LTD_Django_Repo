import json
import logging
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.http import HttpResponse, JsonResponse
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import ensure_csrf_cookie
from django.utils import timezone
from payments.models import Coupon
import datetime
import functools
from django.template.loader import render_to_string
from django.contrib.admin.views.decorators import staff_member_required
try:
    import weasyprint
except (OSError, ImportError):
    weasyprint = None

from django.core import signing
from django.core.cache import cache

# Import data files
from .faq_data import FAQ_DATA
from .privacy_policy_data import PRIVACY_POLICY_DATA
from .tos_data import TOS_DATA
from .refund_policy_data import REFUND_POLICY_DATA
from .shipping_policy_data import SHIPPING_POLICY_DATA
from .about_data import ABOUT_DATA
from cart.utils import get_or_create_cart, get_cart_summary_data
from dreamers.models import DreamerProfile
from team.models import TeamMember
from products.models import Product
from .forms import NewsletterSubscriptionForm, StaffNewsletterForm
from .models import NewsletterSubscriber, NewsletterCampaign, CheatUsage, EmailResendLog
from .cheats import CHEAT_CODES
from .tasks import send_welcome_email_with_pdf_task, send_newsletter_blast_task, send_transactional_email_task, send_campaign_blast_task

logger = logging.getLogger(__name__)

# ==============================================================================
# 1. FUNCTION-BASED VIEWS (Data-Driven Pages)
# ==============================================================================

def home(request):
    """Renders the home page."""
    try:
        products = Product.objects.filter(is_active=True).order_by('-created_at')[:4] # Fetch 4 most recent active products
        team_members = TeamMember.objects.filter(is_active=True)
        cart = get_or_create_cart(request)
        summary = get_cart_summary_data(cart)
        context = {
            'featured_products': products,
            'team_members': team_members,
            'summary': summary,
        }
        return render(request, 'home.html', context)
    except Exception as e:
        logger.error(f"Error rendering home page: {e}", exc_info=True)
        raise

def product_detail(request, slug):
    """Renders the product detail page."""
    product = get_object_or_404(Product, slug=slug, is_active=True)
    
    # --- PREPARE VARIANT DATA FOR ALPINEJS ---
    variants = product.variants.all()
    variant_lookup = {}
    unique_colors = set()
    unique_sizes = set()
    any_stock = False

    for variant in variants:
        # Create lookup key: "Color_Size"
        key = f"{variant.color}_{variant.size}"
        
        # Determine stock status safely (default to 0 if field missing)
        stock_count = getattr(variant, 'stock', 0)
        in_stock = (stock_count if stock_count is not None else 0) > 0
        
        if in_stock:
            any_stock = True
            
        variant_lookup[key] = {
            'id': variant.id,
            'price': float(variant.price),
            'in_stock': in_stock
        }
        
        # Collect unique attributes. Default hex to black if missing.
        hex_code = getattr(variant, 'hex_code', '#000000') 
        unique_colors.add((variant.color, hex_code))
        unique_sizes.add(variant.size)

    context = {
        'product': product,
        'variant_lookup_json': json.dumps(variant_lookup),
        'unique_colors': list(unique_colors),
        'unique_sizes': sorted(list(unique_sizes)),
        'show_color_selector': len(unique_colors) > 0 and not (len(unique_colors) == 1 and list(unique_colors)[0][0] == "Default"),
        'show_size_selector': len(unique_sizes) > 0 and not (len(unique_sizes) == 1 and list(unique_sizes)[0] == "One Size"),
        'is_sold_out': variants.exists() and not any_stock,
    }
    return render(request, 'products/product_detail.html', context)

@require_POST
def add_to_cart(request, product_id):
    """Adds a product to the cart."""
    cart = get_or_create_cart(request)
    product = get_object_or_404(Product, id=product_id, is_active=True)
    
    # Get variations from the form
    size = request.POST.get('size')
    color = request.POST.get('color')

    from django.apps import apps
    CartItem = apps.get_model('cart', 'CartItem')
    
    cart_item, created = CartItem.objects.get_or_create(cart=cart, product=product, size=size, color=color)
    if not created:
        cart_item.quantity += 1
        cart_item.save()

    if request.headers.get('HX-Request'):
        response = HttpResponse(status=204)
        response['HX-Trigger'] = 'loot-acquired'
        return response
        
    messages.success(request, f"Added {product} to cart!")
    return redirect(request.META.get('HTTP_REFERER', 'core:home'))

def about_page(request): 
    """Renders the About page, fetching dynamic Dreamer and Team data."""

    # 1. Fetch Dreamers
    dreamers = DreamerProfile.objects.prefetch_related('channels').all()

    # 2. Fetch Active Team Members
    team_members = TeamMember.objects.filter(is_active=True).all()

    context = {
        'about_data': ABOUT_DATA,
        'dreamer_profiles': dreamers,
        'team_members': team_members,
    }

    return render(request, 'core/about.html', context)

def faqs_page(request): 
    """Renders the FAQ page with structured data for Alpine.js tabs/accordions."""
    context = {
        'faq_items': FAQ_DATA.get('retail', []),
        'category': 'retail'
    } # Default to retail
    
    # For an HTMX request, render only the content partial.
    if request.htmx:
        return render(request, 'core/partials/faq_tab_content.html', context)
    
    return render(request, 'core/faqs.html', context)

def faq_tab(request, category):
    """
    HTMX view to fetch and render FAQ content for a specific category.
    """
    # Get the list of FAQs for the requested category, default to an empty list if not found.
    faq_items = FAQ_DATA.get(category, [])
    context = {
        'faq_items': faq_items,
        'category': category
    }
    
    if request.htmx:
        # Render only the partial containing the list of questions and answers.
        return render(request, 'core/partials/faq_tab_content.html', context)

    return render(request, 'core/faqs.html', context)

def privacy_policy_page(request):
    """Renders the Privacy Policy page with data and Alpine.js tabs."""
    
    # --- HTMX FRAGMENT HANDLING FOR POPUP ---
    if request.headers.get('hx-request'):
        # If HTMX requests this view, render only the content fragment
        return render(request, 'core/partials/policy_content_fragment.html', {'policy_data': PRIVACY_POLICY_DATA, 'policy_type': 'privacy'})

    return render(request, 'core/privacy_policy.html', {'policy_data': PRIVACY_POLICY_DATA})

def terms_of_service_page(request): 
    """Renders the Terms of Service page with data and Alpine.js tabs."""

    # --- HTMX FRAGMENT HANDLING FOR POPUP ---
    if request.headers.get('hx-request'):
        # If HTMX requests this view, render only the content fragment
        return render(request, 'core/partials/policy_content_fragment.html', {'policy_data': TOS_DATA, 'policy_type': 'tos'})

    return render(request, 'core/terms_of_service.html', {'tos_data': TOS_DATA})

def refund_policy_page(request):
    """Renders the Refund Policy page with data and Alpine.js tabs."""
    return render(request, 'core/refund_policy.html', {'refund_data': REFUND_POLICY_DATA})

def shipping_policy_page(request):
    """Renders the Shipping Policy page with data."""
    return render(request, 'core/shipping_policy.html', {'shipping_data': SHIPPING_POLICY_DATA})

@require_POST
def claim_konami_coupon(request):
    """
    Easter Egg: Generates a 10% Off + Free Shipping coupon for the authenticated user.
    Limit: Once per month per user.
    """
    if not request.user.is_authenticated:
        return JsonResponse({
            'status': 'error', 
            'message': '🔒 ACCESS DENIED: Login required to save game progress and claim loot!'
        }, status=403)

    now = timezone.now()
    # Unique code format: CHEATCODE-[USER_ID]-[YYYY-MM]
    # e.g., CHEATCODE-42-2023-10
    code_name = f"CHEATCODE-{request.user.id}-{now.strftime('%Y-%m')}"

    # Check if this specific monthly code already exists
    if Coupon.objects.filter(code=code_name).exists():
        return JsonResponse({
            'status': 'info', 
            'message': '⚠️ Loot box already opened this month! Cooldown active.'
        })

    # Create the coupon
    expiry = now + datetime.timedelta(days=30)
    coupon = Coupon.objects.create(
        code=code_name,
        discount_type=Coupon.DISCOUNT_TYPE_PERCENT,
        discount_value=10,
        coupon_type=Coupon.COUPON_TYPE_DISCOUNT,
        free_shipping=True,
        active=True,
        usage_limit=1,
        user_specific=request.user,
        valid_from=now,
        valid_to=expiry,
        limit_to_product_type=Coupon.LIMIT_TYPE_ALL
    )

    return JsonResponse({
        'status': 'success', 
        'message': f'🎉 CHEAT ACTIVATED! Code: {code_name} (10% Off + Free Shipping)',
        'code': code_name
    })

@require_POST
def verify_cheat_code(request):
    """
    Verifies a Cheat ID sent by the client.
    The client handles the key matching and hashing; the server handles the reward.
    """
    try:
        data = json.loads(request.body)

        try:
            cheat_id = int(data.get('cheat_id'))
        except (TypeError, ValueError):
            return JsonResponse({'status': 'invalid_format'}, status=400)

        if cheat_id not in CHEAT_CODES:
            return JsonResponse({'status': 'invalid_id'}, status=400)

        # Retrieve config for this ID (e.g. "konami")
        effect_config = CHEAT_CODES[cheat_id]
        response_data = effect_config.copy()

        # --- LOGIC: COUPON GENERATION ---
        if effect_config.get('action') == 'coupon':
            if not request.user.is_authenticated:
                return JsonResponse({
                    'status': 'success', # Technically a success in matching, but logic fails
                    'effect': {
                        'message': '🔒 Log in to save your progress and claim this reward!'
                    }
                })

            # Create Unique Coupon
            code = f"KONAMI-{request.user.id}-{timezone.now().strftime('%Y')}"
            coupon, created = Coupon.objects.get_or_create(
                code=code,
                defaults={
                    'discount_type': Coupon.DISCOUNT_TYPE_PERCENT,
                    'discount_value': 10,
                    'active': True,
                    'usage_limit': 1,
                    'user_specific': request.user,
                    'valid_from': timezone.now(),
                    'valid_to': timezone.now() + datetime.timedelta(days=30),
                }
            )
            
            response_data['payload'] = coupon.code
            response_data['message'] = "Cheat Activated! Coupon generated."
            if not created:
                response_data['message'] = "You already discovered this secret! Code retrieved."

        # Log usage
        if request.user.is_authenticated:
            CheatUsage.objects.create(
                user=request.user,
                code_used=str(cheat_id),
                ip_address=request.META.get('REMOTE_ADDR'),
                action_triggered=effect_config.get('action', 'unknown')
            )

        return JsonResponse({'status': 'success', 'effect': response_data})

    except Exception as e:
        logger.error(f"Cheat Error: {e}")
        return JsonResponse({'status': 'error', 'message': str(e)}, status=400)

@require_POST
def set_cookie_consent(request):
    """
    Sets a cookie to store the user's consent choice (via HTMX).
    """
    consent_value = request.POST.get('consent_value')
    if consent_value in ['accepted', 'rejected']:
        response = HttpResponse(status=204)
        response.set_cookie('user_consent', consent_value, max_age=31536000, samesite='Lax', secure=True)
        
        if consent_value == 'accepted':
            response['HX-Trigger'] = 'cookieConsentAccepted'
            
        return response
    return HttpResponse('Invalid consent value.', status=400)

def error_simulation_view(request, error_code):
    """
    Easter Egg View: Manually renders error templates so users can see the designs.
    """
    valid_codes = [403, 404, 500]
    
    if error_code not in valid_codes:
        # If they try a code we don't have a template for, send them home
        return redirect('home')
        
    # Render the specific template (e.g., '403.html', '404.html')
    return render(request, f'{error_code}.html', status=200)

# Use this decorator if you only want Admin/Staff to generate it
# @staff_member_required 
def download_blueprint_pdf(request):
    """
    Generates the Game Master's Blueprint PDF.
    """
    if weasyprint is None:
        return HttpResponse("PDF generation is not available on this server.", status=503)

    # 1. Render HTML with context data if needed (static for now)
    html_string = render_to_string('pdfs/game_master_blueprint.html', request=request)

    # 2. Convert to PDF using WeasyPrint
    pdf_file = weasyprint.HTML(string=html_string, base_url=request.build_absolute_uri()).write_pdf()

    # 3. Create HTTP Response
    response = HttpResponse(pdf_file, content_type='application/pdf')
    
    # 'attachment' forces download; 'inline' opens in browser
    response['Content-Disposition'] = 'inline; filename="Game_Masters_Blueprint.pdf"'
    
    return response

def subscribe_newsletter(request):
    """
    Handles newsletter subscription and sends the welcome PDF.
    """
    if request.method == 'POST':
        # Check if user is already subscribed
        email = request.POST.get('email')
        if email:
            subscriber = NewsletterSubscriber.objects.filter(email=email).first()
            if subscriber and subscriber.is_active:
                request.session['manage_newsletter_email'] = email
                return redirect('core:newsletter_manage')

        form = NewsletterSubscriptionForm(request.POST)
        if form.is_valid():
            subscriber = form.save()
            
            # Store email in session for resend functionality
            request.session['newsletter_email'] = subscriber.email
            
            # Send Welcome Email with PDF
            base_url = request.build_absolute_uri('/')
            send_welcome_email_with_pdf_task.delay(subscriber.email, base_url)
            
            # messages.success(request, "Welcome to the Guild! Check your inbox for the Blueprint.")
            return redirect('core:newsletter_thank_you')
    else:
        form = NewsletterSubscriptionForm()
    
    return render(request, 'core/newsletter_signup.html', {'form': form})

def newsletter_thank_you(request):
    """Renders the newsletter thank you page."""
    return render(request, 'core/newsletter_thank_you.html')

def newsletter_manage(request):
    """
    Renders a menu for existing subscribers to manage their subscription (unsubscribe).
    """
    email = request.session.get('manage_newsletter_email')
    if not email:
        return redirect('home')
    
    # Calculate cooldown remaining for the UI
    last_sent = request.session.get('last_resend_timestamp', 0)
    # Ensure last_sent is a float (handle potential string/None from session)
    try:
        last_sent = float(last_sent) if last_sent is not None else 0.0
    except (ValueError, TypeError):
        last_sent = 0.0

    now = timezone.now().timestamp()
    cooldown_remaining = max(0, int(60 - (now - last_sent)))

    return render(request, 'core/newsletter_manage.html', {'email': email, 'cooldown_remaining': cooldown_remaining})

def newsletter_unsubscribe_manual(request):
    """
    Process manual unsubscribe request from the manage menu.
    """
    if request.method == 'POST':
        email = request.session.get('manage_newsletter_email')
        if email:
            NewsletterSubscriber.objects.filter(email=email).update(is_active=False)
            if 'manage_newsletter_email' in request.session:
                del request.session['manage_newsletter_email']
            return render(request, 'core/newsletter_unsubscribe.html')
    return redirect('home')

def resend_welcome_email(request):
    """Resends the welcome email with a cooldown."""
    if request.method == 'POST':
        # 1. Determine Redirect Target
        target = 'core:newsletter_thank_you'
        if request.session.get('manage_newsletter_email'):
            target = 'core:newsletter_manage'

        # 2. Cooldown Check (60 seconds)
        last_sent = request.session.get('last_resend_timestamp', 0)
        # Ensure last_sent is a float
        try:
            last_sent = float(last_sent) if last_sent is not None else 0.0
        except (ValueError, TypeError):
            last_sent = 0.0
            
        current_time = timezone.now().timestamp()
        if current_time - last_sent < 60:
            messages.warning(request, "Please wait a minute before resending.")
            return redirect(target)

        # 3. Send Email
        email = request.session.get('newsletter_email')
        if not email:
            email = request.session.get('manage_newsletter_email')

        if email:
            base_url = request.build_absolute_uri('/')
            send_welcome_email_with_pdf_task.delay(email, base_url)
            request.session['last_resend_timestamp'] = current_time
            
            # Log the attempt for security auditing
            ip = request.META.get('REMOTE_ADDR')
            user_agent = request.META.get('HTTP_USER_AGENT', '')
            EmailResendLog.objects.create(
                email=email, ip_address=ip, user_agent=user_agent
            )
            
            messages.success(request, f"Blueprint resent to {email}!")
            return redirect(target)
        else:
            messages.error(request, "Session expired. Please subscribe again.")
    return redirect('core:newsletter_thank_you')

def unsubscribe_newsletter(request, token):
    """Handles the unsubscribe action via signed token."""
    try:
        email = signing.loads(token, salt='newsletter-unsubscribe')
        subscriber = NewsletterSubscriber.objects.get(email=email)
        subscriber.is_active = False
        subscriber.save()
        return render(request, 'core/newsletter_unsubscribe.html')
    except (signing.BadSignature, NewsletterSubscriber.DoesNotExist):
        return render(request, 'core/newsletter_unsubscribe.html', {'error': 'Invalid or expired link.'})

@staff_member_required
def staff_newsletter_dashboard(request):
    """
    Staff dashboard to send newsletters to all subscribers.
    """
    # Check if we are loading a draft
    draft_id = request.GET.get('draft_id')
    initial_data = {}
    if draft_id:
        campaign = get_object_or_404(NewsletterCampaign, id=draft_id, status='DRAFT')
        initial_data = {'subject': campaign.subject, 'content': campaign.content, 'template': campaign.template}

    if request.method == 'POST':
        form = StaffNewsletterForm(request.POST, request.FILES)
        if form.is_valid():
            subject = form.cleaned_data['subject']
            content = form.cleaned_data['content']
            template = form.cleaned_data['template']
            header_image = form.cleaned_data.get('header_image')
            
            # Helper to get base URL
            base_url = request.build_absolute_uri('/').rstrip('/')
            
            if 'preview' in request.POST:
                # Render preview
                # FIX: Explicitly create a dummy token for preview
                unsubscribe_url = f"{base_url}/newsletter/unsubscribe/preview-token/"
                
                # Handle the image for preview
                header_image_url = None
                if header_image:
                    # Note: Handling temp image previews is complex. 
                    # We pass here, relying on saved drafts or placeholders if needed.
                    pass 
                elif draft_id:
                    campaign = NewsletterCampaign.objects.get(id=draft_id)
                    if campaign.header_image:
                        header_image_url = campaign.header_image.url

                # Create context compatible with both generic (uses 'body') and layout templates (uses 'newsletter.body')
                newsletter_data = {
                    'subject': subject, 
                    'body': content,
                    'header_image': {'url': header_image_url} if header_image_url else None
                }
                context = {
                    'newsletter': newsletter_data, 
                    'body': content, 
                    'subject': subject, 
                    'unsubscribe_url': unsubscribe_url, 
                    'base_url': base_url
                }
                template_name = f"emails/newsletters/layout_{template}.html"
                preview_html = render_to_string(template_name, context)
                return render(request, 'core/staff_newsletter.html', {'form': form, 'preview_html': preview_html})
            
            elif 'test_send' in request.POST:
                # FIX: Create a dummy token for test emails so the link works (visually)
                unsubscribe_url = f"{base_url}/newsletter/unsubscribe/test-token/"
                
                newsletter_data = {'subject': subject, 'body': content}
                context = {
                    'newsletter': newsletter_data,
                    'body': content, 
                    'subject': f"[TEST] {subject}", 
                    'unsubscribe_url': unsubscribe_url, 
                    'base_url': base_url
                }
                
                template_name = f"emails/newsletters/layout_{template}.html"
                
                if request.user.email:
                    # FIX: Pass the context directly. 
                    # The task expects 'context' to contain everything the template needs.
                    send_transactional_email_task.delay(
                        request.user.email, 
                        f"[TEST] {subject}", 
                        template_name, 
                        context
                    )
                    messages.success(request, f"Test email sent to {request.user.email}")
                else:
                    messages.error(request, "No email address associated with your account.")
                return render(request, 'core/staff_newsletter.html', {'form': form})
            
            elif 'save_draft' in request.POST:
                if draft_id:
                    campaign = NewsletterCampaign.objects.get(id=draft_id)
                    campaign.subject = subject
                    campaign.content = content
                    campaign.template = template
                    if header_image:
                        campaign.header_image = header_image
                    campaign.save()
                else:
                    NewsletterCampaign.objects.create(subject=subject, content=content, status='DRAFT', template=template, header_image=header_image)
                messages.success(request, "Campaign saved as draft.")
                return redirect('core:staff_newsletter_history')
            
            elif 'send' in request.POST:
                base_url = request.build_absolute_uri('/')
                
                if draft_id:
                    campaign = NewsletterCampaign.objects.get(id=draft_id)
                    campaign.subject = subject
                    campaign.content = content
                    campaign.template = template
                    if header_image:
                        campaign.header_image = header_image
                    campaign.status = 'SENT'
                    campaign.sent_at = timezone.now()
                    campaign.save()
                else:
                    campaign = NewsletterCampaign.objects.create(
                        subject=subject, content=content, status='SENT', sent_at=timezone.now(), template=template, header_image=header_image
                    )
                
                send_campaign_blast_task.delay(subject, content, base_url, campaign.id)
                messages.success(request, "Newsletter queued for sending!")
                return redirect('core:staff_newsletter_dashboard')
    else:
        form = StaffNewsletterForm(initial=initial_data)
    
    return render(request, 'core/staff_newsletter.html', {'form': form})

@staff_member_required
def staff_newsletter_history(request):
    """
    Displays a log of past newsletter campaigns.
    """
    campaigns = NewsletterCampaign.objects.order_by('-created_at')
    return render(request, 'core/staff_newsletter_history.html', {'campaigns': campaigns})