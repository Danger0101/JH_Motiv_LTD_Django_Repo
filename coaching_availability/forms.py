from django import forms
from .models import CoachAvailability, DateOverride, CoachVacation
from django.forms import TimeInput
from datetime import time, timedelta

class WeeklyScheduleForm(forms.ModelForm): # Changed from forms.Form to forms.ModelForm
    class Meta:
        model = CoachAvailability
        fields = ['day_of_week', 'start_time', 'end_time']
        widgets = {
            'start_time': forms.TimeInput(format='%H:%M', attrs={'type': 'time'}),
            'end_time': forms.TimeInput(format='%H:%M', attrs={'type': 'time'}),
            # We hide day_of_week because we display it as text in the template
            'day_of_week': forms.HiddenInput(), 
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Ensure the label doesn't show up for the hidden field
        self.fields['day_of_week'].label = ""