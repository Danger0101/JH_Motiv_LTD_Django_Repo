from django.urls import path, include
from .views import update_marketing_preference, ProfileView, CustomLoginView


urlpatterns = [
    path("login/", CustomLoginView.as_view(), name="account_login"),
    path('update-marketing-preference/', update_marketing_preference, name='update_marketing_preference'),
    path('', include('allauth.urls')),
    path('profile/', ProfileView.as_view(), name='account_profile'),
]
