from django.shortcuts import render, get_object_or_404
from django.views.generic import DetailView
from .models import DreamerProfile
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

        # Find the coupon associated with this dreamer's user account
        if dreamer_profile.user:
            try:
                coupon = Coupon.objects.get(user_specific=dreamer_profile.user, active=True)
                # Set the cookie for affiliate tracking. Expires in 30 days.
                response.set_cookie('affiliate_coupon', coupon.code, max_age=2592000, samesite='Lax', secure=True)
                logger.info(f"Affiliate cookie for coupon '{coupon.code}' set for visitor of dreamer page '{dreamer_profile.slug}'.")
            except Coupon.DoesNotExist:
                logger.warning(f"No active, user-specific coupon found for dreamer '{dreamer_profile.name}' (User ID: {dreamer_profile.user.id}).")
            except Coupon.MultipleObjectsReturned:
                logger.error(f"CRITICAL: Multiple active, user-specific coupons found for dreamer '{dreamer_profile.name}' (User ID: {dreamer_profile.user.id}). Only one should exist.")

        return response