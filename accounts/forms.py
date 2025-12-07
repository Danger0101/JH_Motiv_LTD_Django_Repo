from allauth.account.forms import SignupForm
from django import forms
from .models import MarketingPreference

class CustomSignupForm(SignupForm):
    username = forms.CharField(max_length=150, label='Username', required=True)
    first_name = forms.CharField(max_length=30, label='First Name', required=True)
    last_name = forms.CharField(max_length=30, label='Last Name', required=True)
    marketing_opt_in = forms.BooleanField(required=False, initial=False, label="Receive marketing emails")
    policy_agreement = forms.BooleanField(required=True, label="")

    def save(self, request):
        user = super(CustomSignupForm, self).save(request)
        user.username = self.cleaned_data['username']
        user.first_name = self.cleaned_data['first_name']
        user.last_name = self.cleaned_data['last_name']
        user.save()

        is_subscribed = self.cleaned_data.get('marketing_opt_in', False)
        MarketingPreference.objects.get_or_create(user=user, defaults={'is_subscribed': is_subscribed})
        
        return user