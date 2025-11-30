from django import forms
from .models import CoachAvailability, DateOverride, CoachVacation
from django.forms import TimeInput
from datetime import time, timedelta

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

# New code starts here
DAYS_OF_WEEK = [
    (0, 'Monday'),
    (1, 'Tuesday'),
    (2, 'Wednesday'),
    (3, 'Thursday'),
    (4, 'Friday'),
    (5, 'Saturday'),
    (6, 'Sunday'),
]

def get_time_choices():
    choices = [('', '-----')]
    for hour in range(24):
        for minute in range(0, 60, 15):
            t = time(hour, minute)
            choices.append((t.strftime('%H:%M:%S'), t.strftime('%I:%M %p')))
    return choices

class WeeklyScheduleForm(forms.Form):
    day_of_week = forms.ChoiceField(choices=DAYS_OF_WEEK, widget=forms.HiddenInput)
    start_time = forms.TimeField(widget=forms.Select(choices=get_time_choices()), required=False)
    end_time = forms.TimeField(widget=forms.Select(choices=get_time_choices()), required=False)

    def clean(self):
        cleaned_data = super().clean()
        start_time = cleaned_data.get('start_time')
        end_time = cleaned_data.get('end_time')

        if start_time and not end_time:
            self.add_error('end_time', 'Please provide an end time.')
        elif not start_time and end_time:
            self.add_error('start_time', 'Please provide a start time.')
        elif start_time and end_time and start_time >= end_time:
            self.add_error('end_time', 'End time must be after start time.')

        return cleaned_data

BaseWeeklyScheduleFormSet = forms.formset_factory(WeeklyScheduleForm, extra=7)