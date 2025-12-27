from django.views.generic import ListView, DetailView, TemplateView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.utils import timezone
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login
from django.utils.crypto import get_random_string
from django.db.models import Q
from datetime import datetime

from accounts.models import CoachProfile, User
from coaching_core.models import Offering, Workshop
from coaching_client.models import ContentPage
from cart.utils import get_or_create_cart, get_cart_summary_data
from facts.models import Fact
from ..models import SessionBooking
from ..services import BookingService
from core.email_utils import send_transactional_email

class CoachLandingView(TemplateView):
    template_name = "coaching_booking/coach_landing.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        coaches = CoachProfile.objects.filter(user__is_active=True, is_available_for_new_clients=True).select_related('user')
        offerings = Offering.objects.filter(active_status=True).prefetch_related('coaches__user')
        workshops = Workshop.objects.filter(active_status=True)
        knowledge_pages = ContentPage.objects.filter(is_published=True).order_by('title')[:3]
        facts = Fact.objects.all()
        KNOWLEDGE_CATEGORIES = [('all', 'Business Coaches')]
        cart = get_or_create_cart(self.request)
        
        upcoming_workshops = Workshop.objects.filter(
            active_status=True,
            date__gte=timezone.now()
        ).order_by('date')[:3]

        context.update({
            'coaches': coaches,
            'offerings': offerings,
            'workshops': workshops,
            'knowledge_pages': knowledge_pages,
            'facts': facts,
            'knowledge_categories': KNOWLEDGE_CATEGORIES[1:],
            'page_summary_text': "Welcome to our coaching services!",
            'upcoming_workshops': upcoming_workshops,
            'summary': get_cart_summary_data(cart),
        })
        return context

class OfferListView(ListView):
    model = Offering
    template_name = 'coaching_booking/offering_list.html'
    context_object_name = 'offerings'
    def get_queryset(self):
        return Offering.objects.filter(active_status=True)
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        cart = get_or_create_cart(self.request)
        context['summary'] = get_cart_summary_data(cart)
        return context

class OfferEnrollmentStartView(LoginRequiredMixin, DetailView):
    model = Offering
    template_name = 'coaching_booking/checkout_embedded.html'
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['STRIPE_PUBLIC_KEY'] = settings.STRIPE_PUBLISHABLE_KEY
        cart = get_or_create_cart(self.request)
        context['summary'] = get_cart_summary_data(cart)
        return context

def book_workshop(request, slug):
    workshop = get_object_or_404(Workshop, slug=slug)
    if request.method == 'POST':
        email = request.POST.get('email')
        full_name = request.POST.get('full_name')
        business_name = request.POST.get('business_name')
        
        if not email or not full_name:
            messages.error(request, "Name and Email are required.")
            return redirect('coaching_core:workshop_detail', slug=slug)

        user = None
        if request.user.is_authenticated:
            user = request.user
            if business_name and not user.business_name:
                user.business_name = business_name
                user.save()
        else:
            existing_user = User.objects.filter(Q(email=email) | Q(username=email)).first()
            if existing_user:
                user = existing_user
            else:
                first_name = full_name.split(' ')[0]
                last_name = ' '.join(full_name.split(' ')[1:]) if ' ' in full_name else ''
                random_password = get_random_string(12)
                user = User.objects.create_user(username=email, email=email, password=random_password, first_name=first_name, last_name=last_name, business_name=business_name)
                guest_token = get_random_string(32)
                user.billing_notes = guest_token 
                user.save()
                login(request, user, backend='django.contrib.auth.backends.ModelBackend')
                
                access_url = request.build_absolute_uri(reverse('coaching_booking:guest_access', args=[guest_token]))
                context = {'site_name': getattr(settings, 'SITE_NAME', 'JH Motiv'), 'access_url': access_url, 'username': email, 'password': random_password, 'workshop_name': workshop.name, 'is_new_account': True}
                send_transactional_email(recipient_email=email, subject=f"Welcome to {context['site_name']}", template_name='emails/guest_welcome.html', context=context)

        if SessionBooking.objects.filter(client=user, workshop=workshop).exists():
            messages.info(request, "You are already booked for this workshop!")
            return redirect('accounts:account_profile')

        if workshop.price == 0:
            start_dt = datetime.combine(workshop.date, workshop.start_time)
            if timezone.is_naive(start_dt): start_dt = timezone.make_aware(start_dt)
            booking = SessionBooking.objects.create(client=user, coach=workshop.coach, workshop=workshop, start_datetime=start_dt, status='BOOKED', amount_paid=0)
            BookingService.send_confirmation_emails(request, booking)
            messages.success(request, "Workshop booked successfully!")
            return redirect('accounts:account_profile')
        else:
            return redirect('payments:checkout_workshop', workshop_id=workshop.id)
    return redirect('coaching_core:workshop_detail', slug=slug)