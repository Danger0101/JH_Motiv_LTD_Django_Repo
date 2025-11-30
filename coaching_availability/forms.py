from django import forms
from .models import CoachAvailability, DateOverride, CoachVacation


class CoachAvailabilityForm(forms.ModelForm):
    class Meta:
        model = CoachAvailability
        fields = ['day_of_week', 'start_time', 'end_time']


class DateOverrideForm(forms.ModelForm):
    class Meta:
        model = DateOverride
        fields = ['date', 'is_available', 'start_time', 'end_time']


class CoachVacationForm(forms.ModelForm):
    class Meta:
        model = CoachVacation
        fields = ['start_date', 'end_date', 'existing_booking_handling']