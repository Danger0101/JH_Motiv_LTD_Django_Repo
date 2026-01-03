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
            # Generate time choices: All hours 0-23 plus 10:30
            from datetime import time
            _times = [time(h, 0) for h in range(24)]
            _times.append(time(10, 30)) # Add specific requested half-hour
            _times.sort()
            
            TIME_CHOICES = [
                (t.strftime('%H:%M'), t.strftime('%I:%M %p').lstrip('0')) 
                for t in _times
            ]

            # Only show users who are coaches
            coach = forms.ModelChoiceField(queryset=User.objects.filter(coach_profile__isnull=False))
            day_of_week = forms.MultipleChoiceField(
                choices=CoachAvailability.DAYS_OF_WEEK,
                widget=forms.CheckboxSelectMultiple
            )
            start_time = forms.ChoiceField(choices=TIME_CHOICES, label="Start Time")
            end_time = forms.ChoiceField(choices=TIME_CHOICES, label="End Time")

            def clean(self):
                cleaned_data = super().clean()
                start_t_str = cleaned_data.get('start_time')
                end_t_str = cleaned_data.get('end_time')
                
                if start_t_str and end_t_str:
                    from datetime import datetime
                    start_t = datetime.strptime(start_t_str, '%H:%M').time()
                    end_t = datetime.strptime(end_t_str, '%H:%M').time()
                    
                    if start_t >= end_t:
                        raise forms.ValidationError("End time must be after start time.")
                    
                    # Pass the actual time objects to the view
                    cleaned_data['start_time_obj'] = start_t
                    cleaned_data['end_time_obj'] = end_t

                return cleaned_data

        if request.method == 'POST':
            form = BulkAddForm(request.POST)
            if form.is_valid():
                data = form.cleaned_data
                coach_user = data['coach']
                days = data['day_of_week']
                
                # Use the time objects processed in clean()
                start_t = data['start_time_obj']
                end_t = data['end_time_obj']
                
                # 1. Calculate Preview Items
                items_to_create = []
                for day_str in days:
                    day = int(day_str)
                    if not CoachAvailability.objects.filter(
                        coach=coach_user, day_of_week=day, start_time=start_t, end_time=end_t
                    ).exists():
                        day_name = dict(CoachAvailability.DAYS_OF_WEEK)[day]
                        items_to_create.append(f"{day_name}: {start_t.strftime('%H:%M')} - {end_t.strftime('%H:%M')}")

                # 2. Check for Confirmation Flag
                if request.POST.get('confirmed') == 'true':
                    created_count = 0
                    for day_str in days:
                        day = int(day_str)
                        if not CoachAvailability.objects.filter(
                            coach=coach_user, day_of_week=day, start_time=start_t, end_time=end_t
                        ).exists():
                            CoachAvailability.objects.create(
                                coach=coach_user, day_of_week=day, start_time=start_t, end_time=end_t
                            )
                            created_count += 1
                    
                    self.message_user(request, f"Success: Created {created_count} availability slots for {coach_user}.")
                    return redirect('admin:coaching_availability_coachavailability_changelist')

                # 3. Render Confirmation Step
                context = {
                    **self.admin_site.each_context(request),
                    'form': form,
                    'title': "Confirm Bulk Add",
                    'items_to_create': items_to_create,
                    'confirm_mode': True,
                }
                return render(request, "coaching_booking/bulk_add.html", context)
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

            def clean(self):
                cleaned_data = super().clean()
                start_t = cleaned_data.get('start_time')
                end_t = cleaned_data.get('end_time')
                if start_t and end_t and start_t >= end_t:
                    raise forms.ValidationError("End time must be after start time.")
                return cleaned_data

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
                
                # 1. Calculate Preview Items
                items_to_create = []
                temp_date = current_date
                while temp_date <= end_date:
                    status = "Available" if is_avail else "Unavailable"
                    time_str = f"{s_time.strftime('%H:%M')} - {e_time.strftime('%H:%M')}" if s_time and e_time else "All Day"
                    items_to_create.append(f"{temp_date}: {status} ({time_str})")
                    temp_date += timedelta(days=1)

                # 2. Check for Confirmation Flag
                if request.POST.get('confirmed') == 'true':
                    created_count = 0
                    while current_date <= end_date:
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

                # 3. Render Confirmation Step
                context = {
                    **self.admin_site.each_context(request),
                    'form': form,
                    'title': "Confirm Date Overrides",
                    'items_to_create': items_to_create,
                    'confirm_mode': True,
                }
                return render(request, "coaching_booking/bulk_add.html", context)
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
