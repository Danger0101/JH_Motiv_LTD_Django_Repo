from django import forms
from .models import CoachAvailability, DateOverride, CoachVacation

class WeeklyScheduleForm(forms.ModelForm):
    class Meta:
        model = CoachAvailability
        fields = ['day_of_week', 'start_time', 'end_time']
        widgets = {
            'start_time': forms.TimeInput(format='%H:%M', attrs={'type': 'time'}),
            'end_time': forms.TimeInput(format='%H:%M', attrs={'type': 'time'}),
            'day_of_week': forms.HiddenInput(),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['day_of_week'].label = ""

class DateOverrideForm(forms.ModelForm):
    class Meta:
        model = DateOverride
        fields = ['date', 'is_available', 'start_time', 'end_time']
        widgets = {
            'date': forms.DateInput(attrs={'type': 'date'}),
            'start_time': forms.TimeInput(format='%H:%M', attrs={'type': 'time'}),
            'end_time': forms.TimeInput(format='%H:%M', attrs={'type': 'time'}),
        }

class CoachVacationForm(forms.ModelForm):
    class Meta:
        model = CoachVacation
        fields = ['start_date', 'end_date', 'existing_booking_handling']
        widgets = {
            'start_date': forms.DateInput(attrs={'type': 'date'}),
            'end_date': forms.DateInput(attrs={'type': 'date'}),
        }