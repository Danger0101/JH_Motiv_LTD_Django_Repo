from django.urls import path
from .views import ProductListView, ProductDetailView, printful_webhook

app_name = 'products'

urlpatterns = [
    path('', ProductListView.as_view(), name='product_list'),
    path('<int:pk>/', ProductDetailView.as_view(), name='product_detail'),
    path('webhooks/printful/', printful_webhook, name='printful_webhook'),
]