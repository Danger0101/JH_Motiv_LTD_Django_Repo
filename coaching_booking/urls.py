from django.urls import path
from . import views

app_name = 'coaching_booking'

urlpatterns = [
    path('', views.coach_landing_view, name='coach_landing'),
    path('offers/', views.OfferListView.as_view(), name='offer-list'),
    path('enroll/<slug:slug>/', views.OfferEnrollmentStartView.as_view(), name='offer-enroll'),
    path('schedule/<int:enrollment_pk>/', views.SessionBookingView.as_view(), name='session-schedule'),
    path('dashboard/', views.ClientDashboardView.as_view(), name='dashboard'),
]
