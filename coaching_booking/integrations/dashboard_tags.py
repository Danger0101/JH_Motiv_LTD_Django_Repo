from django import template
from coaching_booking.models import CoachReview

register = template.Library()

@register.inclusion_tag('admin/dashboard_widgets/pending_reviews.html')
def render_pending_reviews():
    reviews = CoachReview.objects.filter(status='PENDING_STAFF').select_related('coach__user', 'client').order_by('-created_at')[:5]
    return {'reviews': reviews}