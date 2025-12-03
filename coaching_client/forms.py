from django import forms
from .models import TasterSessionRequest

class GuestTasterRequestForm(forms.ModelForm):
    """
    Form for guest users to request a taster session.
    """
    class Meta:
        model = TasterSessionRequest
        fields = ['full_name', 'email', 'phone_number', 'goal_summary']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['goal_summary'].label = "Your Coaching Goals"


class TasterRequestForm(forms.ModelForm):
    """
    Simplified form only requiring the goal summary from a logged-in user.
    """
    class Meta:
        model = TasterSessionRequest
        fields = ['goal_summary'] 
        
    def __init__(self, *args, **kwargs):
        kwargs.pop('request', None) 
        super().__init__(*args, **kwargs)
        self.fields['goal_summary'].label = "Your Coaching Goals"
