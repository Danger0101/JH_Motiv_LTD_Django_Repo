from django.shortcuts import render
from django.views.generic import TemplateView
from django.http import HttpResponse
from django.views.decorators.http import require_POST

# Import data files
from .faq_data import FAQ_DATA
from .privacy_policy_data import PRIVACY_POLICY_DATA
from .tos_data import TOS_DATA
from .refund_policy_data import REFUND_POLICY_DATA
from .shipping_policy_data import SHIPPING_POLICY_DATA
from .about_data import ABOUT_DATA
from dreamers.models import DreamerProfile # From the new app

# ==============================================================================
# 1. FUNCTION-BASED VIEWS (Data-Driven Pages)
# ==============================================================================

def home(request):
    """Renders the home page."""
    return render(request, 'core/home.html')

def about_page(request): 
    """Renders the About page, fetching dynamic Dreamer data."""
    
    # Fetches all dreamer profiles, pre-fetching their associated channel links
    dreamers = DreamerProfile.objects.prefetch_related('channels').all()
    
    context = {
        'about_data': ABOUT_DATA,
        'dreamer_profiles': dreamers, 
    }
    
    return render(request, 'core/about.html', context)

def faqs_page(request): 
    """Renders the FAQ page with structured data for Alpine.js tabs/accordions."""
    return render(request, 'core/faqs.html', {'faq_data': FAQ_DATA}) 

def privacy_policy_page(request):
    """Renders the Privacy Policy page with data and Alpine.js tabs."""
    return render(request, 'core/privacy_policy.html', {'policy_data': PRIVACY_POLICY_DATA})

def terms_of_service_page(request): 
    """Renders the Terms of Service page with data and Alpine.js tabs."""
    return render(request, 'core/terms_of_service.html', {'tos_data': TOS_DATA})

def refund_policy_page(request):
    """Renders the Refund Policy page with data and Alpine.js tabs."""
    return render(request, 'core/refund_policy.html', {'refund_data': REFUND_POLICY_DATA})

def shipping_policy_page(request):
    """Renders the Shipping Policy page with data."""
    return render(request, 'core/shipping_policy.html', {'shipping_data': SHIPPING_POLICY_DATA})

@require_POST
def set_cookie_consent(request):
    """
    Sets a cookie to store the user's consent choice (via HTMX).
    """
    consent_value = request.POST.get('consent_value')
    if consent_value in ['accepted', 'rejected']:
        response = HttpResponse(status=204)
        response.set_cookie('user_consent', consent_value, max_age=31536000, samesite='Lax', secure=True)
        return response
    return HttpResponse('Invalid consent value.', status=400)

