from django import forms

class PayoutSettingsForm(forms.Form):
    bank_name = forms.CharField(max_length=100, required=True, widget=forms.TextInput(attrs={'class': 'block w-full rounded-lg border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 sm:text-sm'}))
    account_holder_name = forms.CharField(max_length=100, required=True, label="Account Holder Name", widget=forms.TextInput(attrs={'class': 'block w-full rounded-lg border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 sm:text-sm'}))
    sort_code = forms.CharField(max_length=20, required=True, help_text="e.g. 12-34-56", widget=forms.TextInput(attrs={'class': 'block w-full rounded-lg border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 sm:text-sm'}))
    account_number = forms.CharField(max_length=20, required=True, widget=forms.TextInput(attrs={'class': 'block w-full rounded-lg border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 sm:text-sm'}))
    
    # Optional: IBAN for international
    iban = forms.CharField(max_length=34, required=False, label="IBAN (Optional)", widget=forms.TextInput(attrs={'class': 'block w-full rounded-lg border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 sm:text-sm'}))