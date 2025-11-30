from django.urls import path
from . import views

app_name = 'coaching_availability'

urlpatterns = [
    path('', views.profile_availability, name='profile_availability'),


]
