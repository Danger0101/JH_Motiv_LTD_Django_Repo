from django.urls import path
from . import views

app_name = 'core'

urlpatterns = [
    path('', views.home, name='home'),
    path('set-cookie-consent/', views.set_cookie_consent, name='set_cookie_consent'),
    path('about/', views.about_page, name='about'),
    path('faqs/', views.faqs_page, name='faqs'),
    path('faqs/<str:category>/', views.faq_tab, name='faq_tab'),
    path('privacy-policy/', views.privacy_policy_page, name='privacy_policy'),
    path('terms-of-service/', views.terms_of_service_page, name='terms_of_service'),
    path('shipping-policy/', views.shipping_policy_page, name='shipping_policy'),
    path('refund-policy/', views.refund_policy_page, name='refund_policy'),
    path('api/cheat-code/', views.claim_konami_coupon, name='claim_konami'),
]
