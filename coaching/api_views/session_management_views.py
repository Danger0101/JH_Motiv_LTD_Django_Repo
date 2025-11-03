# coaching/api_views/session_management_views.py

from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponse
from django.urls import reverse
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from django.contrib.auth import get_user_model

from ..models import (
    CoachingSession,
    SessionCredit,
    RescheduleRequest,
    CoachSwapRequest,
    CancellationPolicy,
    SessionStatus,
    SwapStatus,
    RescheduleStatus,
)

User = get_user_model()

def _handle_session_cancellation(session, canceller):
    """
    Helper function to contain the core logic for cancelling a session,
    calculating refunds, and sending notifications.
    """
    user_type = 'USER' if canceller == session.client else 'COACH'
    time_difference = session.start_time - timezone.now()
    hours_before_session = time_difference.total_seconds() / 3600

    policies = CancellationPolicy.objects.filter(user_type=user_type).order_by('-hours_before_session')
    refund_percentage = 0
    for policy in policies:
        if hours_before_session >= policy.hours_before_session:
            refund_percentage = policy.refund_percentage
            break

    session.status = SessionStatus.CANCELLED
    session.save()

    if refund_percentage > 0 and hasattr(session, 'used_credit'):
        credit = session.used_credit
        if refund_percentage == 100:
            credit.session = None
            credit.save()
        # Note: Partial credit refunds are not yet implemented.

    # Send notification email to the other party
    recipient = session.coach if canceller == session.client else session.client
    context = {'recipient': recipient, 'canceller': canceller, 'session': session}
    from ..utils import send_multipart_email
    send_multipart_email(f"Session Cancelled: {session.offering.name}", 'coaching/emails/session_cancelled.txt', 'coaching/emails/session_cancelled.html', context, [recipient.email])
    return refund_percentage

@login_required
def cancel_session_view(request, session_id):
    session = get_object_or_404(CoachingSession, id=session_id)
    user = request.user

    if user != session.client and user != session.coach:
        return HttpResponse("Unauthorized", status=403)

    if request.method == 'POST':
        try:
            refund_percentage = _handle_session_cancellation(session, request.user)
            return render(request, 'coaching/partials/session_management/cancellation_confirmation.html', {'session': session, 'refund_percentage': refund_percentage})
        except Exception as e:
            print(f"Error sending cancellation email for session {session.id}: {e}")
            return HttpResponse("An error occurred during cancellation.", status=500)

    return render(request, 'coaching/session_management/cancel_session.html', {'session': session, 'refund_percentage': refund_percentage})

@login_required
def initiate_swap_request_view(request, session_id, receiving_coach_id):
    session = get_object_or_404(CoachingSession, id=session_id, coach=request.user)
    receiving_coach = get_object_or_404(User, id=receiving_coach_id, is_coach=True)

    if request.method == 'POST':
        swap_request = CoachSwapRequest.objects.create(
            session=session,
            initiating_coach=request.user,
            receiving_coach=receiving_coach,
        )
        # Notify the receiving coach
        try:
            from ..utils import send_multipart_email
            response_url = request.build_absolute_uri(reverse('coaching:coach_swap_response', kwargs={'token': swap_request.token}))
            context = {
                'recipient': receiving_coach,
                'swap_request': swap_request,
                'response_url': response_url,
            }
            send_multipart_email(
                subject="Coach Swap Request",
                text_template_path='coaching/emails/swap_request_initiated.txt',
                html_template_path='coaching/emails/swap_request_initiated.html',
                context=context,
                recipient_list=[receiving_coach.email]
            )
        except Exception as e:
            print(f"Error sending swap initiation email for request {swap_request.id}: {e}")

        return HttpResponse("Swap request initiated.")

@login_required
def coach_swap_response_view(request, token):
    swap_request = get_object_or_404(CoachSwapRequest, token=token, receiving_coach=request.user)

    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'accept':
            swap_request.status = SwapStatus.PENDING_USER
            swap_request.save()
            # Notify the user to get their approval
            try:
                from ..utils import send_multipart_email
                response_url = request.build_absolute_uri(reverse('coaching:user_swap_response', kwargs={'token': swap_request.token}))
                context = {
                    'recipient': swap_request.session.client,
                    'swap_request': swap_request,
                    'response_url': response_url,
                }
                send_multipart_email("Action Required: Approve Coach Swap", 'coaching/emails/swap_request_user_approval.txt', 'coaching/emails/swap_request_user_approval.html', context, [swap_request.session.client.email])
            except Exception as e:
                print(f"Error sending swap user approval email for request {swap_request.id}: {e}")

            return HttpResponse("Swap request accepted. Waiting for user confirmation.")
        elif action == 'decline':
            swap_request.status = SwapStatus.DECLINED
            swap_request.save()
            # Notify the initiating coach of the decline
            try:
                from ..utils import send_multipart_email
                recipient = swap_request.initiating_coach
                context = {
                    'recipient': recipient,
                    'swap_request': swap_request,
                }
                send_multipart_email(
                    subject="Coach Swap Request Declined",
                    text_template_path='coaching/emails/swap_request_finalized.txt',
                    html_template_path='coaching/emails/swap_request_finalized.html',
                    context=context, recipient_list=[recipient.email])
            except Exception as e:
                print(f"Error sending swap decline email for request {swap_request.id}: {e}")
            return HttpResponse("Swap request declined.")

    return render(request, 'coaching/session_management/coach_swap_response.html', {'swap_request': swap_request})

@login_required
def user_swap_response_view(request, token):
    swap_request = get_object_or_404(CoachSwapRequest, token=token, session__client=request.user)

    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'accept':
            with transaction.atomic():
                swap_request.status = SwapStatus.ACCEPTED
                session = swap_request.session
                session.coach = swap_request.receiving_coach
                session.save()
                swap_request.save()
            # Notify both coaches of the final acceptance
            try:
                from ..utils import send_multipart_email
                recipients = [swap_request.initiating_coach, swap_request.receiving_coach]
                for coach in recipients:
                    context = {'recipient': coach, 'swap_request': swap_request}
                    send_multipart_email("Coach Swap Accepted", 'coaching/emails/swap_request_finalized.txt', 'coaching/emails/swap_request_finalized.html', context, [coach.email])
            except Exception as e:
                print(f"Error sending swap acceptance email for request {swap_request.id}: {e}")
            return HttpResponse("Swap accepted.")
        elif action == 'decline':
            swap_request.status = SwapStatus.DECLINED
            swap_request.save()
            # Notify both coaches of the user's decline
            try:
                from ..utils import send_multipart_email
                recipients = [swap_request.initiating_coach, swap_request.receiving_coach]
                for coach in recipients:
                    context = {'recipient': coach, 'swap_request': swap_request}
                    send_multipart_email("Coach Swap Declined by Client", 'coaching/emails/swap_request_finalized.txt', 'coaching/emails/swap_request_finalized.html', context, [coach.email])
            except Exception as e:
                print(f"Error sending swap user decline email for request {swap_request.id}: {e}")
            return HttpResponse("Swap declined.")

    return render(request, 'coaching/session_management/user_swap_response.html', {'swap_request': swap_request})

@login_required
def reschedule_request_view(request, token):
    reschedule_request = get_object_or_404(RescheduleRequest, token=token)
    session = reschedule_request.session

    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'reschedule':
            reschedule_request.status = RescheduleStatus.ACCEPTED
            reschedule_request.save()
            if session.offering:
                return redirect('coaching:offering_detail_coach', offering_slug=session.offering.slug, coach_id=session.coach.id)
            else:
                return HttpResponse("Cannot reschedule: The original offering for this session could not be found.", status=404)
        elif action == 'cancel':
            reschedule_request.status = RescheduleStatus.DECLINED
            reschedule_request.save()
            try:
                _handle_session_cancellation(session, request.user)
                return render(request, 'coaching/partials/session_management/reschedule_declined.html')
            except Exception as e:
                print(f"Error handling cancellation from reschedule view for session {session.id}: {e}")
                return HttpResponse("An error occurred during cancellation.", status=500)

    return render(request, 'coaching/session_management/reschedule_request.html', {'reschedule_request': reschedule_request})