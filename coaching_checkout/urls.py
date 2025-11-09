from django.urls import path
from . import views

app_name = 'coaching_checkout'

urlpatterns = [
    # Initiates the Stripe Checkout Session
    path('checkout/<slug:slug>/', views.CreateCoachingCheckoutSessionView.as_view(), name='checkout'),
    
    # Stripe Webhook Endpoint (must be publicly accessible)
    path('webhook/', views.stripe_webhook_received, name='webhook'),
    
    # Success/Cancel pages (client is redirected here from Stripe)
    path('success/', views.CheckoutSuccessView.as_view(), name='checkout_success'),
    path('cancel/', views.CheckoutCancelView.as_view(), name='checkout_cancel'),
]