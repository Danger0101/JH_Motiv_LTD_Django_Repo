from django import forms
from .models import Offering, Workshop


class OfferingCreationForm(forms.ModelForm):
    class Meta:
        model = Offering
        fields = '__all__'
        exclude = ('created_by', 'updated_by', 'slug', 'active_status')


class WorkshopForm(forms.ModelForm):
    class Meta:
        model = Workshop
        fields = [
            'coach', 'name', 'description', 'price',
            'date', 'start_time', 'end_time',
            'total_attendees', 'is_free', 'active_status', 'meeting_link'
        ]
        widgets = {
            'date': forms.DateInput(attrs={'type': 'date'}),
            'start_time': forms.TimeInput(attrs={'type': 'time'}),
            'end_time': forms.TimeInput(attrs={'type': 'time'}),
        }


class WorkshopBookingForm(forms.Form):
    full_name = forms.CharField(label="Full Name", max_length=100)
    email = forms.EmailField(label="Email Address")


class WorkshopRecurrenceForm(forms.Form):
    frequency = forms.ChoiceField(
        choices=[
            ('7', 'Weekly'),
            ('14', 'Bi-Weekly'),
            ('30', 'Monthly'),
            ('1', 'Daily'),
        ],
        label="How often should this workshop repeat?"
    )
    occurrences = forms.IntegerField(
        label="How many times should it repeat?",
        min_value=1,
        max_value=52, # Max of 1 year for weekly
        initial=4
    )
