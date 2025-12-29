from celery import shared_task
from django.core.mail import send_mail
from django.conf import settings
from django.urls import reverse
from .models import ClientOfferingEnrollment

@shared_task
def send_review_request_email(enrollment_id):
    try:
        enrollment = ClientOfferingEnrollment.objects.select_related('client', 'coach__user', 'offering').get(id=enrollment_id)
        client = enrollment.client
        coach_name = enrollment.coach.user.get_full_name()
        
        # Construct URL (assuming SITE_URL in settings, fallback to relative if not)
        site_url = getattr(settings, 'SITE_URL', 'https://jhmotiv.shop')
        review_url = f"{site_url}{reverse('coaching_booking:submit_coach_review', args=[enrollment.id])}"
        
        subject = f"How was your coaching with {coach_name}?"
        message = f"""Hi {client.first_name},

Congratulations on completing your coaching program '{enrollment.offering.name}'!

We'd love to hear about your experience. Your feedback helps {coach_name} and helps others find the right coach.

Please leave a review here:
{review_url}

Best regards,
The JH Motiv Team
"""
        send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, [client.email])
    except ClientOfferingEnrollment.DoesNotExist:
        pass