from django.urls import path
from . import views

urlpatterns = [
    path('', views.dashboard_view, name='dashboard'),
    path('coach/', views.CoachDashboardView.as_view(), name='coach_dashboard'),
    path('staff/', views.StaffDashboardView.as_view(), name='staff_dashboard'),
    path('client/', views.ClientDashboardView.as_view(), name='client_dashboard'),
]