from django.urls import path
from . import views

app_name = 'coaching_booking'

urlpatterns = [
    path('', views.OfferListView.as_view(), name='offer-list'),
    path('enroll/<slug:slug>/', views.OfferEnrollmentStartView.as_view(), name='offer-enroll'),
    path('schedule/<int:enrollment_pk>/', views.SessionBookingView.as_view(), name='session-schedule'),
    path('dashboard/', views.ClientDashboardView.as_view(), name='dashboard'),
]
