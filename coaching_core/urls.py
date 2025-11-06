from django.urls import path
from . import views

app_name = 'coaching'

urlpatterns = [
    path('api/recurring-availability/', views.api_recurring_availability, name='api_recurring_availability'),
]