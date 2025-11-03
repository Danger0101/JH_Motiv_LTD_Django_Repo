# coaching/utils.py
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.conf import settings

def coach_is_valid(user):
    """Helper: Checks if the user is authenticated and is a coach."""
    return user.is_authenticated and user.is_coach

def send_multipart_email(subject, text_template_path, html_template_path, context, recipient_list):
    """
    Renders and sends a multipart (text and HTML) email.
    """
    text_content = render_to_string(text_template_path, context)
    html_content = render_to_string(html_template_path, context)

    send_mail(
        subject=subject,
        message=text_content,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=recipient_list,
        html_message=html_content,
        fail_silently=False, # Set to True in production if you don't want errors to block requests
    )