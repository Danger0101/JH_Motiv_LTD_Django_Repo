from django import forms
from .models import TasterSessionRequest 

class TasterRequestForm(forms.ModelForm):
    """
    Simplified form requiring only the goal summary from a logged-in user.
    """
    class Meta:
        model = TasterSessionRequest
        # Only require goal_summary (User, Full Name, Email are auto-populated in the view)
        fields = ['goal_summary']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Add basic Bootstrap class for styling and placeholder text
        self.fields['goal_summary'].widget.attrs.update({
            'class': 'form-control',
            'placeholder': 'Briefly describe your main coaching goal(s) (Required)',
            'rows': 4
        })
        self.fields['goal_summary'].label = "Your Coaching Goals"