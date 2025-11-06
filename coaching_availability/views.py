from django.urls import reverse_lazy
from django.views.generic import ListView, CreateView, DeleteView
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.utils import timezone

from .models import CoachAvailability, CoachVacation
from .forms import CoachAvailabilityForm

class CoachRequiredMixin(LoginRequiredMixin, UserPassesTestMixin):
    """Mixin to ensure the user is a logged-in coach."""
    def test_func(self):
        # Assumes a related 'coachprofile' exists or an 'is_coach' boolean.
        return hasattr(self.request.user, 'coachprofile') and self.request.user.is_coach

# --- Coach Availability Views ---

class AvailabilityListView(CoachRequiredMixin, ListView):
    model = CoachAvailability
    template_name = 'coaching_availability/availability_list.html'
    context_object_name = 'availabilities'

    def get_queryset(self):
        """Only show availability for the currently logged-in coach."""
        return CoachAvailability.objects.filter(coach=self.request.user.coachprofile)

class AvailabilityCreateView(CoachRequiredMixin, CreateView):
    model = CoachAvailability
    form_class = CoachAvailabilityForm
    template_name = 'coaching_availability/availability_form.html'
    success_url = reverse_lazy('coaching_availability:availability-list')

    def form_valid(self, form):
        availability = form.save(commit=False)
        availability.coach = self.request.user.coachprofile
        availability.save()
        return super().form_valid(form)

class AvailabilityDeleteView(CoachRequiredMixin, DeleteView):
    model = CoachAvailability
    template_name = 'coaching_availability/availability_confirm_delete.html'
    success_url = reverse_lazy('coaching_availability:availability-list')

# --- Coach Vacation Views ---

class VacationListView(CoachRequiredMixin, ListView):
    model = CoachVacation
    template_name = 'coaching_availability/vacation_list.html'
    context_object_name = 'vacations'

    def get_queryset(self):
        """Only show future vacations for the currently logged-in coach."""
        return CoachVacation.objects.filter(
            coach=self.request.user.coachprofile,
            end_date__gte=timezone.now().date()
        )

class VacationCreateView(CoachRequiredMixin, CreateView):
    model = CoachVacation
    fields = ['start_date', 'end_date', 'cancel_bookings']
    template_name = 'coaching_availability/vacation_form.html'
    success_url = reverse_lazy('coaching_availability:vacation-list')

    def form_valid(self, form):
        vacation = form.save(commit=False)
        vacation.coach = self.request.user.coachprofile
        vacation.save()
        return super().form_valid(form)