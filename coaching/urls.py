
from django.urls import path
from . import views

app_name = 'coaching'

urlpatterns = [
    path('', views.CoachingOverview.as_view(), name='coaching_overview'),
    path('calendar-link/init/', views.calendar_link_init, name='calendar_link_init'),
    path('calendar-link/callback/', views.calendar_link_callback, name='calendar_link_callback'),
    path('book/<int:coach_id>/', views.booking_page, name='booking_page'),
]
