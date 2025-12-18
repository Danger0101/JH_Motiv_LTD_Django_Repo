from django import forms
from .models import DreamerProfile

class DreamerApplicationForm(forms.ModelForm):
    class Meta:
        model = DreamerProfile
        fields = ['name', 'story_excerpt']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'w-full rounded-lg border-gray-300', 'placeholder': 'Your Stage Name / Brand'}),
            'story_excerpt': forms.Textarea(attrs={'class': 'w-full rounded-lg border-gray-300', 'rows': 4, 'placeholder': 'Tell us about your dream...'}),
        }
        labels = {
            'name': 'Public Display Name',
            'story_excerpt': 'Your Story (Short Bio)',
        }