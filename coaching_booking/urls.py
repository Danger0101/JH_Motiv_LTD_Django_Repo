from django.urls import path, include
from . import views

app_name = 'coaching_booking'

urlpatterns = [
    path('', views.coach_landing_view, name='coach_landing'),
    path('offers/', views.OfferListView.as_view(), name='offer-list'),
    path('enroll/<slug:slug>/', views.OfferEnrollmentStartView.as_view(), name='offer-enroll'),
    path('schedule/<int:enrollment_pk>/', views.SessionBookingView.as_view(), name='session-schedule'),
    path('book-session/', views.book_session, name='book_session'),
    path('cancel-session/<int:booking_id>/', views.cancel_session, name='cancel_session'),
    path('reschedule-session/<int:booking_id>/', views.reschedule_session, name='reschedule_session'),
    path('reschedule-session-form/<int:booking_id>/', views.reschedule_session_form, name='reschedule_session_form'),
    path('profile/book-session/', views.profile_book_session_partial, name='profile_book_session'),
    path('get-booking-calendar/', views.get_booking_calendar, name='get_booking_calendar'),
    path('get-daily-slots/', views.get_daily_slots, name='get_daily_slots'),
    path('book-session/confirm/', views.book_session_confirm, name='book_session_confirm'),
]
