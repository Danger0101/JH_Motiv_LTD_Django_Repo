from django import forms
from .models import CoachReview

class CoachReviewForm(forms.ModelForm):
    class Meta:
        model = CoachReview
        fields = ['knowledge_rating', 'delivery_rating', 'value_rating', 'results_rating', 'comment']
        widgets = {
            'comment': forms.Textarea(attrs={'rows': 4, 'class': 'w-full border border-gray-300 rounded p-2'}),
            'knowledge_rating': forms.NumberInput(attrs={'min': 1, 'max': 5, 'class': 'border border-gray-300 rounded p-1 w-16'}),
            'delivery_rating': forms.NumberInput(attrs={'min': 1, 'max': 5, 'class': 'border border-gray-300 rounded p-1 w-16'}),
            'value_rating': forms.NumberInput(attrs={'min': 1, 'max': 5, 'class': 'border border-gray-300 rounded p-1 w-16'}),
            'results_rating': forms.NumberInput(attrs={'min': 1, 'max': 5, 'class': 'border border-gray-300 rounded p-1 w-16'}),
        }