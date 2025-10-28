# accounts/forms.py

from django import forms
from allauth.account.forms import SignupForm, LoginForm
from django.contrib.auth import get_user_model

# Get the User model set in settings.py
User = get_user_model()

# --- Custom Form Base Classes (For Styling) ---

class TailwindFormMixin:
    """Mixin to apply standard Tailwind CSS classes to all widgets."""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        common_classes = 'mt-1 block w-full px-3 py-2 bg-white border border-gray-300 rounded-md shadow-sm placeholder-gray-400 focus:outline-none focus:ring-blue-500 focus:border-blue-500 sm:text-sm'
        
        for field_name, field in self.fields.items():
            # Exclude BooleanFields (checkboxes) from general text styling
            if not isinstance(field.widget, forms.CheckboxInput):
                field.widget.attrs.update({'class': common_classes})
            
            # Remove Django's default help text to keep the UI clean
            if field.help_text:
                field.help_text = ''


# --- Custom Login Form ---

class CustomLoginForm(TailwindFormMixin, LoginForm):
    """Custom allauth login form applying Tailwind classes."""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Specific placeholders/overrides
        self.fields['login'].widget.attrs.update({'placeholder': 'Username or Email'})


# --- Custom Signup Form ---

class CustomSignupForm(TailwindFormMixin, SignupForm):
    """
    Custom form extending allauth's SignupForm to include first and last names,
    and mandatory policy agreement/optional marketing consent.
    """
    first_name = forms.CharField(max_length=150, required=True, 
                                 widget=forms.TextInput(attrs={'placeholder': 'First Name'}))
    last_name = forms.CharField(max_length=150, required=True, 
                                widget=forms.TextInput(attrs={'placeholder': 'Last Name'}))

    # --- Compliance Fields ---
    policy_agreement = forms.BooleanField(
        label="I have read and agree to the Terms of Service and Privacy Policy.", 
        required=True,
        error_messages={'required': 'You must agree to the Terms of Service and Privacy Policy to create an account.'}
    )

    marketing_opt_in = forms.BooleanField(
        label="I would like to receive motivational content and updates (optional).",
        required=False
    )

    def save(self, request):
        """
        Saves the first and last name onto the User object after it is created.
        """
        # Call the parent save method to create the user
        user = super(CustomSignupForm, self).save(request)
        
        # Set the first and last name fields
        user.first_name = self.cleaned_data['first_name']
        user.last_name = self.cleaned_data['last_name']
        
        # NOTE: You would save the marketing_opt_in status to a UserProfile or
        # a separate Subscription model here, but for simplicity, we just save the base user fields.
        
        user.save()
        
        return user