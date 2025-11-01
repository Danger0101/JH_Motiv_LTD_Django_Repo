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


from django.forms import ModelForm

class RecurringAvailabilityForm(ModelForm):
    class Meta:
        model = RecurringAvailability
        fields = '__all__'

class RecurringAvailabilityFormSet(BaseInlineFormSet):
    def get_queryset(self):
        if not self.instance.pk:
            # For a new coach, return an empty queryset, forms will be created with initial data
            return super().get_queryset().none()

        # For an existing coach, get existing availability
        queryset = super().get_queryset().filter(coach=self.instance).order_by('day_of_week')
        existing_days = {obj.day_of_week for obj in queryset}

        # Create dummy instances for missing days
        dummy_instances = []
        for i in range(7):
            if i not in existing_days:
                dummy_instances.append(
                    RecurringAvailability(coach=self.instance, day_of_week=i, is_available=False)
                )
        
        # Combine existing and dummy instances.
        # This will be a list, not a QuerySet, but the formset can handle it.
        # The formset will then create forms for these instances.
        return list(queryset) + dummy_instances

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Ensure there are always 7 forms, even if the queryset was empty
        if not self.forms:
            for i in range(7):
                # Create a new form for each day with initial data
                form = self.empty_form.__class__(
                    initial={'day_of_week': i, 'is_available': False},
                    prefix=f'{self.prefix}-{i}'
                )
                form.instance.day_of_week = i # Set day_of_week on instance for day_display
                self.forms.append(form)
        
        # Sort forms by day_of_week for consistent display
        self.forms.sort(key=lambda form: form.instance.day_of_week)



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
    fk_name = 'user'
    model = CreditApplication
    extra = 0
    can_delete = False
    verbose_name_plural = 'Credit Applications'
    fields = ('is_taster', 'status', 'created_at', 'approved_by', 'denied_by')
    readonly_fields = ('is_taster', 'status', 'created_at')
    autocomplete_fields = ('user', 'approved_by', 'denied_by')


class SpecificAvailabilityInline(admin.TabularInline):
    model = SpecificAvailability
    extra = 0
    fields = ('date', 'start_time', 'end_time', 'is_available', 'coach')
    autocomplete_fields = ('coach',)


class CoachVacationBlockInline(admin.TabularInline):
    model = CoachVacationBlock
    extra = 0
    fields = ('start_date', 'end_date', 'reason', 'override_allowed', 'coach')
    autocomplete_fields = ('coach',)


class CoachOfferingInline(admin.TabularInline):
    model = CoachOffering
    extra = 0
    fields = ('name', 'price', 'credits_granted', 'duration_months', 'is_active')
    prepopulated_fields = {'slug': ('name',)}


class CoachPayoutInline(admin.TabularInline):
    model = CoachPayout
    extra = 0
    fields = ('amount', 'status', 'created_at', 'paid_at', 'coach')
    readonly_fields = ('amount', 'status', 'created_at', 'paid_at')
    autocomplete_fields = ('coach',)


class CoachingSessionClientInline(admin.TabularInline):
    model = CoachingSession
    fk_name = 'client'
    extra = 0
    fields = ('service_name', 'coach', 'start_time', 'status', 'client')
    readonly_fields = ('service_name', 'start_time', 'status')
    autocomplete_fields = ('coach', 'client')


class CoachingSessionCoachInline(admin.TabularInline):
    model = CoachingSession
    fk_name = 'coach'
    extra = 0
    fields = ('service_name', 'client', 'start_time', 'status', 'coach')
    readonly_fields = ('service_name', 'start_time', 'status')
    autocomplete_fields = ('client', 'coach')


class CoachSessionNoteInline(admin.TabularInline):


    model = SessionNote


    extra = 0


    fields = ('session', 'note', 'created_at', 'coach')


    readonly_fields = ('session', 'note', 'created_at')


    autocomplete_fields = ('coach',)








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




















@admin.register(CancellationPolicy)


class CancellationPolicyAdmin(admin.ModelAdmin):


    list_display = ('user_type', 'hours_before_session', 'refund_percentage')


    list_filter = ('user_type',)







@admin.register(SessionNote)
class SessionNoteAdmin(admin.ModelAdmin):
    list_display = ('session', 'coach', 'created_at')
    search_fields = ('coach__username', 'session__id')
    date_hierarchy = 'created_at'
    autocomplete_fields = ('coach', 'session')
    list_select_related = ('coach', 'session')

@admin.register(CoachingSession)
class CoachingSessionAdmin(admin.ModelAdmin):
    list_display = ('service_name', 'coach', 'client', 'start_time', 'status')
    list_filter = ('status', 'coach', 'client')
    search_fields = ('service_name', 'coach__username', 'client__username')
    autocomplete_fields = ('coach', 'client')
    list_select_related = ('coach', 'client')

