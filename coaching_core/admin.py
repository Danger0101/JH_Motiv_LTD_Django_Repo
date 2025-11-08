from django.contrib import admin
from .models import Offering
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