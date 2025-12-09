from django.urls import path
from . import views
from .htmx_views import (
    cart_item_list, cart_summary_panel, add_to_cart, remove_from_cart, update_cart_item
)

app_name = 'cart'

urlpatterns = [
    path('', views.cart_detail, name='cart_detail'),
    path('apply-coupon/', views.apply_coupon, name='apply_coupon'),
    # ... other urls
]