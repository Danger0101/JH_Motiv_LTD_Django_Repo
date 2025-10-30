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

     # --- INTEGRATION/PLACEHOLDER VIEWS ---
    path('calendar-link/init/', views.calendar_link_init, name='calendar_link_init'),
    path('calendar-link/callback/', views.calendar_link_callback, name='calendar_link_callback'),
    path('book/<int:coach_id>/', views.booking_page, name='booking_page'),

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
]