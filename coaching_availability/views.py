from django.shortcuts import render, redirect
from django.views import View
from django.db import transaction
from django.contrib.auth.mixins import LoginRequiredMixin
from .forms import CoachAvailabilityForm, DateOverrideForm, CoachVacationForm
from .models import CoachAvailability, DateOverride, CoachVacation


class SetRecurringScheduleView(LoginRequiredMixin, View):
    def post(self, request, *args, **kwargs):
        form = CoachAvailabilityForm(request.POST)
        if form.is_valid():
            with transaction.atomic():
                CoachAvailability.objects.filter(coach=request.user).delete()
                # This is a simplified example. In a real application, you'd
                # likely handle multiple day/time slots in a more complex form.
                availability = form.save(commit=False)
                availability.coach = request.user
                availability.save()
            return redirect('account:account_profile')
        return render(request, 'your-template.html', {'form': form})


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

