from datetime import time # Import time for default slot times
from django.shortcuts import render, redirect # Ensure redirect is imported
from django.http import HttpResponseRedirect # Ensure HttpResponseRedirect is imported
from django.db import transaction
from django.forms import modelformset_factory
from django.contrib.auth.decorators import login_required
from .forms import DateOverrideForm, CoachVacationForm, WeeklyScheduleForm
from .models import CoachAvailability, DateOverride, CoachVacation, settings

@login_required
def profile_availability(request):
    # Ensure the user is a coach to access this view
    if not hasattr(request.user, 'coach_profile'):
        # Redirect non-coaches or show an error
        # For HTMX, you might want to render an error partial or simply do nothing
        return render(request, 'accounts/partials/_availability.html', {
            'error': 'You must be a coach to manage availability.'
        })

    WeeklyScheduleFormSet = modelformset_factory(
        CoachAvailability,
        form=WeeklyScheduleForm,
        extra=0,
        can_delete=True # Allow deletion of existing time slots
    )

    # Handle POST requests
    if request.method == 'POST':
        if 'add_slot_for_day' in request.POST:
            day_code = int(request.POST.get('add_slot_for_day'))
            CoachAvailability.objects.create(
                coach=request.user,
                day_of_week=day_code,
                start_time=time(9, 0),  # Default start time
                end_time=time(17, 0)   # Default end time
            )
            # For HTMX, re-render the partial
            return HttpResponseRedirect(request.path) # Redirect to GET to re-render the entire availability block

        elif 'delete_slot' in request.POST:
            slot_id = request.POST.get('delete_slot')
            try:
                CoachAvailability.objects.filter(pk=slot_id, coach=request.user).delete()
            except CoachAvailability.DoesNotExist:
                pass # Already deleted or not found
            # For HTMX, re-render the partial
            return HttpResponseRedirect(request.path) # Redirect to GET to re-render the entire availability block

        else: # Process formset submission for updates/deletions
            queryset = CoachAvailability.objects.filter(coach=request.user).order_by('day_of_week', 'start_time')
            formset = WeeklyScheduleFormSet(request.POST, queryset=queryset)
            if formset.is_valid():
                with transaction.atomic():
                    # Save existing instances and handle deletions
                    formset.save()
                    # Any new instances added via 'add_slot_for_day' would not be handled here,
                    # as 'extra' is 0 for this formset. New instances are created directly above.
                # For HTMX, re-render the partial with updated data
                return HttpResponseRedirect(request.path) # Redirect to GET to re-render the entire availability block
            else:
                # If formset is invalid, re-render with errors
                context = {
                    'weekly_schedule_formset': formset, # Formset with errors
                    'vacation_form': CoachVacationForm(),
                    'override_form': DateOverrideForm(),
                    'active_tab': 'availability',
                    'days_of_week': CoachAvailability.DAYS_OF_WEEK,
                }
                return render(request, 'accounts/partials/_availability.html', context)

    # Handle GET requests
    queryset = CoachAvailability.objects.filter(coach=request.user).order_by('day_of_week', 'start_time')
    weekly_schedule_formset = WeeklyScheduleFormSet(queryset=queryset)

    context = {
        'weekly_schedule_formset': weekly_schedule_formset,
        'vacation_form': CoachVacationForm(),
        'override_form': DateOverrideForm(),
        'active_tab': 'availability',
        'days_of_week': CoachAvailability.DAYS_OF_WEEK,
    }
    return render(request, 'accounts/partials/_availability.html', context)

@login_required
def profile_override(request):
    """
    Renders the list of future Date Overrides and the form to add a new one.
    Refreshed via HTMX when tabs are clicked or items are modified.
    """
    if not hasattr(request.user, 'coach_profile'):
        return render(request, 'coaching_availability/partials/_one_off_availability.html', {'error': 'Unauthorized'})

    overrides = DateOverride.objects.filter(
        coach=request.user, 
        date__gte=timezone.now().date()
    ).order_by('date')
    
    context = {
        'form': DateOverrideForm(),
        'overrides': overrides
    }
    return render(request, 'coaching_availability/partials/_one_off_availability.html', context)


@login_required
def profile_vacation(request):
    """
    Renders the list of future Vacations and the form to add a new one.
    Refreshed via HTMX when tabs are clicked or items are modified.
    """
    if not hasattr(request.user, 'coach_profile'):
        return render(request, 'coaching_availability/partials/_vacation_management.html', {'error': 'Unauthorized'})

    vacations = CoachVacation.objects.filter(
        coach=request.user, 
        end_date__gte=timezone.now().date()
    ).order_by('start_date')
    
    context = {
        'form': CoachVacationForm(),
        'vacations': vacations
    }
    return render(request, 'coaching_availability/partials/_vacation_management.html', context)


@login_required
@require_POST
def save_date_override(request):
    """
    Handles HTMX form submission to create a new DateOverride.
    Returns the updated partial HTML.
    """
    form = DateOverrideForm(request.POST)
    if form.is_valid():
        # Check if override already exists for this date to prevent duplicates/errors
        date_obj = form.cleaned_data['date']
        DateOverride.objects.filter(coach=request.user, date=date_obj).delete()
        
        override = form.save(commit=False)
        override.coach = request.user
        override.save()
        # Reset form for the UI
        form = DateOverrideForm()
    
    # Fetch fresh list for re-rendering
    overrides = DateOverride.objects.filter(
        coach=request.user, 
        date__gte=timezone.now().date()
    ).order_by('date')
    
    context = {
        'form': form,
        'overrides': overrides
    }
    return render(request, 'coaching_availability/partials/_one_off_availability.html', context)


@login_required
@require_http_methods(["DELETE"])
def delete_date_override(request, pk):
    """
    Handles HTMX delete request for a DateOverride.
    """
    try:
        override = DateOverride.objects.get(pk=pk, coach=request.user)
        override.delete()
    except DateOverride.DoesNotExist:
        pass
        
    return profile_override(request)


@login_required
@require_POST
def save_coach_vacation(request):
    """
    Handles HTMX form submission to create a new CoachVacation.
    Returns the updated partial HTML.
    """
    form = CoachVacationForm(request.POST)
    if form.is_valid():
        vacation = form.save(commit=False)
        vacation.coach = request.user
        vacation.save()
        # Reset form
        form = CoachVacationForm()
        
    vacations = CoachVacation.objects.filter(
        coach=request.user, 
        end_date__gte=timezone.now().date()
    ).order_by('start_date')
    
    context = {
        'form': form,
        'vacations': vacations
    }
    return render(request, 'coaching_availability/partials/_vacation_management.html', context)


@login_required
@require_http_methods(["DELETE"])
def delete_coach_vacation(request, pk):
    """
    Handles HTMX delete request for a CoachVacation.
    """
    try:
        vacation = CoachVacation.objects.get(pk=pk, coach=request.user)
        vacation.delete()
    except CoachVacation.DoesNotExist:
        pass
        
    return profile_vacation(request)