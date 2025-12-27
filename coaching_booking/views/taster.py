from django.shortcuts import get_object_or_404, redirect, render
from django.http import HttpResponse
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.db.models import Q
from django.utils import timezone
from datetime import datetime

from accounts.models import CoachProfile
from ..models import OneSessionFreeOffer, SessionBooking
from coaching_core.models import Offering

@login_required
@require_POST
def apply_for_free_session(request):
    coach_id = request.POST.get('coach_id')
    coach = get_object_or_404(CoachProfile, id=coach_id)
    
    existing = OneSessionFreeOffer.objects.filter(client=request.user, coach=coach, status__in=['PENDING', 'APPROVED']).filter(Q(redemption_deadline__isnull=True) | Q(redemption_deadline__gt=timezone.now())).first()
    if existing:
        msg = 'Request pending.' if existing.status == 'PENDING' else 'Offer already approved.'
        return render(request, 'coaching_booking/partials/free_session_status.html', {'status': 'pending', 'message': msg})

    OneSessionFreeOffer.objects.create(client=request.user, coach=coach, status='PENDING')
    return render(request, 'coaching_booking/partials/free_session_status.html', {'status': 'success', 'message': 'Request submitted!'})

@login_required
@require_POST
def request_taster(request, offering_id):
    offering = get_object_or_404(Offering, id=offering_id)
    if not offering.coach: return HttpResponse('Error: No coach assigned.')
    
    if OneSessionFreeOffer.objects.filter(client=request.user, coach=offering.coach, status__in=['PENDING', 'APPROVED']).exists():
        return HttpResponse('<button disabled>Request Pending</button>')

    OneSessionFreeOffer.objects.create(client=request.user, coach=offering.coach, offering=offering, status='PENDING')
    return HttpResponse('<button disabled>Request Sent</button>')

@login_required
def book_taster_session(request, offer_id):
    offer = get_object_or_404(OneSessionFreeOffer, id=offer_id, client=request.user, status='APPROVED')
    if request.method == "POST":
        try:
            clean_time = request.POST.get('slot', '').replace('Z', '+00:00').replace(' ', '+')
            start_dt = datetime.fromisoformat(clean_time)
            if timezone.is_naive(start_dt): start_dt = timezone.make_aware(start_dt)
            
            booking = SessionBooking.objects.create(client=request.user, coach=offer.coach, offering=offer.offering, start_datetime=start_dt, status='BOOKED', amount_paid=0)
            offer.status = 'USED'; offer.session = booking; offer.save()
            messages.success(request, "Taster session booked!")
        except ValueError:
            messages.error(request, "Invalid time slot.")
    return redirect('accounts:account_profile')

@login_required
@require_POST
def approve_taster(request, offer_id):
    try: coach_profile = request.user.coach_profile
    except: return HttpResponse(status=403)
    
    offer = get_object_or_404(OneSessionFreeOffer, id=offer_id)
    if offer.coach != coach_profile: return HttpResponse(status=403)
    
    offer.status = 'APPROVED'; offer.save()
    messages.success(request, f"Approved offer for {offer.client.get_full_name()}.")
    return HttpResponse("")

@login_required
@require_POST
def decline_taster(request, offer_id):
    try: coach_profile = request.user.coach_profile
    except: return HttpResponse(status=403)
    
    offer = get_object_or_404(OneSessionFreeOffer, id=offer_id)
    if offer.coach != coach_profile: return HttpResponse(status=403)
    
    offer.status = 'DECLINED'; offer.save()
    return HttpResponse("")