from django.urls import path
from . import views

app_name = 'core'

urlpatterns = [
    path('', views.home, name='home'),
    path('set-cookie-consent/', views.set_cookie_consent, name='set_cookie_consent'),
    path('about/', views.AboutView.as_view(), name='about'),
   path('faqs/', views.faqs_page, name='faqs'),
    path('privacy-policy/', views.PrivacyPolicyView.as_view(), name='privacy_policy'),
    path('terms-of-service/', views.TermsOfServiceView.as_view(), name='terms_of_service'),
    path('shipping-policy/', views.ShippingPolicyView.as_view(), name='shipping_policy'),
    path('refund-policy/', views.RefundPolicyView.as_view(), name='refund_policy'),
]
