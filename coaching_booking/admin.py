from django.contrib import admin
from .models import ClientOfferingEnrollment, SessionBooking
from coaching_core.models import Offering
from django.db.models import F
from django.urls import reverse
from django.utils.html import format_html

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
    list_display = ('client_link', 'coach_link', 'offering_link', 'remaining_sessions', 'end_date', 'is_active')
    list_filter = ('is_active', 'coach', 'offering')
    search_fields = ['client__email', 'client__first_name', 'client__last_name', 'coach__user__email', 'offering__name']
    readonly_fields = ('enrolled_on', 'end_date')
    inlines = [SessionBookingInline]
    list_select_related = ('client', 'coach__user', 'offering') # Performance boost
    actions = ['add_bonus_session']

    @admin.action(description='Add 1 bonus session to selected enrollments')
    def add_bonus_session(self, request, queryset):
        """
        Admin action to add one bonus session to the selected enrollments.
        This increments both total_sessions and remaining_sessions.
        """
        # Use F() expressions for a race-condition-safe update at the database level.
        updated_count = queryset.update(
            total_sessions=F('total_sessions') + 1,
            remaining_sessions=F('remaining_sessions') + 1
        )
        self.message_user(
            request,
            f'Successfully added 1 bonus session to {updated_count} enrollment(s).',
        )
        
    @admin.display(description='Client', ordering='client')
    def client_link(self, obj):
        url = reverse("admin:accounts_user_change", args=[obj.client.pk])
        return format_html('<a href="{}">{}</a>', url, obj.client.get_full_name())

    @admin.display(description='Coach', ordering='coach')
    def coach_link(self, obj):
        if not obj.coach:
            return "-"
        url = reverse("admin:accounts_coachprofile_change", args=[obj.coach.pk])
        return format_html('<a href="{}">{}</a>', url, obj.coach.user.get_full_name())

    @admin.display(description='Offering', ordering='offering')
    def offering_link(self, obj):
        url = reverse("admin:coaching_core_offering_change", args=[obj.offering.pk])
        return format_html('<a href="{}">{}</a>', url, obj.offering.name)

@admin.register(SessionBooking)
class SessionBookingAdmin(admin.ModelAdmin):
    list_display = ('client', 'coach', 'start_datetime', 'status', 'gcal_event_id')
    list_filter = ('status', 'coach', 'start_datetime')
    date_hierarchy = 'start_datetime'
    search_fields = ['client__email', 'coach__user__email', 'gcal_event_id']
