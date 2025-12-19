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
    path('taster/request/<int:offering_id>/', views.request_taster, name='request_taster'),
    path('taster/approve/<int:offer_id>/', views.approve_taster, name='approve_taster'),
    path('taster/decline/<int:offer_id>/', views.decline_taster, name='decline_taster'),
    path('taster/book/<int:offer_id>/', views.book_taster_session, name='book_taster_session'),
    path('webhooks/stripe/', webhooks.stripe_webhook, name='stripe_webhook'),
    path('booking/verify/<int:booking_id>/', views.check_payment_status, name='check_payment_status'),
    path('booking/pay/<int:booking_id>/', views.session_payment_page, name='session_payment_page'),
    path('guest-access/<str:token>/', views.guest_access_view, name='guest_access'),
    path('staff/create-guest/', views.staff_create_guest_account, name='staff_create_guest'),
    path('staff/send-password-reset/', views.staff_send_password_reset, name='staff_send_password_reset'),
    path('staff/recent-guests/', views.recent_guests_widget, name='recent_guests_widget'),
    path('staff/resend-invite/<int:user_id>/', views.resend_guest_invite, name='resend_guest_invite'),
    path('staff/delete-guest/<int:user_id>/', views.delete_guest_account, name='delete_guest_account'),
    path('book-workshop/<slug:slug>/', views.book_workshop, name='book_workshop'),
]