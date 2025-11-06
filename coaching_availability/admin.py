from django.contrib import admin
from .models import CoachAvailability, CoachVacation

@admin.register(CoachAvailability)
class CoachAvailabilityAdmin(admin.ModelAdmin):
    list_display = ('coach', 'day_of_week', 'start_time', 'end_time')
    list_filter = ('day_of_week', 'coach')
    ordering = ('coach', 'day_of_week', 'start_time')

@admin.register(CoachVacation)
class CoachVacationAdmin(admin.ModelAdmin):
    list_display = ('coach', 'start_date', 'end_date', 'cancel_bookings')
    list_filter = ('cancel_bookings', 'coach')
    date_hierarchy = 'start_date'