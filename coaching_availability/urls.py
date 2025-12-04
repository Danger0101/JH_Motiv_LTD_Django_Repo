from django.urls import path
from . import views

app_name = 'coaching_availability'

urlpatterns = [
    # Existing Weekly Schedule
    path('', views.profile_availability, name='profile_availability'),

    # NEW: Date Overrides (One-Offs)
    path('profile/override/', views.profile_override, name='profile_override'),
    path('override/save/', views.save_date_override, name='save_date_override'),
    path('override/delete/<int:pk>/', views.delete_date_override, name='delete_date_override'),

    # NEW: Vacation Management
    path('profile/vacation/', views.profile_vacation, name='profile_vacation'),
    path('vacation/save/', views.save_coach_vacation, name='save_coach_vacation'),
    path('vacation/delete/<int:pk>/', views.delete_coach_vacation, name='delete_coach_vacation'),
]
