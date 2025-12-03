from django import forms
from .models import TasterSessionRequest

class TasterRequestForm(forms.ModelForm):
    """
    Simplified form only requiring the goal summary from a logged-in user.
    """
    class Meta:
        model = TasterSessionRequest
        # Only require goal_summary field in the form itself
        fields = ['goal_summary'] 
        
    def __init__(self, *args, **kwargs):
        # Remove the custom 'request' kwarg used in the view for auto-population
        kwargs.pop('request', None) 
        super().__init__(*args, **kwargs)
        
        # NOTE: Bootstrap classes are now applied directly in the template partial
        self.fields['goal_summary'].label = "Your Coaching Goals"