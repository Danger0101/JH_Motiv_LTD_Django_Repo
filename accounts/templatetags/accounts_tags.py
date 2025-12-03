from django import template
from coaching_client.models import TasterSessionRequest

register = template.Library()

@register.filter
def pending_taster_count(user):
    if user.is_authenticated and (user.is_staff or hasattr(user, 'is_coach') and user.is_coach):
        return TasterSessionRequest.objects.filter(status='PENDING').count()
    return 0
