from django.urls import path
from . import views

app_name = 'coaching_availability'

urlpatterns = [
    path('', views.profile_availability, name='profile_availability'),
    path(
        'schedule/recurring/',
        views.SetRecurringScheduleView.as_view(),
        name='set_recurring_schedule'
    ),
    path(
        'schedule/override/',
        views.SetDateOverrideView.as_view(),
        name='set_date_override'
    ),
    path(
        'schedule/vacation/',
        views.ManageVacationView.as_view(),
        name='manage_vacation'
    ),
]
