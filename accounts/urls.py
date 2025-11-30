from django.urls import path, include
from . import views
from allauth.account import views as allauth_views

app_name = 'accounts'

urlpatterns = [
    path('update-marketing-preference/', views.update_marketing_preference, name='update_marketing_preference'),
    path('profile/', views.ProfileView.as_view(), name='account_profile'),


    path('profile/offerings/', views.profile_offerings_partial, name='profile_offerings'),
    path('profile/bookings/', views.profile_bookings_partial, name='profile_bookings'),
    path('profile/book-session/', views.profile_book_session_partial, name='profile_book_session'),
    path('profile/get-coaches-for-offering/', views.get_coaches_for_offering, name='get_coaches_for_offering'),
    path('profile/get-available-slots/', views.get_available_slots, name='get_available_slots'),


    # allauth urls (explicitly defined for namespacing)
    path('login/', views.CustomLoginView.as_view(), name='login'),
    path('logout/', views.CustomLogoutView.as_view(), name='logout'),
    path('signup/', views.CustomSignupView.as_view(), name='signup'),
    path('password/change/', views.CustomPasswordChangeView.as_view(), name='password_change'),
    path('password/set/', views.CustomPasswordSetView.as_view(), name='password_set'),
    path('password/reset/', views.CustomPasswordResetView.as_view(), name='password_reset'),
    path('password/reset/done/', views.CustomPasswordResetDoneView.as_view(), name='password_reset_done'),
]
