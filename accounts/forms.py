from allauth.account.forms import SignupForm, ChangePasswordForm, SetPasswordForm, ResetPasswordForm, ResetPasswordKeyForm, AddEmailForm
from django import forms
from .models import MarketingPreference

TAILWIND_INPUT_CLASSES = 'block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm placeholder-gray-400 focus:outline-none focus:ring-blue-500 focus:border-blue-500 sm:text-sm'

class CustomSignupForm(SignupForm):
    username = forms.CharField(max_length=150, label='Username', required=True)
    first_name = forms.CharField(max_length=30, label='First Name', required=True)
    last_name = forms.CharField(max_length=30, label='Last Name', required=True)
    marketing_opt_in = forms.BooleanField(required=False, initial=False, label="Receive marketing emails")
    policy_agreement = forms.BooleanField(required=True, label="")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name, field in self.fields.items():
            # We don't want to style checkboxes this way
            if not isinstance(field.widget, (forms.CheckboxInput, forms.RadioSelect)):
                field.widget.attrs.update({'class': TAILWIND_INPUT_CLASSES})

    def save(self, request):
        user = super(CustomSignupForm, self).save(request)
        user.username = self.cleaned_data['username']
        user.first_name = self.cleaned_data['first_name']
        user.last_name = self.cleaned_data['last_name']
        user.save()

        is_subscribed = self.cleaned_data.get('marketing_opt_in', False)
        MarketingPreference.objects.get_or_create(user=user, defaults={'is_subscribed': is_subscribed})
        
        return user

class CustomChangePasswordForm(ChangePasswordForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name, field in self.fields.items():
            field.widget.attrs.update({'class': TAILWIND_INPUT_CLASSES})

class CustomSetPasswordForm(SetPasswordForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name, field in self.fields.items():
            field.widget.attrs.update({'class': TAILWIND_INPUT_CLASSES})

class CustomResetPasswordForm(ResetPasswordForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name, field in self.fields.items():
            field.widget.attrs.update({'class': TAILWIND_INPUT_CLASSES})

class CustomResetPasswordKeyForm(ResetPasswordKeyForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name, field in self.fields.items():
            field.widget.attrs.update({'class': TAILWIND_INPUT_CLASSES})

class CustomAddEmailForm(AddEmailForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name, field in self.fields.items():
            if field_name == 'email':
                field.widget.attrs.update({'class': TAILWIND_INPUT_CLASSES})