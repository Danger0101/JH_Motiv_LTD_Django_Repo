from django.urls import path, include
from . import views
from . import webhooks

app_name = 'coaching_booking'

urlpatterns = [
    path('', views.CoachLandingView.as_view(), name='coach_landing'),
    path('offers/', views.OfferListView.as_view(), name='offer-list'),
    path('enroll/<slug:slug>/', views.OfferEnrollmentStartView.as_view(), name='offer-enroll'),
    
    path('book-session/', views.book_session, name='book_session'),
    path('cancel-session/<int:booking_id>/', views.cancel_session, name='cancel_session'),
    path('reschedule-session/<int:booking_id>/', views.reschedule_session, name='reschedule_session'),
    path('reschedule-session-form/<int:booking_id>/', views.reschedule_session_form, name='reschedule_session_form'),
    path('reschedule/confirm/<int:booking_id>/', views.confirm_reschedule_modal, name='confirm_reschedule_modal'),
    path('profile/book-session/', views.profile_book_session_partial, name='profile_book_session'),
    path('get-booking-calendar/', views.get_booking_calendar, name='get_booking_calendar'),
    path('confirm-booking-modal/', views.confirm_booking_modal, name='confirm_booking_modal'),
    path('get-daily-slots/', views.get_daily_slots, name='get_daily_slots'),
    path('apply-for-free-session/', views.apply_for_free_session, name='apply_for_free_session'),
    path('coach-approve-free-session/', views.coach_approve_free_session, name='coach_approve_free_session'),
    path('coach-deny-free-session/', views.coach_deny_free_session, name='coach_deny_free_session'),
    path('webhooks/stripe/', webhooks.stripe_webhook, name='stripe_webhook'),
    path('booking/verify/<int:booking_id>/', views.check_payment_status, name='check_payment_status'),
    path('booking/pay/<int:booking_id>/', views.session_payment_page, name='session_payment_page'),
    path('book-workshop/<slug:slug>/', views.book_workshop, name='book_workshop'),
]