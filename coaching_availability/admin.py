from django.contrib import admin
from django import forms
from django.shortcuts import render, redirect
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.utils.html import format_html
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
            # Generate time choices: All hours 0-23 plus 10:30
            from datetime import time
            _times = [time(h, 0) for h in range(24)]
            _times.append(time(10, 30)) # Add specific requested half-hour
            _times.sort()
            
            TIME_CHOICES = [('', 'Full Day / None')] + [
                (t.strftime('%H:%M'), t.strftime('%I:%M %p').lstrip('0')) 
                for t in _times
            ]

            coach = forms.ModelChoiceField(queryset=User.objects.filter(coach_profile__isnull=False))
            
            # CHANGED: Use a CharField to accept multiple dates (e.g., via a JS picker or manual entry)
            selected_dates = forms.CharField(
                widget=forms.TextInput(attrs={'placeholder': 'YYYY-MM-DD, YYYY-MM-DD', 'class': 'vTextField', 'id': 'id_selected_dates'}),
                help_text=format_html(
                    "Select multiple dates using the picker. "
                    "<style>"
                    ".flatpickr-calendar {{ font-family: Roboto, sans-serif; border: none !important; box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.1), 0 4px 6px -2px rgba(0, 0, 0, 0.05) !important; }}"
                    ".flatpickr-day.selected, .flatpickr-day.startRange, .flatpickr-day.endRange, .flatpickr-day.selected.inRange, .flatpickr-day.startRange.inRange, .flatpickr-day.endRange.inRange, .flatpickr-day.selected:focus, .flatpickr-day.startRange:focus, .flatpickr-day.endRange:focus, .flatpickr-day.selected:hover, .flatpickr-day.startRange:hover, .flatpickr-day.endRange:hover, .flatpickr-day.selected.prevMonthDay, .flatpickr-day.startRange.prevMonthDay, .flatpickr-day.endRange.prevMonthDay, .flatpickr-day.selected.nextMonthDay, .flatpickr-day.startRange.nextMonthDay, .flatpickr-day.endRange.nextMonthDay {{ background: #417690 !important; border-color: #417690 !important; }}"
                    ".flatpickr-months .flatpickr-month {{ background: #417690 !important; color: #fff !important; fill: #fff !important; }}"
                    ".flatpickr-current-month .flatpickr-monthDropdown-months {{ background: #417690 !important; }}"
                    ".flatpickr-weekdays {{ background: #417690 !important; }}"
                    "span.flatpickr-weekday {{ color: #fff !important; }}"
                    "</style>"
                    "<script>"
                    "document.addEventListener('DOMContentLoaded', function() {{"
                    "  if (typeof flatpickr !== 'undefined') {{"
                    "    flatpickr('#id_selected_dates', {{ mode: 'multiple', dateFormat: 'Y-m-d', minDate: 'today' }});"
                    "  }}"
                    "}});"
                    "</script>"
                )
            )
            
            class Media:
                css = {'all': ('https://cdn.jsdelivr.net/npm/flatpickr/dist/flatpickr.min.css',)}
                js = ('https://cdn.jsdelivr.net/npm/flatpickr',)
            
            is_available = forms.BooleanField(required=False, initial=True, label="Is Available?")
            start_time = forms.ChoiceField(choices=TIME_CHOICES, required=False, label="Start Time", help_text="Leave blank for full day")
            end_time = forms.ChoiceField(choices=TIME_CHOICES, required=False, label="End Time", help_text="Leave blank for full day")

            def clean_selected_dates(self):
                data = self.cleaned_data['selected_dates']
                date_list = []
                import datetime
                try:
                    # Split by comma and strip whitespace
                    raw_dates = [d.strip() for d in data.split(',')]
                    for date_str in raw_dates:
                        if not date_str: continue
                        date_obj = datetime.datetime.strptime(date_str, '%Y-%m-%d').date()
                        if date_obj < timezone.now().date():
                            raise forms.ValidationError(f"Date {date_obj} is in the past. Please select future dates.")
                        date_list.append(date_obj)
                except ValueError:
                    raise forms.ValidationError("Ensure all dates follow the YYYY-MM-DD format.")
                return date_list

            def clean(self):
                cleaned_data = super().clean()
                start_t_str = cleaned_data.get('start_time')
                end_t_str = cleaned_data.get('end_time')
                
                start_t = None
                end_t = None

                if start_t_str:
                    from datetime import datetime
                    start_t = datetime.strptime(start_t_str, '%H:%M').time()
                    cleaned_data['start_time_obj'] = start_t
                else:
                    cleaned_data['start_time_obj'] = None

                if end_t_str:
                    from datetime import datetime
                    end_t = datetime.strptime(end_t_str, '%H:%M').time()
                    cleaned_data['end_time_obj'] = end_t
                else:
                    cleaned_data['end_time_obj'] = None

                if start_t and end_t and start_t >= end_t:
                    raise forms.ValidationError("End time must be after start time.")
                return cleaned_data

        if request.method == 'POST':
            form = BulkAddOverrideForm(request.POST)
            if form.is_valid():
                data = form.cleaned_data
                coach_user = data['coach']
                target_dates = data['selected_dates'] # This is now our list of date objects
                is_avail = data['is_available']
                s_time = data.get('start_time_obj')
                e_time = data.get('end_time_obj')

                # 1. Calculate Preview Items
                items_to_create = []
                for d in target_dates:
                    status = "Available" if is_avail else "Unavailable"
                    time_str = f"{s_time.strftime('%H:%M')} - {e_time.strftime('%H:%M')}" if s_time and e_time else "All Day"
                    items_to_create.append(f"{d} ({d.strftime('%A')}): {status} ({time_str})")

                # 2. Check for Confirmation Flag
                if request.POST.get('confirmed') == 'true':
                    created_count = 0
                    for current_date in target_dates:
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

                    self.message_user(request, f"Success: Created {created_count} overrides.")
                    return redirect('admin:coaching_availability_dateoverride_changelist')

                # 3. Render Confirmation Step
                context = {
                    **self.admin_site.each_context(request),
                    'form': form,
                    'title': "Confirm Specific Date Overrides",
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
