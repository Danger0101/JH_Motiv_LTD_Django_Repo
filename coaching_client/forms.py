from django import forms
from .models import TasterSessionRequest

tailwind_input_classes = "w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-green-500 focus:border-green-500"
tailwind_textarea_classes = tailwind_input_classes + " resize-y"

class TasterRequestForm(forms.ModelForm):
    """
    Form for clients (or potential clients) to request a taster session.
    """
    class Meta:
        model = TasterSessionRequest
        fields = ['full_name', 'email', 'phone_number', 'goal_summary']
        widgets = {
            'full_name': forms.TextInput(attrs={'placeholder': 'Full Name', 'class': tailwind_input_classes}),
            'email': forms.EmailInput(attrs={'placeholder': 'Email Address', 'class': tailwind_input_classes}),
            'phone_number': forms.TextInput(attrs={'placeholder': 'Phone Number (Optional)', 'class': tailwind_input_classes}),
            'goal_summary': forms.Textarea(attrs={'placeholder': 'Briefly describe your main coaching goal(s)', 'rows': 3, 'class': tailwind_textarea_classes}),
        }

    # Add optional custom clean methods if needed, but for simplicity, the above is enough.