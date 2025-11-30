from django import forms
from .models import Workshop, Offering

class OfferingCreationForm(forms.ModelForm):
    class Meta:
        model = Offering
        fields = ['name', 'description', 'price', 'duration_type', 'total_length_units', 'session_length_minutes', 'total_number_of_sessions', 'is_whole_day', 'coaches']

class OfferingUpdateForm(forms.ModelForm):
    class Meta:
        model = Offering
        fields = ['name', 'description', 'price', 'duration_type', 'total_length_units', 'session_length_minutes', 'total_number_of_sessions', 'is_whole_day', 'coaches']

class WorkshopForm(forms.ModelForm):
    class Meta:
        model = Workshop
        fields = ['name', 'description', 'price', 'date', 'start_time', 'end_time', 'total_attendees', 'is_free', 'active_status']
        widgets = {
            'date': forms.DateInput(attrs={'type': 'date'}),
            'start_time': forms.TimeInput(attrs={'type': 'time'}),
            'end_time': forms.TimeInput(attrs={'type': 'time'}),
        }