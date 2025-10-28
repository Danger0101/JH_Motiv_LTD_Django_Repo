from django.shortcuts import render
from django.views.generic import TemplateView
from django.http import HttpResponse
from django.views.decorators.http import require_POST

def home(request):
    """Renders the home page."""
    return render(request, 'core/home.html')

@require_POST
def set_cookie_consent(request):
    """
    Sets a cookie to store the user's consent choice.
    This view is called via HTMX from the cookie consent banner.
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

class FAQsView(TemplateView):
    template_name = "core/faqs.html"

class PrivacyPolicyView(TemplateView):
    template_name = "core/privacy_policy.html"

class TermsOfServiceView(TemplateView):
    template_name = "core/terms_of_service.html"

class ShippingPolicyView(TemplateView):
    template_name = "core/shipping_policy.html"

class RefundPolicyView(TemplateView):
    template_name = "core/refund_policy.html"
