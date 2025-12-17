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
        fields = ['name', 'description', 'price', 'date', 'start_time', 'end_time', 'total_attendees', 'is_free', 'active_status', 'meeting_link']
        widgets = {
            'date': forms.DateInput(attrs={'type': 'date'}),
            'start_time': forms.TimeInput(attrs={'type': 'time'}),
            'end_time': forms.TimeInput(attrs={'type': 'time'}),
        }

class WorkshopRecurrenceForm(forms.Form):
    FREQUENCY_CHOICES = [
        ('7', 'Weekly'),
        ('14', 'Bi-Weekly'),
        ('28', 'Every 4 Weeks'),
        ('30', 'Monthly (Same Date)'),
    ]
    
    frequency = forms.ChoiceField(choices=FREQUENCY_CHOICES, label="Repetition Frequency", widget=forms.Select(attrs={'class': 'bg-gray-50 border border-gray-300 text-gray-900 text-sm rounded-lg focus:ring-blue-500 focus:border-blue-500 block w-full p-2.5'}))
    occurrences = forms.IntegerField(min_value=1, max_value=52, initial=4, label="Number of Repeats", widget=forms.NumberInput(attrs={'class': 'bg-gray-50 border border-gray-300 text-gray-900 text-sm rounded-lg focus:ring-blue-500 focus:border-blue-500 block w-full p-2.5'}))