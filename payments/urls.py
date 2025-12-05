# d:\GitHub\JH_Motiv_LTD_Django_Repo\payments\urls.py
from django.urls import path
from . import views

app_name = 'payments'

urlpatterns = [
    path('create-checkout-session/', views.create_checkout_session, name='create_checkout_session'),
    path('success/', views.payment_success, name='payment_success'),
    path('cancel/', views.payment_cancel, name='payment_cancel'),
    path('webhook/', views.stripe_webhook, name='webhook'),
    path('guest-order/<uuid:guest_order_token>/', views.order_detail_guest, name='order_detail_guest'),
    
    path('order/<int:order_id>/', views.order_detail, name='order_detail'),
    path('api/calculate-shipping/', views.calculate_shipping_api, name='calculate_shipping'),
    
    # The PAGE that shows the address form
    path('checkout/', views.checkout_cart_view, name='checkout_cart'),
    
    # Corrected URL for creating a coaching checkout session
    path('create-coaching-checkout-session/<int:offering_id>/', views.create_coaching_checkout_session_view, name='create_coaching_checkout_session'),
]