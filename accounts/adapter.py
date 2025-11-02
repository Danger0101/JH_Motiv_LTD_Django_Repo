# accounts/adapter.py

from allauth.account.adapter import DefaultAccountAdapter
from django.http import HttpResponse
from django.contrib.auth import get_user_model
from django.db.models import Q

class AccountAdapter(DefaultAccountAdapter):
    """
    Custom adapter required by settings.py to handle authentication logic,
    specifically to allow non-case-sensitive lookups for username/email.
    """
    def pre_authenticate(self, request, **kwargs):
        User = get_user_model()
        login_val = kwargs.get('username') or kwargs.get('email')
        
        if login_val:
            try:
                # Look up the user by non-case-sensitive username
                user = User.objects.get(username__iexact=login_val)
                kwargs['username'] = user.username 
            except User.DoesNotExist:
                # If not found by username, check if it's a case-insensitive email
                try:
                    user = User.objects.get(email__iexact=login_val)
                    kwargs['username'] = user.username 
                except User.DoesNotExist:
                    pass 

        return super().pre_authenticate(request, **kwargs)