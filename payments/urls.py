from django.urls import path
from . import views

app_name = 'payments'

urlpatterns = [
    path('create-checkout-session/<int:program_id>/', views.create_checkout_session, name='create_checkout_session'),
    path('success/', views.payment_success, name='payment_success'),
    path('cancel/', views.payment_cancel, name='payment_cancel'),
    path('webhook/', views.stripe_webhook, name='stripe_webhook'),
    path('order-track/<uuid:guest_order_token>/', views.order_detail_guest, name='order_detail_guest'),
]
