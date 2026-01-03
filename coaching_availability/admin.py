from django.contrib import admin
from django import forms
from django.shortcuts import render, redirect
from django.utils import timezone
from django.contrib.auth import get_user_model
from .models import CoachAvailability, DateOverride, CoachVacation

User = get_user_model()

@admin.register(CoachAvailability)
class CoachAvailabilityAdmin(admin.ModelAdmin):
    list_display = ('coach_name', 'day_name', 'time_range')
    list_filter = ('day_of_week', 'coach')
    ordering = ('coach', 'day_of_week', 'start_time')
    list_select_related = ('coach',)

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "coach":
            kwargs["queryset"] = User.objects.filter(coach_profile__isnull=False)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    @admin.display(description='Coach', ordering='coach__username')
    def coach_name(self, obj):
        return obj.coach.get_full_name() or obj.coach.username

    @admin.display(description='Day', ordering='day_of_week')
    def day_name(self, obj):
        return obj.get_day_of_week_display()

    @admin.display(description='Time Slot')
    def time_range(self, obj):
        return f"{obj.start_time.strftime('%H:%M')} - {obj.end_time.strftime('%H:%M')}"

    # --- BULK ADD LOGIC ---
    def get_urls(self):
        from django.urls import path
        urls = super().get_urls()
        custom_urls = [
            path('bulk-add/', self.admin_site.admin_view(self.bulk_add_view), name='coaching_availability_bulk_add'),
        ]
        return custom_urls + urls

    def bulk_add_view(self, request):
        
        class BulkAddForm(forms.Form):
            # Only show users who are coaches
            coach = forms.ModelChoiceField(queryset=User.objects.filter(coach_profile__isnull=False))
            day_of_week = forms.MultipleChoiceField(
                choices=CoachAvailability.DAYS_OF_WEEK,
                widget=forms.CheckboxSelectMultiple
            )
            start_hour = forms.IntegerField(min_value=0, max_value=23, help_text="Start Hour (0-23)")
            end_hour = forms.IntegerField(min_value=0, max_value=23, help_text="End Hour (0-23)")

        if request.method == 'POST':
            form = BulkAddForm(request.POST)
            if form.is_valid():
                data = form.cleaned_data
                coach_user = data['coach']
                days = data['day_of_week']
                start_h = data['start_hour']
                end_h = data['end_hour']
                
                from datetime import time
                start_t = time(start_h, 0)
                end_t = time(end_h, 0)
                
                created_count = 0
                for day_str in days:
                    day = int(day_str)
                    # Check for duplicates before creating
                    exists = CoachAvailability.objects.filter(
                        coach=coach_user,
                        day_of_week=day,
                        start_time=start_t,
                        end_time=end_t
                    ).exists()

                    if not exists:
                        CoachAvailability.objects.create(
                            coach=coach_user,
                            day_of_week=day,
                            start_time=start_t,
                            end_time=end_t
                        )
                        created_count += 1

                self.message_user(request, f"Success: Created {created_count} availability slots for {coach_user}.")

                return redirect('admin:coaching_availability_coachavailability_changelist')
        else:
            form = BulkAddForm()

        context = {
            **self.admin_site.each_context(request),
            'form': form,
            'title': "Bulk Add Availability",
        }
        return render(request, "coaching_booking/bulk_add.html", context)

@admin.register(DateOverride)
class DateOverrideAdmin(admin.ModelAdmin):
    list_display = ('coach', 'date', 'status_display', 'time_range')
    list_filter = ('is_available', 'date', 'coach')
    date_hierarchy = 'date'
    list_select_related = ('coach',)

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "coach":
            kwargs["queryset"] = User.objects.filter(coach_profile__isnull=False)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    def get_urls(self):
        from django.urls import path
        urls = super().get_urls()
        custom_urls = [
            path('bulk-add/', self.admin_site.admin_view(self.bulk_add_view), name='date_override_bulk_add'),
        ]
        return custom_urls + urls

    def bulk_add_view(self, request):
        class BulkAddOverrideForm(forms.Form):
            coach = forms.ModelChoiceField(queryset=User.objects.filter(coach_profile__isnull=False))
            start_date = forms.DateField(widget=forms.DateInput(attrs={'type': 'date'}))
            end_date = forms.DateField(widget=forms.DateInput(attrs={'type': 'date'}))
            is_available = forms.BooleanField(required=False, initial=True, label="Is Available?")
            start_time = forms.TimeField(required=False, widget=forms.TimeInput(attrs={'type': 'time'}), help_text="Leave blank for full day")
            end_time = forms.TimeField(required=False, widget=forms.TimeInput(attrs={'type': 'time'}), help_text="Leave blank for full day")

        if request.method == 'POST':
            form = BulkAddOverrideForm(request.POST)
            if form.is_valid():
                data = form.cleaned_data
                coach_user = data['coach']
                current_date = data['start_date']
                end_date = data['end_date']
                is_avail = data['is_available']
                s_time = data['start_time']
                e_time = data['end_time']

                from datetime import timedelta
                
                created_count = 0
                while current_date <= end_date:
                    # Update or create to avoid duplicates
                    DateOverride.objects.update_or_create(
                        coach=coach_user,
                        date=current_date,
                        defaults={
                            'is_available': is_avail,
                            'start_time': s_time,
                            'end_time': e_time
                        }
                    )
                    created_count += 1
                    current_date += timedelta(days=1)

                self.message_user(request, f"Success: Created/Updated {created_count} overrides for {coach_user}.")
                return redirect('admin:coaching_availability_dateoverride_changelist')
        else:
            form = BulkAddOverrideForm()

        context = {
            **self.admin_site.each_context(request),
            'form': form,
            'title': "Bulk Add Date Overrides",
        }
        # Reusing the same template structure as availability bulk add
        return render(request, "coaching_booking/bulk_add.html", context)

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

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "coach":
            kwargs["queryset"] = User.objects.filter(coach_profile__isnull=False)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)
