from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.http import HttpResponse, HttpResponseForbidden
from django.contrib.auth import login
from django.utils.crypto import get_random_string
from django.contrib.auth.forms import PasswordResetForm
from django.core.paginator import Paginator
from django.db.models import Q
from django.conf import settings

from accounts.models import User, MarketingPreference
from coaching_core.models import Offering
from ..models import ClientOfferingEnrollment
from core.email_utils import send_transactional_email

def guest_access_view(request, token):
    user = get_object_or_404(User, billing_notes=token)
    user.is_active = True
    login(request, user, backend='django.contrib.auth.backends.ModelBackend')
    user.billing_notes = ""; user.save()
    messages.success(request, "Welcome! Please set a password.")
    return redirect('accounts:account_profile')

@login_required
def staff_create_guest_account(request):
    if not request.user.is_staff: return HttpResponseForbidden()
    offerings = Offering.objects.filter(active_status=True)
    
    if request.method == 'POST':
        email = request.POST.get('email')
        full_name = request.POST.get('full_name')
        if not email or not full_name:
            messages.error(request, "Email/Name required.")
            return render(request, 'account/partials/staff/staff_create_guest.html', {'offerings': offerings})

        user = User.objects.filter(Q(email=email)|Q(username=email)).first()
        random_pw = None
        if not user:
            random_pw = get_random_string(12)
            user = User.objects.create_user(username=email, email=email, password=random_pw, first_name=full_name.split()[0], is_active=False)
            MarketingPreference.objects.create(user=user, is_subscribed=False)
        
        token = get_random_string(32)
        user.billing_notes = token; user.save()
        
        offering_id = request.POST.get('offering_id')
        if offering_id:
            offering = Offering.objects.get(id=offering_id)
            ClientOfferingEnrollment.objects.create(client=user, offering=offering, coach=offering.coaches.first(), remaining_sessions=offering.total_number_of_sessions)

        access_url = request.build_absolute_uri(reverse('coaching_booking:guest_access', args=[token]))
        context = {'site_name': 'JH Motiv', 'access_url': access_url, 'username': email, 'password': random_pw, 'is_new_account': bool(random_pw)}
        send_transactional_email(recipient_email=email, subject="Welcome", template_name='emails/guest_welcome.html', context=context)
        
        messages.success(request, f"Guest account created for {email}.")
        return redirect('coaching_booking:staff_create_guest')
    return render(request, 'account/partials/staff/staff_create_guest.html', {'offerings': offerings})

@login_required
@require_POST
def staff_send_password_reset(request):
    if not request.user.is_staff: return HttpResponseForbidden()
    email = request.POST.get('email')
    user = User.objects.filter(email=email).first()
    if user:
        form = PasswordResetForm({'email': email})
        if form.is_valid():
            form.save(request=request, use_https=request.is_secure(), from_email=settings.DEFAULT_FROM_EMAIL)
            messages.success(request, f"Reset sent to {email}.")
    else: messages.error(request, "User not found.")
    return redirect('coaching_booking:staff_create_guest')

@login_required
def recent_guests_widget(request):
    if not request.user.is_staff: return HttpResponseForbidden()
    q = request.GET.get('q', '')
    status = request.GET.get('status', 'pending')
    guests = User.objects.all()
    
    if status == 'pending': guests = guests.exclude(billing_notes='')
    elif status == 'active': guests = guests.filter(billing_notes='').filter(is_staff=False)
    if q: guests = guests.filter(email__icontains=q)
    
    paginator = Paginator(guests.order_by('-date_joined'), 5)
    return render(request, 'account/partials/staff/_recent_guests.html', {'recent_guests': paginator.get_page(request.GET.get('page')), 'q': q, 'status': status})

@login_required
@require_POST
def resend_guest_invite(request, user_id):
    if not request.user.is_staff: return HttpResponseForbidden()
    user = get_object_or_404(User, id=user_id)
    if not user.billing_notes: return HttpResponse('Active')
    
    url = request.build_absolute_uri(reverse('coaching_booking:guest_access', args=[user.billing_notes]))
    send_transactional_email(recipient_email=user.email, subject="Access Link", template_name='emails/guest_welcome.html', context={'access_url': url, 'username': user.email})
    return HttpResponse('Sent!')

@login_required
@require_POST
def delete_guest_account(request, user_id):
    if not request.user.is_staff: return HttpResponseForbidden()
    User.objects.filter(id=user_id).delete()
    return HttpResponse("")