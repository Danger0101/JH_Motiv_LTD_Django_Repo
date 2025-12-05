from django.urls import path
from . import views

app_name = 'products'

urlpatterns = [
    path('', views.ProductListView.as_view(), name='product_list'),
    path('<int:pk>/', views.ProductDetailView.as_view(), name='product_detail'),
    
    # --- Printful Webhook Endpoint ---
    path('webhook/printful/', views.printful_webhook, name='printful_webhook'),
]