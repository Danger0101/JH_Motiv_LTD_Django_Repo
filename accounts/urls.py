from django.urls import path
from .views import update_marketing_preference

app_name = 'accounts'

urlpatterns = [
    path('update-marketing-preference/', update_marketing_preference, name='update_marketing_preference'),
]
