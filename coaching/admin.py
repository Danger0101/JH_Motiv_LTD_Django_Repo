from django.contrib import admin, messages
from django import forms
from django.forms import BaseInlineFormSet
from .models import (
    CoachingSession,
    CoachPayout,
    CoachVacationBlock,
    RecurringAvailability,
    SpecificAvailability,
    CoachOffering,
    UserOffering,
    SessionCredit,
    CreditApplication,
    RescheduleRequest,
    CoachSwapRequest,
    CancellationPolicy,
    SessionNote,
    Goal,
)


class RecurringAvailabilityFormSet(BaseInlineFormSet):
    def get_queryset(self):
        if not self.instance.pk:
            return RecurringAvailability.objects.none()

        queryset = super().get_queryset()
        existing_days = {obj.day_of_week for obj in queryset}
        
        # Add dummy instances for missing days
        for i in range(7):
            if i not in existing_days:
                dummy_instance = RecurringAvailability(coach=self.instance, day_of_week=i, is_available=False)
                # We need to add this dummy instance to the queryset without saving it
                # This is a bit tricky as Django's QuerySet is not designed for unsaved objects.
                # A common workaround is to create a list of objects and then convert it to a queryset
                # or to ensure the formset handles the creation of these forms.
                # For now, we'll rely on the formset to create these forms if they don't exist in the queryset.
                # The __init__ of the formset will handle populating initial data for these.
                pass # The __init__ will handle the creation of forms for missing days
        return queryset.order_by('day_of_week')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Collect existing forms and their day_of_week
        existing_forms_map = {form.instance.day_of_week: form for form in self.forms if form.instance.pk}
        
        # Create a new list of forms, ensuring all 7 days are present
        all_forms = []
        for i in range(7):
            if i in existing_forms_map:
                all_forms.append(existing_forms_map[i])
            else:
                # Create a new form for the missing day
                form = self._construct_form(i, initial={'day_of_week': i, 'is_available': False})
                all_forms.append(form)
        
        self.forms = all_forms


class RecurringAvailabilityInline(admin.TabularInline):
    model = RecurringAvailability
    formset = RecurringAvailabilityFormSet  # Use the custom formset to enforce 7 rows
    extra = 0                             # Do not add extra blank forms
    can_delete = False                    # Prevent deleting a day row (must be blocked)
    verbose_name_plural = 'Weekly Recurring Availability'
    
    # Use the custom method 'day_display' here instead of the raw field 'day_of_week'
    fields = ('day_display', 'start_time', 'end_time', 'is_available')
    # Set the custom method as read-only
    readonly_fields = ('day_display',)
    ordering = ('day_of_week',)

    # Define the method to fetch the human-readable day name
    def day_display(self, obj):
        """Returns the human-readable day name (e.g., 'Monday') from the model's choices."""
        # obj is the RecurringAvailability instance (saved or unsaved dummy)
        # We use the built-in Django method for choice fields
        return obj.get_day_of_week_display()
    
    day_display.short_description = 'Day' # Sets the column header text


class UserSessionCreditInline(admin.TabularInline):
    model = SessionCredit
    extra = 0
    fields = ('user_offering', 'is_taster', 'purchase_date', 'expiration_date', 'session')
    readonly_fields = ('user_offering', 'is_taster', 'purchase_date', 'expiration_date', 'session')


class UserGoalInline(admin.TabularInline):
    model = Goal
    extra = 0
    fields = ('title', 'status', 'due_date')

class PurchasedUserOfferingInline(admin.TabularInline):
    model = UserOffering
    extra = 0
    fields = ('offering', 'purchase_date', 'start_date', 'end_date')
    readonly_fields = ('offering', 'purchase_date', 'start_date', 'end_date')


class UserCreditApplicationInline(admin.TabularInline):
    model = CreditApplication
    extra = 0
    fields = ('is_taster', 'status', 'created_at', 'approved_by')
    readonly_fields = ('is_taster', 'status', 'created_at', 'approved_by')


class SpecificAvailabilityInline(admin.TabularInline):
    model = SpecificAvailability
    extra = 0
    fields = ('date', 'start_time', 'end_time', 'is_available')


class CoachVacationBlockInline(admin.TabularInline):
    model = CoachVacationBlock
    extra = 0
    fields = ('start_date', 'end_date', 'reason', 'override_allowed')


class CoachOfferingInline(admin.TabularInline):
    model = CoachOffering
    extra = 0
    fields = ('name', 'price', 'credits_granted', 'duration_months', 'is_active')
    prepopulated_fields = {'slug': ('name',)}


class CoachPayoutInline(admin.TabularInline):
    model = CoachPayout
    extra = 0
    fields = ('amount', 'status', 'created_at', 'paid_at')
    readonly_fields = ('amount', 'status', 'created_at', 'paid_at')


class CoachingSessionClientInline(admin.TabularInline):
    model = CoachingSession
    fk_name = 'client'
    extra = 0
    fields = ('service_name', 'coach', 'start_time', 'status')
    readonly_fields = ('service_name', 'coach', 'start_time', 'status')


class CoachingSessionCoachInline(admin.TabularInline):
    model = CoachingSession
    fk_name = 'coach'
    extra = 0
    fields = ('service_name', 'client', 'start_time', 'status')
    readonly_fields = ('service_name', 'client', 'start_time', 'status')


class CoachSessionNoteInline(admin.TabularInline):


    model = SessionNote


    extra = 0


    fields = ('session', 'note', 'created_at')


    readonly_fields = ('session', 'note', 'created_at')








@admin.register(CoachOffering)


class CoachOfferingAdmin(admin.ModelAdmin):


    list_display = ('name', 'display_coaches', 'price', 'credits_granted', 'duration_months', 'is_active')


    list_filter = ('coaches', 'is_active')


    search_fields = ('name', 'description')


    prepopulated_fields = {'slug': ('name',)}


    filter_horizontal = ('coaches',)





    def display_coaches(self, obj):


        return ", ".join([coach.username for coach in obj.coaches.all()])


    display_coaches.short_description = 'Coaches'








@admin.register(RescheduleRequest)


class RescheduleRequestAdmin(admin.ModelAdmin):


    list_display = ('session', 'status', 'created_at')


    list_filter = ('status',)





@admin.register(CoachSwapRequest)


class CoachSwapRequestAdmin(admin.ModelAdmin):


    list_display = ('session', 'initiating_coach', 'receiving_coach', 'status')


    list_filter = ('status', 'initiating_coach', 'receiving_coach')





@admin.register(CancellationPolicy)


class CancellationPolicyAdmin(admin.ModelAdmin):


    list_display = ('user_type', 'hours_before_session', 'refund_percentage')


    list_filter = ('user_type',)







@admin.register(SessionNote)
class SessionNoteAdmin(admin.ModelAdmin):
    list_display = ('session', 'coach', 'created_at')
    search_fields = ('coach__username', 'session__id')
    date_hierarchy = 'created_at'

