from django.shortcuts import render, get_object_or_404, redirect
from django.views.generic import DetailView, CreateView, ListView, View
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib import messages
from django.urls import reverse_lazy
from django.utils import timezone
from django.db import transaction
from django.core.mail import send_mail
from django.conf import settings
from .models import DreamerProfile
from .forms import DreamerApplicationForm
from payments.models import Coupon
import logging

logger = logging.getLogger(__name__)

class DreamerLandingView(DetailView):
    """
    Displays a public landing page for a Dreamer (affiliate).
    It also sets the affiliate tracking cookie if a valid coupon is associated.
    """
    model = DreamerProfile
    template_name = 'dreamers/dreamer_landing_page.html'
    context_object_name = 'dreamer'
    slug_field = 'slug'
    slug_url_kwarg = 'slug'

    def get(self, request, *args, **kwargs):
        response = super().get(request, *args, **kwargs)
        dreamer_profile = self.get_object()

        # FIX: Look up by 'affiliate_dreamer', NOT 'user_specific'
        # This allows the coupon to be public (shareable) but still owned by the Dreamer.
        try:
            coupon = Coupon.objects.get(affiliate_dreamer=dreamer_profile, active=True)
            # Set the cookie for affiliate tracking. Expires in 30 days.
            response.set_cookie('affiliate_coupon', coupon.code, max_age=2592000, samesite='Lax', secure=True)
            logger.info(f"Affiliate cookie '{coupon.code}' set for visitor of '{dreamer_profile.slug}'.")
        except Coupon.DoesNotExist:
            logger.warning(f"No active affiliate coupon found for dreamer '{dreamer_profile.name}'.")
        except Coupon.MultipleObjectsReturned:
            logger.error(f"Multiple active coupons found for dreamer '{dreamer_profile.name}'.")

        return response

class DreamerApplicationView(LoginRequiredMixin, CreateView):
    """Allows a user to apply to become a Dreamer."""
    model = DreamerProfile
    form_class = DreamerApplicationForm
    template_name = 'dreamers/apply.html'
    success_url = reverse_lazy('accounts:account_profile')

    def dispatch(self, request, *args, **kwargs):
        # Prevent double application
        if hasattr(request.user, 'dreamer_profile'):
            messages.info(request, "You have already submitted a Dreamer application.")
            return redirect('accounts:account_profile')
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        form.instance.user = self.request.user
        form.instance.status = DreamerProfile.STATUS_PENDING
        messages.success(self.request, "Application submitted! Our staff will review your request shortly.")
        
        # Notify Staff (Optional: You could use a background task here)
        send_mail(
            subject=f"New Dreamer Application: {self.request.user.username}",
            message=f"User {self.request.user.email} has applied to be a Dreamer.\n\nReview here: {settings.SITE_URL}/admin/dreamers/dreamerprofile/",
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[settings.DEFAULT_FROM_EMAIL], # Send to admin
            fail_silently=True
        )
        return super().form_valid(form)

class StaffDreamerManageView(UserPassesTestMixin, ListView):
    """Staff dashboard view to manage pending applications."""
    model = DreamerProfile
    template_name = 'dreamers/staff_manage.html'
    context_object_name = 'applications'

    def test_func(self):
        return self.request.user.is_staff

    def get_queryset(self):
        return DreamerProfile.objects.filter(status=DreamerProfile.STATUS_PENDING)

class StaffDreamerActionView(UserPassesTestMixin, View):
    """Handle Approve/Reject actions."""
    
    def test_func(self):
        return self.request.user.is_staff

    def post(self, request, pk):
        profile = get_object_or_404(DreamerProfile, pk=pk)
        action = request.POST.get('action')
        
        if action == 'approve':
            with transaction.atomic():
                # 1. Update Profile
                profile.status = DreamerProfile.STATUS_APPROVED
                profile.save()
                
                # 2. Update User
                if profile.user:
                    profile.user.is_dreamer = True
                    profile.user.save()
                    
                    # 3. Generate Affiliate Coupon (e.g., ASHLEY10)
                    base_code = profile.name.split()[0].upper().replace("'", "") # Simple heuristic
                    code = f"{base_code}10"
                    
                    # Ensure uniqueness
                    counter = 1
                    while Coupon.objects.filter(code=code).exists():
                        code = f"{base_code}{10 + counter}"
                        counter += 1
                    
                    coupon = Coupon.objects.create(
                        code=code,
                        discount_type=Coupon.DISCOUNT_TYPE_PERCENT,
                        discount_value=10,
                        active=True,
                        valid_from=timezone.now(),
                        valid_to=timezone.now() + timezone.timedelta(days=3650), # 10 years
                        affiliate_dreamer=profile,
                        referrer=profile.user,
                        usage_limit=None # Unlimited use
                    )
                    
                    # 4. Send Email
                    send_mail(
                        subject="You're In! Dreamer Application Approved",
                        message=f"Welcome to the Wall of Dreamers!\n\nYour application has been approved.\nYour unique affiliate code is: {code}\n\nShare this code to give 10% off and earn commissions.",
                        from_email=settings.DEFAULT_FROM_EMAIL,
                        recipient_list=[profile.user.email],
                    )
                    messages.success(request, f"Approved {profile.name}. Coupon {code} created.")

        elif action == 'reject':
            profile.status = DreamerProfile.STATUS_REJECTED
            profile.rejection_reason = request.POST.get('reason', '')
            profile.save()
            
            if profile.user:
                send_mail(
                    subject="Update on your Dreamer Application",
                    message=f"Thank you for applying. Unfortunately, we cannot accept your application at this time.\nReason: {profile.rejection_reason}",
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[profile.user.email],
                )
            messages.warning(request, f"Rejected {profile.name}.")

        return redirect('dreamers:staff_manage')