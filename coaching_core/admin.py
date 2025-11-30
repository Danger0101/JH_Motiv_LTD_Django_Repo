from django.contrib import admin
from .models import Offering, Workshop
from accounts.models import CoachProfile

# Note: The inline configuration below assumes that your 'Offering' model
# has a ManyToManyField named 'coaches'. If you have a custom 'through'

# model, you should specify it directly in the inline.

class CoachAssignmentInline(admin.TabularInline):
    # This will use the auto-generated through model for the 'coaches' ManyToManyField.
    # If your field is named differently, update 'Offering.coaches.through'.
    model = Offering.coaches.through
    extra = 1
    verbose_name = "Coach Assignment"
    verbose_name_plural = "Coach Assignments"

@admin.register(Offering)
class OfferingAdmin(admin.ModelAdmin):
    list_display = ('name', 'session_length_minutes', 'price', 'active_status', 'created_by')
    list_filter = ('active_status', 'duration_type', 'is_whole_day')
    search_fields = ['name', 'description']
    fieldsets = (
        ('Service Details', {
            'fields': ('name', 'description')
        }),
        ('Pricing & Length', {
            'fields': ('price', 'duration_type', 'total_length_units', 'session_length_minutes', 'total_number_of_sessions', 'is_whole_day')
        }),
        ('Status & Audit', {
            'fields': ('active_status', 'created_by', 'created_at')
        }),
    )
    readonly_fields = ('created_at',)
    inlines = [CoachAssignmentInline]


@admin.register(Workshop)
class WorkshopAdmin(admin.ModelAdmin):
    list_display = ('name', 'coach', 'date', 'start_time', 'price', 'total_attendees', 'active_status')
    list_filter = ('active_status', 'is_free', 'coach', 'date')
    search_fields = ['name', 'description', 'coach__user__first_name', 'coach__user__last_name']
    fieldsets = (
        ('Workshop Details', {
            'fields': ('name', 'coach', 'description')
        }),
        ('Time and Date', {
            'fields': ('date', 'start_time', 'end_time')
        }),
        ('Pricing and Capacity', {
            'fields': ('price', 'is_free', 'total_attendees')
        }),
        ('Status & Audit', {
            'fields': ('active_status', 'created_by', 'created_at')
        }),
    )
    readonly_fields = ('created_at',)
    autocomplete_fields = ['coach']