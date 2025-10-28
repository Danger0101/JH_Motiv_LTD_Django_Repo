from django.urls import path
from . import views

app_name = 'payments'

urlpatterns = [
    path('order-track/<uuid:guest_order_token>/', views.order_detail_guest, name='order_detail_guest'),
]