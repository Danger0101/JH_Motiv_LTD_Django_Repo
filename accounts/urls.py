from django.urls import path, include, re_path
from . import views
from allauth.account import views as allauth_views


app_name = 'accounts'

urlpatterns = [
    path('update-marketing-preference/', views.update_marketing_preference, name='update_marketing_preference'),
    path('profile/', views.ProfileView.as_view(), name='account_profile'),
    path('profile/dashboard-partial/', views.dashboard_partial, name='dashboard_partial'),
    path('profile/offerings/', views.profile_offerings_partial, name='profile_offerings'),
    path('profile/bookings/', views.profile_bookings_partial, name='profile_bookings'),
    path('profile/recent-activity/', views.recent_activity_partial, name='recent_activity_partial'),
    path('profile/get-coaches-for-offering/', views.get_coaches_for_offering, name='get_coaches_for_offering'),
    path('profile/coach-clients-partial/', views.coach_clients_partial, name='coach_clients_partial'),
    path('profile/coach-reviews-partial/', views.coach_reviews_partial, name='coach_reviews_partial'),
    path('profile/invoice/<int:order_id>/', views.generate_invoice_pdf, name='generate_invoice_pdf'),
    path('profile/booking/<int:booking_id>/ics/', views.download_booking_ics, name='download_booking_ics'),
    # Staff/Admin URLs for the profile dashboard
    path('staff/dashboard/', views.StaffDashboardView.as_view(), name='staff_dashboard'),
    path('staff/customer-lookup/', views.staff_customer_lookup, name='staff_customer_lookup'),
    path('staff/update-order/<int:order_id>/', views.staff_update_order, name='staff_update_order'),
    path('staff/get-order-row/<int:order_id>/', views.staff_get_order_row, name='staff_get_order_row'),
    # allauth urls (explicitly defined for namespacing)
    path('login/', views.CustomLoginView.as_view(), name='login'),
    path('logout/', views.CustomLogoutView.as_view(), name='logout'),
    path('signup/', views.CustomSignupView.as_view(), name='signup'),
    path('password/change/', views.CustomPasswordChangeView.as_view(), name='password_change'),
    path('password/set/', views.CustomPasswordSetView.as_view(), name='password_set'),
    path('password/reset/', views.CustomPasswordResetView.as_view(), name='password_reset'),
    path('password/reset/done/', views.CustomPasswordResetDoneView.as_view(), name='password_reset_done'),
    path('password/reset/key/<str:key>/', views.CustomPasswordResetFromKeyView.as_view(), name="account_reset_password_from_key"),
    path('password/reset/key/done/', views.CustomPasswordResetFromKeyDoneView.as_view(), name='account_reset_password_from_key_done'),
    path('email/', views.CustomEmailView.as_view(), name='account_email'),
    path('confirm-email/', views.CustomEmailVerificationSentView.as_view(), name='account_email_verification_sent'),
    re_path(r'^confirm-email/(?P<key>[-:\w]+)/$', views.CustomConfirmEmailView.as_view(), name='account_confirm_email'),
    # Custom Allauth Social Account Connections View for HTMX
    path('3rdparty/', views.CustomSocialAccountListView.as_view(), name='socialaccount_connections'),
    # Guest Conversion & Deactivation
    path('convert-guest/', views.ConvertGuestView.as_view(), name='convert_guest'),
    path('deactivate/', views.DeactivateAccountView.as_view(), name='deactivate_account'),
    path('reactivate/<uidb64>/<token>/', views.ReactivateAccountView.as_view(), name='reactivate_account'),
    path('profile/copy-schedule/', views.CopyScheduleView.as_view(), name='copy_schedule'),
]