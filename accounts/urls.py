from django.urls import path, include
from .views import update_marketing_preference

urlpatterns = [
    path('update-marketing-preference/', update_marketing_preference, name='update_marketing_preference'),
    path('', include('allauth.urls')),
    path
]
