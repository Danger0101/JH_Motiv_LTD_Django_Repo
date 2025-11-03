# coaching/api_views/taster_views.py

from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponse
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.utils import timezone
from django.contrib.auth import get_user_model

from ..models import CreditApplication, SessionCredit, CreditApplicationStatus 
from ..utils import coach_is_valid

User = get_user_model()

@login_required
def apply_taster_view(request):
    """
    Handles the user application for the one-time Momentum Catalyst Session credit.
    Records the application for coach approval.
    """
    user = request.user
    
    # 1. Check if the user already has a pending or approved application
    existing_application = CreditApplication.objects.filter(
        user=user, 
        is_taster=True
    ).exclude(status=CreditApplicationStatus.DENIED).first() # Exclude DENIED to allow re-applying after denial
    
    if request.method == 'POST':
        # Assuming a simple form post to initiate the application
        
        # 2. Create the application record
        CreditApplication.objects.create(
            user=user,
            is_taster=True,
            status=CreditApplicationStatus.PENDING,
            # Additional form data (e.g., goals) could be saved here
        )
        
        # Refresh the page to show the new status
        return redirect('coaching:apply_taster')

    # Display the application form or status (GET request)
    return render(request, 'coaching/taster/apply_taster.html', {'application': existing_application})


@login_required
def coach_manage_taster_view(request):
    """
    View for coaches to see pending taster credit applications and approve/deny them.
    """
    if not coach_is_valid(request.user):
        return HttpResponse("Access Denied: You do not have coach privileges.", status=403)
        
    pending_applications = CreditApplication.objects.filter(
        is_taster=True, 
        status=CreditApplicationStatus.PENDING
    ).order_by('created_at')
    
    context = {
        'pending_applications': pending_applications,
    }
    return render(request, 'coaching/coach/manage_tasters.html', context)


@login_required
@transaction.atomic
def approve_taster_credit_view(request, application_id):
    """
    Handles the coach's action to approve a taster credit application.
    """
    if not coach_is_valid(request.user) or request.method != 'POST':
        return HttpResponse("Unauthorized or Invalid Request.", status=403)

    application = get_object_or_404(CreditApplication, id=application_id, is_taster=True)

    if application.status != CreditApplicationStatus.PENDING:
        return HttpResponse("Application is not pending review.", status=400)

    # 1. Update the application status
    application.status = CreditApplicationStatus.APPROVED
    application.approved_by = request.user
    application.approved_at = timezone.now()
    application.save()

    # The post_save signal on CreditApplication now handles credit creation.
    
    # Send notification email
    try:
        from ..utils import send_multipart_email
        booking_url = request.build_absolute_uri(reverse('coaching:taster_booking_start'))
        context = {
            'user': application.user,
            'booking_url': booking_url,
        }
        send_multipart_email(
            subject="Your Momentum Catalyst Session Application is Approved!",
            text_template_path='coaching/emails/taster_approved.txt',
            html_template_path='coaching/emails/taster_approved.html',
            context=context,
            recipient_list=[application.user.email]
        )
    except Exception as e:
        # Log the error, but don't block the response
        print(f"Error sending approval email for application {application.id}: {e}")

    return redirect('coaching:coach_manage_tasters') # Redirect back to the management view


@login_required
def deny_taster_credit_view(request, application_id):
    """
    Handles the coach's action to deny a taster credit application.
    """
    if not coach_is_valid(request.user) or request.method != 'POST':
        return HttpResponse("Unauthorized or Invalid Request.", status=403)

    application = get_object_or_404(CreditApplication, id=application_id, is_taster=True)

    if application.status != CreditApplicationStatus.PENDING:
        return HttpResponse("Application is not pending review.", status=400)
    
    application.status = CreditApplicationStatus.DENIED
    application.denied_by = request.user
    application.denied_at = timezone.now()
    application.save()
    
    # Send notification email
    try:
        from ..utils import send_multipart_email
        context = {'user': application.user}
        send_multipart_email(
            subject="Update on Your Momentum Catalyst Session Application",
            text_template_path='coaching/emails/taster_denied.txt',
            html_template_path='coaching/emails/taster_denied.html',
            context=context,
            recipient_list=[application.user.email]
        )
    except Exception as e:
        # Log the error, but don't block the response
        print(f"Error sending denial email for application {application.id}: {e}")

    return redirect('coaching:coach_manage_tasters')