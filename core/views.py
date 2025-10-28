from django.shortcuts import render
from django.views.generic import TemplateView
from django.http import HttpResponse
from django.views.decorators.http import require_POST

# --- FIX: Import FAQ_DATA from the separate data.py file ---
# This assumes data.py is in the same Django app directory.
from .faq_data import FAQ_DATA 


def home(request):
    """Renders the home page."""
    return render(request, 'core/home.html')

def faqs_page(request): 
    """Renders the FAQ page with structured data for Alpine.js tabs/accordions."""
    # The FAQ_DATA dictionary is now imported and ready to use.
    return render(request, 'core/faqs.html', {'faq_data': FAQ_DATA}) 

@require_POST
def set_cookie_consent(request):
    """
    Sets a cookie to store the user's consent choice.
    """
    consent_value = request.POST.get('consent_value')
    if consent_value in ['accepted', 'rejected']:
        response = HttpResponse(status=204)
        # Set a permanent cookie (expires in 1 year)
        response.set_cookie('user_consent', consent_value, max_age=31536000, samesite='Lax', secure=True)
        return response
    # Return a bad request if the consent value is invalid
    return HttpResponse('Invalid consent value.', status=400)

class AboutView(TemplateView):
    template_name = "core/about.html"

class PrivacyPolicyView(TemplateView):
    template_name = "core/privacy_policy.html"

class TermsOfServiceView(TemplateView):
    template_name = "core/terms_of_service.html"

class ShippingPolicyView(TemplateView):
    template_name = "core/shipping_policy.html"

class RefundPolicyView(TemplateView):
    template_name = "core/refund_policy.html"
