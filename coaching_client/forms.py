from django import forms
from .models import TasterSessionRequest 

class TasterRequestForm(forms.ModelForm):
    """
    Form for clients (or potential clients) to request a taster session.
    """
    class Meta:
        model = TasterSessionRequest
        fields = ['full_name', 'email', 'phone_number', 'goal_summary']
        widgets = {
            'full_name': forms.TextInput(attrs={'placeholder': 'Full Name'}),
            'email': forms.EmailInput(attrs={'placeholder': 'Email Address'}),
            'phone_number': forms.TextInput(attrs={'placeholder': 'Phone Number (Optional)'}),
            'goal_summary': forms.Textarea(attrs={'placeholder': 'Briefly describe your main coaching goal(s)', 'rows': 3}),
        }