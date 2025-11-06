from django.contrib import admin
from .models import ClientOfferingEnrollment, SessionBooking
from coaching_core.models import Offering

class SessionBookingInline(admin.TabularInline):
    model = SessionBooking
    extra = 0  # Don't show extra forms for new bookings by default
    readonly_fields = ('start_datetime', 'status', 'gcal_event_id')
    can_delete = False
    verbose_name = "Scheduled Session"
    verbose_name_plural = "Scheduled Sessions"

    def has_add_permission(self, request, obj=None):
        return False

@admin.register(ClientOfferingEnrollment)
class EnrollmentAdmin(admin.ModelAdmin):
    list_display = ('client', 'coach', 'offering', 'remaining_sessions', 'is_active')
    list_filter = ('is_active', 'coach', 'offering')
    search_fields = ['client__email', 'coach__user__email']
    readonly_fields = ('total_sessions', 'enrolled_on')
    inlines = [SessionBookingInline]

@admin.register(SessionBooking)
class SessionBookingAdmin(admin.ModelAdmin):
    list_display = ('client', 'coach', 'start_datetime', 'status', 'gcal_event_id')
    list_filter = ('status', 'coach', 'start_datetime')
    date_hierarchy = 'start_datetime'
    search_fields = ['client__email', 'coach__user__email', 'gcal_event_id']
