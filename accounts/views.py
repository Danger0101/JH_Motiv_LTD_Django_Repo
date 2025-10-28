from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from .models import MarketingPreference

@login_required
def update_marketing_preference(request):
    if request.method == 'POST':
        is_subscribed = request.POST.get('is_subscribed') == 'on'
        preference, created = MarketingPreference.objects.get_or_create(user=request.user)
        preference.is_subscribed = is_subscribed
        preference.save()
        status_message = 'Subscribed' if is_subscribed else 'Unsubscribed'
        return HttpResponse(f"Current status: {status_message}")
    return HttpResponse("Invalid request", status=400)