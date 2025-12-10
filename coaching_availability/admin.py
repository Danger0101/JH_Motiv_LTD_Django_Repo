from django.contrib import admin
from .models import CoachAvailability, DateOverride, CoachVacation

@admin.register(CoachAvailability)
class CoachAvailabilityAdmin(admin.ModelAdmin):
    list_display = ('coach_name', 'day_name', 'time_range')
    list_filter = ('day_of_week', 'coach')
    ordering = ('coach', 'day_of_week', 'start_time')
    list_select_related = ('coach',)

    @admin.display(description='Coach', ordering='coach__username')
    def coach_name(self, obj):
        return obj.coach.get_full_name()

    @admin.display(description='Day', ordering='day_of_week')
    def day_name(self, obj):
        return obj.get_day_of_week_display()

    @admin.display(description='Time Slot')
    def time_range(self, obj):
        return f"{obj.start_time.strftime('%H:%M')} - {obj.end_time.strftime('%H:%M')}"

@admin.register(DateOverride)
class DateOverrideAdmin(admin.ModelAdmin):
    list_display = ('coach', 'date', 'status_display', 'time_range')
    list_filter = ('is_available', 'date', 'coach')
    date_hierarchy = 'date'
    list_select_related = ('coach',)

    @admin.display(description='Status', boolean=True)
    def status_display(self, obj):
        return obj.is_available

    @admin.display(description='Time Override')
    def time_range(self, obj):
        if not obj.is_available:
            return "BLOCKED"
        if obj.start_time and obj.end_time:
            return f"{obj.start_time.strftime('%H:%M')} - {obj.end_time.strftime('%H:%M')}"
        return "All Day Available"

@admin.register(CoachVacation)
class CoachVacationAdmin(admin.ModelAdmin):
    list_display = ('coach', 'start_date', 'end_date', 'existing_booking_handling')
    list_filter = ('existing_booking_handling', 'coach')
    search_fields = ('coach__email', 'coach__first_name')
    list_select_related = ('coach',)
