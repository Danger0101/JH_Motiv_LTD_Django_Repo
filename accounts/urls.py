from django.urls import path, include
from .views import ProfileView # Only need the specific view

urlpatterns = [
    # 1. Include all the core allauth paths (login, logout, signup, etc.)
    path('', include('allauth.urls')),
    
    # 2. Add your custom profile page path, which requires login
    path('profile/', ProfileView.as_view(), name='account_profile'),
]