from django import forms
from .models import NewsletterSubscriber

class NewsletterSubscriptionForm(forms.ModelForm):
    # Honeypot field to catch bots
    nickname = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={'tabindex': '-1', 'autocomplete': 'off'})
    )

    class Meta:
        model = NewsletterSubscriber
        fields = ['email']
        widgets = {
            'email': forms.EmailInput(attrs={
                'placeholder': 'Enter your email...',
                'class': 'form-control'
            })
        }

    def clean(self):
        cleaned_data = super().clean()
        if cleaned_data.get('nickname'):
            raise forms.ValidationError("Spam detected.")
        return cleaned_data

    def clean_email(self):
        email = self.cleaned_data.get('email')
        # Check if email exists AND is active
        subscriber = NewsletterSubscriber.objects.filter(email=email).first()
        if subscriber and subscriber.is_active:
             raise forms.ValidationError("This email is already registered in the Guild.")
        return email

    def save(self, commit=True):
        email = self.cleaned_data['email']
        subscriber = NewsletterSubscriber.objects.filter(email=email).first()

        if subscriber:
            # Reactivate existing subscriber
            subscriber.is_active = True
            if commit:
                subscriber.save()
            return subscriber
        else:
            # Create new subscriber
            return super().save(commit=commit)

class StaffNewsletterForm(forms.Form):
    subject = forms.CharField(
        max_length=200, 
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )
    header_image = forms.ImageField(required=False, widget=forms.FileInput(attrs={'class': 'form-control'}))
    content = forms.CharField(
        widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 10}),
        help_text="HTML content is supported."
    )
    template = forms.ChoiceField(
        choices=[
            ('standard', 'Standard (Text Focused)'),
            ('hero', 'Visual Impact (Big Image)'),
            ('showcase', 'Product Showcase (Grid)'),
        ],
        initial='standard',
        widget=forms.Select(attrs={'class': 'form-control'})
    )