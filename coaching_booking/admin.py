from django.contrib import admin
from django.db.models import F
from django.utils.html import format_html
from django.urls import reverse
from django.utils import timezone
from datetime import timedelta
from .models import ClientOfferingEnrollment, SessionBooking, OneSessionFreeOffer
from coaching_availability.models import CoachAvailability
from accounts.models import User

# --- INLINES ---

class SessionBookingInline(admin.TabularInline):
    model = SessionBooking
    extra = 0  # Don't show extra forms for new bookings by default
    fields = ('start_datetime', 'status', 'coach_link', 'gcal_event_id')
    readonly_fields = ('start_datetime', 'status', 'coach_link', 'gcal_event_id')
    can_delete = False
    show_change_link = True # Allows jumping to the full booking edit page
    verbose_name = "Scheduled Session"
    verbose_name_plural = "Scheduled Sessions"

    def has_add_permission(self, request, obj=None):
        return False

    @admin.display(description='Coach')
    def coach_link(self, obj):
        return obj.coach.user.get_full_name()

# --- MODEL ADMINS ---

@admin.register(ClientOfferingEnrollment)
class EnrollmentAdmin(admin.ModelAdmin):
    list_display = ('id', 'client_link', 'offering_link', 'coach_link', 'remaining_sessions', 'is_active', 'expiration_date')
    list_filter = ('is_active', 'coach', 'offering')
    search_fields = ('client__email', 'client__username', 'coach__user__email')
    readonly_fields = ('enrolled_on', 'purchase_date', 'deactivated_on')
    inlines = [SessionBookingInline]
    
    # Critical Optimization
    list_select_related = ('client', 'offering', 'coach', 'coach__user') 
    autocomplete_fields = ('client', 'coach', 'offering')

    actions = ['add_bonus_session', 'deactivate_enrollments']

    @admin.action(description='Add 1 bonus session to selected')
    def add_bonus_session(self, request, queryset):
        """
        Admin action to add one bonus session to the selected enrollments.
        This increments both total_sessions and remaining_sessions.
        """
        # Use F() expressions for a race-condition-safe update at the database level.
        updated = queryset.update(
            total_sessions=F('total_sessions') + 1,
            remaining_sessions=F('remaining_sessions') + 1
        )
        self.message_user(request, f"Added bonus session to {updated} enrollments.")

    @admin.action(description='Deactivate selected enrollments')
    def deactivate_enrollments(self, request, queryset):
        queryset.update(is_active=False)
        
    @admin.display(description='Client', ordering='client__last_name')
    def client_link(self, obj):
        url = reverse("admin:accounts_user_change", args=[obj.client.pk])
        return format_html('<a href="{}">{}</a>', url, obj.client.get_full_name())

    @admin.display(description='Offering', ordering='offering__name')
    def offering_link(self, obj):
        return obj.offering.name

    @admin.display(description='Coach', ordering='coach__user__last_name')
    def coach_link(self, obj):
        if not obj.coach:
            return "-"
        url = reverse("admin:accounts_coachprofile_change", args=[obj.coach.pk])
        return format_html('<a href="{}">{}</a>', url, obj.coach.user.get_full_name())

@admin.register(SessionBooking)
class SessionBookingAdmin(admin.ModelAdmin):
    list_display = ('id', 'start_datetime', 'get_customer', 'type_label', 'status', 'gcal_event_id')
    list_filter = ('status', 'coach', 'start_datetime', 'workshop')
    search_fields = ['client__email', 'coach__user__email', 'gcal_event_id', 'guest_email', 'guest_name']
    date_hierarchy = 'start_datetime'
    
    # Critical Optimization
    list_select_related = ('client', 'coach', 'coach__user', 'enrollment', 'workshop')
    autocomplete_fields = ('client', 'coach', 'enrollment', 'workshop')

    @admin.display(description='Customer')
    def get_customer(self, obj):
        if obj.client:
            return obj.client.get_full_name()
        return f"{obj.guest_name} ({obj.guest_email}) [Guest]"

    @admin.display(description='Booking Type')
    def type_label(self, obj):
        if obj.workshop:
            return f"Workshop: {obj.workshop.title}"
        return "1-on-1 Session"

# coaching_booking/admin.py

@admin.register(OneSessionFreeOffer)
class OneSessionFreeOfferAdmin(admin.ModelAdmin):
    # Update list_display to use 'status' instead of 'is_approved' and 'is_redeemed'
    list_display = ('client', 'coach', 'status', 'redemption_deadline', 'session_link')
    
    # Update list_filter to use 'status' instead of the old boolean fields
    list_filter = ('status', 'date_offered')
    
    search_fields = ('client__email', 'coach__user__email')
    readonly_fields = ('date_offered', 'redemption_deadline', 'session')
    
    list_select_related = ('client', 'coach', 'coach__user', 'session')
    
    actions = ['approve_offers']
    
    @admin.action(description='Approve selected offers')
    def approve_offers(self, request, queryset):
        # Update the status field to 'APPROVED' instead of setting a boolean
        updated = queryset.filter(status='PENDING').update(status='APPROVED')
        self.message_user(request, f"{updated} offers approved.")
        
    @admin.display(description='Booked Session')
    def session_link(self, obj):
        if obj.session:
            url = reverse("admin:coaching_booking_sessionbooking_change", args=[obj.session.pk])
            return format_html('<a href="{}">View Session</a>', url)
        return "Not Booked"