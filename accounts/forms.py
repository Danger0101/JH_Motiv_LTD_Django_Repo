from allauth.account.forms import SignupForm, ChangePasswordForm, SetPasswordForm, ResetPasswordForm, ResetPasswordKeyForm, AddEmailForm
from django import forms
from django.contrib.auth import get_user_model
from django.utils.safestring import mark_safe
from django.urls import reverse
from .models import MarketingPreference
from turnstile.fields import TurnstileField

TAILWIND_INPUT_CLASSES = 'block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm placeholder-gray-400 focus:outline-none focus:ring-blue-500 focus:border-blue-500 sm:text-sm'

class CustomSignupForm(SignupForm):
    username = forms.CharField(max_length=150, label='Username', required=True)
    first_name = forms.CharField(max_length=30, label='First Name', required=True)
    last_name = forms.CharField(max_length=30, label='Last Name', required=True)
    marketing_opt_in = forms.BooleanField(required=False, initial=False, label="Receive marketing emails")
    policy_agreement = forms.BooleanField(required=True, label="")
    captcha = TurnstileField()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name, field in self.fields.items():
            # We don't want to style checkboxes this way
            if not isinstance(field.widget, (forms.CheckboxInput, forms.RadioSelect)):
                field.widget.attrs.update({'class': TAILWIND_INPUT_CLASSES})

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if email and get_user_model().objects.filter(email__iexact=email).exists():
            reset_url = reverse('accounts:password_reset')
            msg = mark_safe(f'An account with this email already exists. <a href="{reset_url}" class="text-indigo-600 hover:text-indigo-500 underline">Forgot your password?</a>')
            raise forms.ValidationError(msg)
        return super().clean_email()

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

class GuestConversionForm(forms.Form):
    username = forms.CharField(max_length=150, required=True, label="Choose a Username")
    password = forms.CharField(widget=forms.PasswordInput, required=True, label="Set Password")
    password_confirm = forms.CharField(widget=forms.PasswordInput, required=True, label="Confirm Password")

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        for field_name, field in self.fields.items():
            field.widget.attrs.update({'class': TAILWIND_INPUT_CLASSES})

    def clean_username(self):
        username = self.cleaned_data['username']
        User = get_user_model()
        if User.objects.filter(username__iexact=username).exclude(pk=self.user.pk).exists():
            raise forms.ValidationError("This username is already taken.")
        return username

    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get("password")
        password_confirm = cleaned_data.get("password_confirm")
        if password and password_confirm and password != password_confirm:
            self.add_error('password_confirm', "Passwords do not match.")
        return cleaned_data

    def save(self):
        self.user.username = self.cleaned_data['username']
        self.user.set_password(self.cleaned_data['password'])
        self.user.is_guest = False
        self.user.save()
        return self.user