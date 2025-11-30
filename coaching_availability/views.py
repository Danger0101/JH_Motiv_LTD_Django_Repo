from django.shortcuts import render, redirect
from django.views import View
from django.db import transaction
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import HttpResponse # Ensure HttpResponse is imported
from collections import defaultdict # Import defaultdict
from .forms import DateOverrideForm, CoachVacationForm, BaseWeeklyScheduleFormSet, DAYS_OF_WEEK
from .models import CoachAvailability, DateOverride, CoachVacation


class SetRecurringScheduleView(LoginRequiredMixin, View):
    def post(self, request, *args, **kwargs):
        formset = BaseWeeklyScheduleFormSet(request.POST, request.FILES)
        if formset.is_valid():
            with transaction.atomic():
                CoachAvailability.objects.filter(coach=request.user).delete()
                for form in formset:
                    cleaned_data = form.cleaned_data
                    start_time = cleaned_data.get('start_time')
                    end_time = cleaned_data.get('end_time')
                    day_of_week = cleaned_data.get('day_of_week')

                    if start_time and end_time:
                        CoachAvailability.objects.create(
                            coach=request.user,
                            day_of_week=day_of_week,
                            start_time=start_time,
                            end_time=end_time
                        )
            # Handle HTMX request: re-render partial or return empty response
            if request.htmx:
                # Re-fetch initial data to render the formset correctly
                from collections import defaultdict
                from coaching_availability.forms import DAYS_OF_WEEK

                initial_data = []
                availabilities = CoachAvailability.objects.filter(coach=request.user).order_by('day_of_week', 'start_time')
                
                existing_data = defaultdict(list)
                for availability in availabilities:
                    existing_data[availability.day_of_week].append({
                        'start_time': availability.start_time,
                        'end_time': availability.end_time,
                    })

                for day, day_name in DAYS_OF_WEEK:
                    day_availabilities = existing_data[day]
                    if day_availabilities:
                        for availability in day_availabilities:
                            initial_data.append({
                                'day_of_week': day,
                                'start_time': availability['start_time'],
                                'end_time': availability['end_time'],
                            })
                    else:
                        initial_data.append({'day_of_week': day, 'start_time': None, 'end_time': None})
                
                context = {
                    'weekly_schedule_formset': BaseWeeklyScheduleFormSet(initial=initial_data),
                    'days_of_week': DAYS_OF_WEEK,
                    'override_form': DateOverrideForm(), 
                    'vacation_form': CoachVacationForm(),
                    'google_calendar_connected': False, 
                }
                return render(request, 'accounts/partials/_availability.html', context)
            else:
                return redirect('accounts:account_profile')
        
        # If form is not valid and it's an HTMX request, re-render the partial with errors
        if request.htmx:
            from collections import defaultdict
            from coaching_availability.forms import DAYS_OF_WEEK
            
            context = {
                'weekly_schedule_formset': formset, 
                'days_of_week': DAYS_OF_WEEK,
                'override_form': DateOverrideForm(), 
                'vacation_form': CoachVacationForm(),
                'google_calendar_connected': False, 
            }
            return render(request, 'accounts/partials/_availability.html', context)
        else:
            # If form is not valid and not HTMX, redirect back to profile, losing errors
            return redirect('accounts:account_profile')


class SetDateOverrideView(LoginRequiredMixin, View):
    def post(self, request, *args, **kwargs):
        form = DateOverrideForm(request.POST)
        if form.is_valid():
            date_override, created = DateOverride.objects.update_or_create(
                coach=request.user,
                date=form.cleaned_data['date'],
                defaults=form.cleaned_data
            )
            return redirect('account:account_profile')
        return render(request, 'your-template.html', {'form': form})


class ManageVacationView(LoginRequiredMixin, View):
    def post(self, request, *args, **kwargs):
        form = CoachVacationForm(request.POST)
        if form.is_valid():
            with transaction.atomic():
                vacation = form.save(commit=False)
                vacation.coach = request.user
                vacation.save()
                
                from coaching_booking.models import SessionBooking
                conflicting_bookings = SessionBooking.objects.filter(
                    coach=request.user,
                    start_time__date__range=(
                        vacation.start_date,
                        vacation.end_date
                    ),
                    status='confirmed'  # Assuming a 'confirmed' status
                )

                if form.cleaned_data['existing_booking_handling'] == 'cancel':
                    conflicting_bookings.update(status='cancelled')
                elif form.cleaned_data['existing_booking_handling'] == 'reschedule':
                    conflicting_bookings.update(status='needs_reschedule')
                # 'keep' requires no action

            return redirect('account:account_profile')
        return render(request, 'your-template.html', {'form': form})

