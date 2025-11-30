from django.shortcuts import render, redirect
from django.views import View
from django.db import transaction
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import HttpResponse # Ensure HttpResponse is imported
from collections import defaultdict # Import defaultdict
from django.forms import modelformset_factory # Import modelformset_factory
from .forms import DateOverrideForm, CoachVacationForm, WeeklyScheduleForm # Removed BaseWeeklyScheduleFormSet
from .models import CoachAvailability, DateOverride, CoachVacation
from .utils import get_weekly_schedule_context


class SetRecurringScheduleView(LoginRequiredMixin, View):
    def get(self, request, *args, **kwargs):
        WeeklyScheduleFormSet = modelformset_factory(
            CoachAvailability,
            form=WeeklyScheduleForm,
            extra=0,
            can_delete=False
        )
        queryset = CoachAvailability.objects.filter(
            coach=request.user.coachprofile
        ).order_by('day_of_week')
        weekly_schedule_formset = WeeklyScheduleFormSet(queryset=queryset)
        context = get_weekly_schedule_context(request.user)
        context['weekly_schedule_formset'] = weekly_schedule_formset
        return render(request, 'accounts/partials/_availability.html', context)


    def post(self, request, *args, **kwargs):
        WeeklyScheduleFormSet = modelformset_factory(
            CoachAvailability,
            form=WeeklyScheduleForm,
            extra=0,
            can_delete=False
        )
        queryset = CoachAvailability.objects.filter(
            coach=request.user.coachprofile
        ).order_by('day_of_week')
        weekly_schedule_formset = WeeklyScheduleFormSet(request.POST, queryset=queryset)
        if weekly_schedule_formset.is_valid():
            with transaction.atomic():
                instances = weekly_schedule_formset.save(commit=False)
                for instance in instances:
                    instance.coach = request.user.coachprofile
                    instance.save()
            # Handle HTMX request: re-render partial or return empty response
            if request.htmx:
                context = get_weekly_schedule_context(request.user)
                return render(request, 'accounts/partials/_availability.html', context)
            else:
                return redirect('accounts:account_profile')
        
        # If form is not valid and it's an HTMX request, re-render the partial with errors
        if request.htmx:
            context = get_weekly_schedule_context(request.user)
            context['weekly_schedule_formset'] = weekly_schedule_formset # Pass the formset with errors
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

