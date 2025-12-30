import csv
from datetime import timedelta
from django.contrib import admin
from django.contrib import messages
from django.http import HttpResponse
from .models import (
    ClientOfferingEnrollment, SessionBooking, SessionCoverageRequest, 
    OneSessionFreeOffer, CoachBusySlot, CoachReview
)

@admin.register(ClientOfferingEnrollment)
class ClientOfferingEnrollmentAdmin(admin.ModelAdmin):
    list_display = ('client', 'offering', 'coach', 'remaining_sessions', 'is_active', 'enrolled_on', 'completed_on')
    list_filter = ('is_active', 'offering', 'coach')
    search_fields = ('client__email', 'client__first_name', 'client__last_name')
    readonly_fields = ('enrolled_on', 'purchase_date', 'completed_on')
    actions = ['extend_expiration_30_days']

    @admin.action(description='Extend expiration by 30 days')
    def extend_expiration_30_days(self, request, queryset):
        updated = 0
        for enrollment in queryset:
            if enrollment.expiration_date:
                enrollment.expiration_date += timedelta(days=30)
                enrollment.save()
                updated += 1
        self.message_user(request, f"Extended expiration for {updated} enrollments.", messages.SUCCESS)

@admin.register(SessionBooking)
class SessionBookingAdmin(admin.ModelAdmin):
    list_display = ('client', 'coach', 'start_datetime', 'status', 'attendance', 'offering', 'workshop')
    list_filter = ('status', 'attendance', 'start_datetime', 'coach')
    search_fields = ('client__email', 'coach__user__email')
    date_hierarchy = 'start_datetime'
    actions = ['export_as_csv']

    @admin.action(description='Export Selected Bookings to CSV')
    def export_as_csv(self, request, queryset):
        meta = self.model._meta
        field_names = ['id', 'client', 'coach', 'offering', 'start_datetime', 'end_datetime', 'status', 'attendance', 'amount_paid']
        
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename={meta.verbose_name_plural}.csv'
        writer = csv.writer(response)

        writer.writerow(field_names)
        for obj in queryset:
            row = []
            for field in field_names:
                val = getattr(obj, field)
                if field == 'client' and val:
                    val = val.email
                elif field == 'coach' and val:
                    val = val.user.get_full_name()
                elif field == 'offering' and val:
                    val = val.name
                elif field in ['start_datetime', 'end_datetime'] and val:
                    val = val.strftime('%Y-%m-%d %H:%M')
                row.append(str(val) if val is not None else '')
            writer.writerow(row)

        return response

@admin.register(CoachReview)
class CoachReviewAdmin(admin.ModelAdmin):
    list_display = ('coach', 'client', 'weighted_average', 'status', 'created_at')
    list_filter = ('status', 'created_at', 'coach')
    search_fields = ('coach__user__email', 'client__email', 'comment')
    readonly_fields = ('created_at', 'updated_at', 'weighted_average')
    
    actions = ['approve_reviews', 'reject_reviews']

    @admin.action(description='Mark selected reviews as Published')
    def approve_reviews(self, request, queryset):
        queryset.update(status='PUBLISHED')

    @admin.action(description='Mark selected reviews as Rejected')
    def reject_reviews(self, request, queryset):
        queryset.update(status='REJECTED')

@admin.register(OneSessionFreeOffer)
class OneSessionFreeOfferAdmin(admin.ModelAdmin):
    list_display = ('client', 'coach', 'status', 'date_offered', 'redemption_deadline')
    list_filter = ('status', 'coach')

@admin.register(SessionCoverageRequest)
class SessionCoverageRequestAdmin(admin.ModelAdmin):
    list_display = ('requesting_coach', 'target_coach', 'session', 'status', 'created_at')
    list_filter = ('status',)

@admin.register(CoachBusySlot)
class CoachBusySlotAdmin(admin.ModelAdmin):
    list_display = ('coach', 'start_time', 'end_time', 'source')
    list_filter = ('coach', 'source')