from django.contrib import admin
from .models import Offering, Workshop

# --- INLINES ---

class CoachAssignmentInline(admin.TabularInline):
    model = Offering.coaches.through
    extra = 1
    verbose_name = "Coach Assignment"
    verbose_name_plural = "Coach Assignments"
    autocomplete_fields = ('coachprofile',) # Requires search_fields on CoachProfileAdmin

# --- MODEL ADMINS ---

@admin.register(Offering)
class OfferingAdmin(admin.ModelAdmin):
    list_display = ('name', 'duration_display', 'price', 'active_status', 'coach_count')
    list_filter = ('active_status', 'duration_type', 'is_whole_day')
    search_fields = ['name', 'description']
    readonly_fields = ('slug', 'created_at', 'updated_at', 'created_by', 'updated_by')    
    inlines = [CoachAssignmentInline]
    exclude = ('coaches',) # Manage via inline to prevent massive multiselect box loading

    def get_queryset(self, request):
        return super().get_queryset(request).prefetch_related('coaches')

    @admin.display(description='Duration')
    def duration_display(self, obj):
        return obj.display_length

    @admin.display(description='Coaches Assigned')
    def coach_count(self, obj): # Renamed from 'Coaches' to 'Coaches Assigned'
        return obj.coaches.count()

    fieldsets = (
        ('Service Details', {
            'fields': ('name', 'slug', 'description', 'active_status')
        }),
        ('Pricing & Structure', {
            'fields': ('price', 'duration_type', 'total_length_units', 'session_length_minutes', 'total_number_of_sessions', 'is_whole_day')
        }),
        ('Financials', {
            'fields': ('coach_revenue_share', 'referral_commission_type', 'referral_commission_value'),
            'classes': ('collapse',),
        }),
        ('Audit', {
            'fields': ('created_by', 'created_at', 'updated_by', 'updated_at'),
            'classes': ('collapse',),
        }),
    )

    def save_model(self, request, obj, form, change):
        if not change:
            obj.created_by = request.user
        obj.updated_by = request.user
        super().save_model(request, obj, form, change)

@admin.register(Workshop)
class WorkshopAdmin(admin.ModelAdmin):
    list_display = ('name', 'coach_link', 'date', 'time_range', 'booking_capacity_status', 'active_status')
    list_filter = ('active_status', 'is_free', 'date', 'coach')
    search_fields = ('name', 'coach__user__email', 'coach__user__last_name')
    readonly_fields = ('slug', 'created_at', 'updated_at', 'created_by', 'updated_by')
    autocomplete_fields = ('coach',) # Critical for usability if you have many coaches
    list_select_related = ('coach', 'coach__user')    
    date_hierarchy = 'date'

    @admin.display(description='Coach', ordering='coach__user__last_name')
    def coach_link(self, obj):
        return obj.coach.user.get_full_name()

    @admin.display(description='Time')
    def time_range(self, obj):
        return f"{obj.start_time.strftime('%H:%M')} - {obj.end_time.strftime('%H:%M')}"

    @admin.display(description='Bookings / Cap')
    def booking_capacity_status(self, obj):
        # This uses the related_name='bookings' from SessionBooking model
        count = obj.bookings.filter(status='BOOKED').count()
        return f"{count} / {obj.total_attendees}"

    fieldsets = (
        ('Workshop Info', {
            'fields': ('name', 'slug', 'description', 'coach')
        }),
        ('Schedule', {
            'fields': ('date', 'start_time', 'end_time')
        }),
        ('Capacity & Pricing', {
            'fields': ('price', 'is_free', 'total_attendees', 'active_status')
        }),
        ('Audit', {
            'fields': ('created_by', 'created_at'),
            'classes': ('collapse',),
        }),
    )