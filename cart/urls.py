from django.urls import path
from . import views
from . import htmx_views

app_name = 'cart'

urlpatterns = [
    # Main Page
    path('', views.cart_detail, name='cart_detail'),
    path('apply-coupon/', views.apply_coupon, name='apply_coupon'),
    path('remove-coupon/', views.remove_coupon, name='remove_coupon'),
    
    # HTMX / Partial Actions
    path('htmx/items/', htmx_views.cart_item_list, name='cart_item_list'),
    path('htmx/summary/', htmx_views.cart_summary_panel, name='cart_summary_panel'),
    path('htmx/summary-fragment/', htmx_views.cart_summary_fragment, name='cart_summary_fragment'),
    path('add/<int:variant_id>/', htmx_views.add_to_cart, name='add_to_cart'),
    path('update/<int:item_id>/', htmx_views.update_cart_item, name='update_cart_item'),
    path('remove/<int:item_id>/', htmx_views.remove_from_cart, name='remove_from_cart'),
]