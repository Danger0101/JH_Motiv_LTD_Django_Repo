from django.urls import path, include
from . import views
from allauth.account import views as allauth_views

app_name = 'account'

urlpatterns = [
    path('update-marketing-preference/', views.update_marketing_preference, name='update_marketing_preference'),
    path('profile/', views.ProfileView.as_view(), name='account_profile'),

    # HTMX specific URLs for profile data fragments
    path('htmx/enrollment-status/', views.EnrollmentStatusHtmxView.as_view(), name='htmx_enrollment_status'),
    path('htmx/session-list/', views.SessionListHtmxView.as_view(), name='htmx_session_list'),
    path('htmx/order-history/', views.OrderHistoryHtmxView.as_view(), name='htmx_order_history'),

    # allauth urls (explicitly defined for namespacing)
    path('login/', views.CustomLoginView.as_view(), name='login'),
    path('logout/', views.CustomLogoutView.as_view(), name='logout'),
    path('signup/', views.CustomSignupView.as_view(), name='signup'),
    path('password/change/', views.CustomPasswordChangeView.as_view(), name='password_change'),
    path('password/set/', views.CustomPasswordSetView.as_view(), name='password_set'),
    path('password/reset/', views.CustomPasswordResetView.as_view(), name='password_reset'),
    path('password/reset/done/', views.CustomPasswordResetDoneView.as_view(), name='password_reset_done'),
]
