import json
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
from .models import NewsletterSubscriber, NewsletterCampaign, CheatUsage
from .cheats import CHEAT_CODES
from .tasks import send_welcome_email_with_pdf_task, send_newsletter_blast_task, send_transactional_email_task

# ==============================================================================
# 1. FUNCTION-BASED VIEWS (Data-Driven Pages)
# ==============================================================================

def home(request):
    """Renders the home page."""
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
    Verifies a keystroke sequence against hidden server-side codes.
    """
    # 1. Rate Limiting (Prevent Brute Force)
    ip = request.META.get('REMOTE_ADDR')
    cache_key = f"cheat_attempts_{ip}"
    attempts = cache.get(cache_key, 0)
    
    if attempts >= 10: # Limit: 10 attempts per minute
        return JsonResponse({
            'status': 'error', 
            'message': '⛔ SYSTEM LOCKOUT: Too many failed attempts. Cooldown active.'
        }, status=429)
    
    # Increment counter (expires in 60s)
    cache.set(cache_key, attempts + 1, 60)

    try:
        data = json.loads(request.body)
        sequence = data.get('sequence', '').lower()

        # Check if the sequence matches any hidden code
        for code, effect in CHEAT_CODES.items():
            if code in sequence:
                # If it's a coupon action, we can generate the code here dynamically
                response_data = effect.copy()
                
                if effect.get('action') == 'coupon':
                    # Check Authentication
                    if not request.user.is_authenticated:
                        return JsonResponse({
                            'status': 'error',
                            'message': '🔒 Login required to save game progress and claim loot!'
                        })

                    # Dynamic Coupon Logic
                    now = timezone.now()
                    # Format: KONAMI-[USER_ID]-[YYYYMM]
                    code_name = f"KONAMI-{request.user.id}-{now.strftime('%Y%m')}"
                    
                    # Get or Create the coupon
                    coupon, created = Coupon.objects.get_or_create(
                        code=code_name,
                        defaults={
                            'discount_type': Coupon.DISCOUNT_TYPE_PERCENT,
                            'discount_value': 10,
                            'coupon_type': Coupon.COUPON_TYPE_DISCOUNT,
                            'free_shipping': True,
                            'active': True,
                            'usage_limit': 1,
                            'user_specific': request.user,
                            'valid_from': now,
                            'valid_to': now + datetime.timedelta(days=30),
                            'limit_to_product_type': Coupon.LIMIT_TYPE_ALL
                        }
                    )
                    
                    response_data['payload'] = coupon.code
                    if not created:
                        response_data['message'] = "⚠️ You already claimed this month's loot! Code retrieved."

                # Log the usage
                CheatUsage.objects.create(
                    code_used=code,
                    user=request.user if request.user.is_authenticated else None,
                    ip_address=ip,
                    action_triggered=effect.get('action', 'unknown')
                )

                return JsonResponse({'status': 'success', 'effect': response_data})

        return JsonResponse({'status': 'no_match'})

    except Exception as e:
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

def resend_welcome_email(request):
    """Resends the welcome email if the user just subscribed."""
    if request.method == 'POST':
        email = request.session.get('newsletter_email')
        if email:
            base_url = request.build_absolute_uri('/')
            send_welcome_email_with_pdf_task.delay(email, base_url)
            messages.success(request, f"Blueprint resent to {email}!")
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
        initial_data = {'subject': campaign.subject, 'content': campaign.content}

    if request.method == 'POST':
        form = StaffNewsletterForm(request.POST)
        if form.is_valid():
            subject = form.cleaned_data['subject']
            content = form.cleaned_data['content']
            
            if 'preview' in request.POST:
                # Render preview
                base_url = request.build_absolute_uri('/')
                unsubscribe_url = f"{base_url.rstrip('/')}/newsletter/unsubscribe/preview-token/"
                context = {'body': content, 'subject': subject, 'unsubscribe_url': unsubscribe_url}
                preview_html = render_to_string('core/generic_newsletter.html', context)
                return render(request, 'core/staff_newsletter.html', {'form': form, 'preview_html': preview_html})
            
            elif 'test_send' in request.POST:
                base_url = request.build_absolute_uri('/')
                unsubscribe_url = f"{base_url.rstrip('/')}/newsletter/unsubscribe/test-token/"
                context = {'body': content, 'subject': f"[TEST] {subject}", 'unsubscribe_url': unsubscribe_url}
                
                if request.user.email:
                    send_transactional_email_task.delay(
                        request.user.email, 
                        f"[TEST] {subject}", 
                        'core/generic_newsletter.html', 
                        context
                    )
                    messages.success(request, f"Test email sent to {request.user.email}")
                else:
                    messages.error(request, "No email address associated with your account.")
                return render(request, 'core/staff_newsletter.html', {'form': form})
            
            elif 'save_draft' in request.POST:
                if draft_id:
                    NewsletterCampaign.objects.filter(id=draft_id).update(subject=subject, content=content)
                else:
                    NewsletterCampaign.objects.create(subject=subject, content=content, status='DRAFT')
                messages.success(request, "Campaign saved as draft.")
                return redirect('core:staff_newsletter_history')
            
            elif 'send' in request.POST:
                base_url = request.build_absolute_uri('/')
                
                if draft_id:
                    campaign = NewsletterCampaign.objects.get(id=draft_id)
                    campaign.subject = subject
                    campaign.content = content
                    campaign.status = 'SENT'
                    campaign.sent_at = timezone.now()
                    campaign.save()
                else:
                    campaign = NewsletterCampaign.objects.create(
                        subject=subject, content=content, status='SENT', sent_at=timezone.now()
                    )
                
                send_newsletter_blast_task.delay(subject, content, base_url, campaign.id)
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