from django.contrib import admin
from .models import (
    CoachingSession,
    CoachVacationBlock,
    RecurringAvailability,
    SpecificAvailability,
    CoachOffering
)

@admin.register(CoachingSession)
class CoachingSessionAdmin(admin.ModelAdmin):
    list_display = ('service_name', 'coach', 'client', 'start_time', 'status')
    list_filter = ('status', 'coach', 'start_time')
    search_fields = ('service_name', 'client__username', 'coach__username')

# --- New Availability & Offerings Registration ---

@admin.register(CoachVacationBlock)
class CoachVacationBlockAdmin(admin.ModelAdmin):
    list_display = ('coach', 'start_date', 'end_date', 'reason')
    list_filter = ('coach',)

@admin.register(RecurringAvailability)
class RecurringAvailabilityAdmin(admin.ModelAdmin):
    list_display = ('coach', 'day_of_week', 'start_time', 'end_time', 'is_available')
    list_filter = ('coach', 'day_of_week', 'is_available')
    # Use the human-readable day name for sorting
    ordering = ('day_of_week', 'start_time')

@admin.register(SpecificAvailability)
class SpecificAvailabilityAdmin(admin.ModelAdmin):
    list_display = ('coach', 'date', 'start_time', 'end_time', 'is_available')
    list_filter = ('coach', 'date', 'is_available')
    ordering = ('date', 'start_time')
    date_hierarchy = 'date' # Adds a date navigation bar

@admin.register(CoachOffering)
class CoachOfferingAdmin(admin.ModelAdmin):
    list_display = ('name', 'coach', 'price', 'duration_minutes', 'is_active')
    list_filter = ('coach', 'is_active')
    search_fields = ('name', 'description')
    prepopulated_fields = {'slug': ('name',)}