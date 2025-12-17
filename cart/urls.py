from django.urls import path
from . import views

app_name = 'cart'

urlpatterns = [
    # Main Page
    path('', views.cart_detail, name='cart_detail'),
    path('apply-coupon/', views.apply_coupon, name='apply_coupon'),
    path('remove-coupon/', views.remove_coupon, name='remove_coupon'),
    
    # HTMX / Partial Actions
    path('htmx/items/', views.cart_item_list, name='cart_item_list'),
    path('htmx/summary/', views.cart_summary_panel, name='cart_summary_panel'),
    path('htmx/summary-fragment/', views.cart_summary_fragment, name='cart_summary_fragment'),
    path('add/<int:variant_id>/', views.add_to_cart, name='add_to_cart'),
    
    # This was missing!
    path('update/<int:item_id>/', views.update_cart_item, name='update_cart_item'),
]