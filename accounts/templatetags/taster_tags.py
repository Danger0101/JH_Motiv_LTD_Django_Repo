# accounts/templatetags/taster_tags.py

from django import template
from coaching_client.models import TasterSessionRequest # Ensure this import is correct

register = template.Library()

@register.simple_tag(takes_context=True)
def pending_taster_count(context):
    """Returns the count of PENDING taster session requests for the badge."""
    user = context['request'].user
    if user.is_authenticated and (user.is_staff or user.is_coach):
        return TasterSessionRequest.objects.filter(status='PENDING').count()
    return 0
