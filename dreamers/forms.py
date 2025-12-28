from django import forms
from django.utils.safestring import mark_safe
from django.core.validators import URLValidator
from django.core.exceptions import ValidationError
from .models import DreamerProfile

class DreamerApplicationForm(forms.ModelForm):
    agree_terms = forms.BooleanField(
        required=True,
        label=mark_safe('I agree to the <a href="/terms-of-service/?tab=dreamer" target="_blank" class="text-indigo-600 hover:text-indigo-500 underline">Dreamer Terms of Service</a>'),
        widget=forms.CheckboxInput(attrs={'class': 'h-4 w-4 text-indigo-600 focus:ring-indigo-500 border-gray-300 rounded'}),
    )
    
    # Added Social Links field as requested
    social_links = forms.CharField(
        required=False,
        label="Website / Social Media",
        widget=forms.Textarea(attrs={'class': 'w-full rounded-lg border-gray-300', 'rows': 4, 'placeholder': 'https://instagram.com/yourhandle\nhttps://www.yourbrand.com\nhttps://tiktok.com/@yourhandle'}),
        help_text="Please paste full URLs, one per line."
    )

    class Meta:
        model = DreamerProfile
        # Note: 'social_links' is handled as a non-model field here unless added to the model
        fields = ['name', 'story_excerpt', 'social_links']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'w-full rounded-lg border-gray-300', 'placeholder': 'Your Stage Name / Brand'}),
            'story_excerpt': forms.Textarea(attrs={'class': 'w-full rounded-lg border-gray-300', 'rows': 4, 'placeholder': 'Tell us about your dream...'}),
        }
        labels = {
            'name': 'Public Display Name',
            'story_excerpt': 'Your Story (Short Bio)',
        }
        help_texts = {
            'name': 'Full Name or Business Name (e.g., John Hummel | JH Motiv Ltd)',
            'story_excerpt': 'A short paragraph about your journey or dream.',
        }

    def clean_social_links(self):
        data = self.cleaned_data.get('social_links')
        if data:
            validator = URLValidator()
            lines = data.split('\n')
            invalid_urls = []
            
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                try:
                    validator(line)
                except ValidationError:
                    invalid_urls.append(line)
            
            if invalid_urls:
                raise forms.ValidationError(f"The following lines are not valid URLs: {', '.join(invalid_urls)}")
        return data