from django import forms
from .models import CoachAvailability, DAY_CHOICES

class CoachAvailabilityForm(forms.ModelForm):
    day_of_week = forms.MultipleChoiceField(
        choices=DAY_CHOICES,
        widget=forms.CheckboxSelectMultiple,
        label="Select Days"
    )

    class Meta:
        model = CoachAvailability
        fields = ['day_of_week', 'start_time', 'end_time']
        widgets = {
            'start_time': forms.TimeInput(attrs={'type': 'time'}),
            'end_time': forms.TimeInput(attrs={'type': 'time'}),
        }
