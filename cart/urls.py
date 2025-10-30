
from django.urls import path
from . import views

app_name = 'cart'

urlpatterns = [
    path('', views.cart_detail, name='cart_detail'),
    path('add/<int:variant_id>/', views.add_to_cart, name='add_to_cart'),
    path('update/<int:item_id>/', views.update_cart_item, name='update_cart_item'),
    path('summary/', views.cart_summary_fragment, name='cart_summary_fragment'),
    path('items/', views.cart_item_list, name='cart_item_list'),
    path('summary-panel/', views.cart_summary_panel, name='cart_summary_panel'),
]
