from django.shortcuts import render
from django.views.generic import TemplateView
from django.http import HttpResponse
from django.views.decorators.http import require_POST

# Import data files
from .faq_data import FAQ_DATA
from .privacy_policy_data import PRIVACY_POLICY_DATA
from .tos_data import TOS_DATA

def home(request):
    """Renders the home page."""
    return render(request, 'core/home.html')

def faqs_page(request): 
    """Renders the FAQ page with structured data for Alpine.js tabs/accordions."""
    return render(request, 'core/faqs.html', {'faq_data': FAQ_DATA}) 

def privacy_policy_page(request):
    """Renders the Privacy Policy page with data and Alpine.js tabs."""
    return render(request, 'core/privacy_policy.html', {'policy_data': PRIVACY_POLICY_DATA})

def terms_of_service_page(request):
    """Renders the Terms of Service page with data and Alpine.js tabs."""
    return render(request, 'core/terms_of_service.html', {'tos_data': TOS_DATA})

@require_POST
def set_cookie_consent(request):
    consent_value = request.POST.get('consent_value')
    if consent_value in ['accepted', 'rejected']:
        response = HttpResponse(status=204)
        response.set_cookie('user_consent', consent_value, max_age=31536000, samesite='Lax', secure=True)
        return response
    return HttpResponse('Invalid consent value.', status=400)

class AboutView(TemplateView):
    template_name = "core/about.html"


class ShippingPolicyView(TemplateView):
    template_name = "core/shipping_policy.html"

class RefundPolicyView(TemplateView):
    template_name = "core/refund_policy.html"