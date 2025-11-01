from django.urls import path
# Import views from the main file for non-API functions (Overview, Settings)
from . import views
# Import all specific view functions from their new modules
from .api_views import vacation, availability, offerings 

app_name = 'coaching'

urlpatterns = [
    # --- GENERAL VIEWS ---
    path('', views.CoachingOverview.as_view(), name='coaching_overview'),
    path('settings/', views.coach_settings_view, name='coach_settings'),
    path('programs/', views.program_list_view, name='program_list'),
    path('programs/purchase/<int:program_id>/', views.purchase_program_view, name='purchase_program'),

     # --- INTEGRATION/PLACEHOLDER VIEWS ---
    path('calendar-link/init/', views.calendar_link_init, name='calendar_link_init'),
    path('calendar-link/callback/', views.calendar_link_callback, name='calendar_link_callback'),
    path('book/<int:coach_id>/', views.booking_page, name='booking_page'),
    path('offering/<int:offering_id>/', views.offering_detail_view, name='offering_detail'),
    path('book/session/<int:offering_id>/', views.create_session_view, name='create_session'),

    # --- VACATION & AVAILABILITY API PATHS (Imported from Modules) ---
    # Vacation
    path('api/vacation/blocks/', vacation.coach_vacation_blocks, name='api_vacation_blocks'),
    path('api/vacation/blocks/<int:block_id>/', vacation.coach_vacation_block_detail, name='api_vacation_block_detail'),

    # Calendar & Modals (New paths for the interactive calendar feature)
    path('api/availability/calendar/', availability.coach_calendar_view, name='api_calendar_view'),
    path('api/availability/modal/', availability.coach_add_availability_modal_view, name='api_add_availability_modal'),
    path('api/availability/create/', availability.coach_create_availability_from_modal_view, name='api_create_availability_from_modal'),
    # Recurring Weekly Schedule Management
    path('api/availability/recurring/', availability.coach_recurring_availability_view, name='api_recurring_availability'),
    
    
    # Specific One-Off Slot Management
    path('api/availability/specific/', availability.coach_specific_availability_view, name='api_specific_availability'),
    path('api/availability/specific/<int:slot_id>/', availability.coach_specific_availability_detail, name='api_specific_availability_detail'),

    # --- OFFERINGS API PATHS (Imported from Modules) ---
    path('api/offerings/', offerings.coach_offerings_list_create, name='api_offerings_list_create'),
    path('api/offerings/<int:offering_id>/', offerings.coach_offerings_detail, name='api_offerings_detail'),

    # --- RESCHEDULE REQUEST ---
    path('reschedule/<uuid:token>/', views.reschedule_request_view, name='reschedule_request'),

    # --- COACH SWAP ---
    path('swap/initiate/<int:session_id>/<int:receiving_coach_id>/', views.initiate_swap_request_view, name='initiate_swap_request'),
    path('swap/coach-response/<uuid:token>/', views.coach_swap_response_view, name='coach_swap_response'),
    path('swap/user-response/<uuid:token>/', views.user_swap_response_view, name='user_swap_response'),

    # --- CANCELLATION ---
    path('cancel-session/<int:session_id>/', views.cancel_session_view, name='cancel_session'),

    # --- COACH DASHBOARD ---
    path('dashboard/', views.CoachDashboardView.as_view(), name='coach_dashboard'),

    # --- SESSION NOTES ---
    path('session-notes/<int:session_id>/', views.session_notes_view, name='session_notes'),
]