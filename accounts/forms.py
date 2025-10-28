from allauth.account.forms import SignupForm
from django import forms
from .models import MarketingPreference

class CustomSignupForm(SignupForm):
    marketing_opt_in = forms.BooleanField(required=False, initial=True, label="Receive marketing emails")

    def save(self, request):
        user = super(CustomSignupForm, self).save(request)
        if user:
            is_subscribed = self.cleaned_data.get('marketing_opt_in', True)
            MarketingPreference.objects.create(user=user, is_subscribed=is_subscribed)
        return user
