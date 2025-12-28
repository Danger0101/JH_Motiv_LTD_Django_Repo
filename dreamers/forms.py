from django import forms
from django.utils.safestring import mark_safe
from .models import DreamerProfile

class DreamerApplicationForm(forms.ModelForm):
    agree_terms = forms.BooleanField(
        required=True,
        label=mark_safe('I agree to the <a href="/legal/dreamer-terms/" target="_blank" class="text-indigo-600 hover:text-indigo-500 underline">Dreamer Terms of Service</a>'),
        widget=forms.CheckboxInput(attrs={'class': 'h-4 w-4 text-indigo-600 focus:ring-indigo-500 border-gray-300 rounded'}),
    )

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