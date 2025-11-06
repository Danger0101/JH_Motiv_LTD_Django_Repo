from django.urls import path
from . import views

app_name = 'gcal'

urlpatterns = [
    path('init/', views.google_calendar_init, name='google_calendar_init'),
    path('redirect/', views.google_calendar_redirect, name='google_calendar_redirect'),
]
