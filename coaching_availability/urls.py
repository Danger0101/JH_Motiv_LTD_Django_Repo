from django.urls import path
from .views import (
    SetRecurringScheduleView,
    SetDateOverrideView,
    ManageVacationView
)

urlpatterns = [
    path(
        'schedule/recurring/',
        SetRecurringScheduleView.as_view(),
        name='set_recurring_schedule'
    ),
    path(
        'schedule/override/',
        SetDateOverrideView.as_view(),
        name='set_date_override'
    ),
    path(
        'schedule/vacation/',
        ManageVacationView.as_view(),
        name='manage_vacation'
    ),
]
