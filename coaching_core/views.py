from django.urls import reverse_lazy
from django.utils.text import slugify
from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
import json
from django.utils import timezone
from datetime import datetime, timedelta
import pytz

from .models import Offering, Workshop
from .forms import OfferingCreationForm, WorkshopForm
from coaching_booking.models import SessionBooking
from coaching_booking.utils import generate_workshop_ics

class StaffRequiredMixin(LoginRequiredMixin, UserPassesTestMixin):
    """Mixin to ensure the user is a logged-in staff member."""
    def test_func(self):
        return self.request.user.is_staff

class WorkshopListView(ListView):
    model = Workshop
    template_name = 'coaching_core/workshop_list.html'
    context_object_name = 'workshops'

class WorkshopDetailView(DetailView):
    model = Workshop
    template_name = 'coaching_core/workshop_detail.html'
    context_object_name = 'workshop'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        workshop = self.object
        user = self.request.user
        
        # 1. Check if User has Booked
        user_has_booked = False
        if user.is_authenticated:
            user_has_booked = SessionBooking.objects.filter(
                workshop=workshop,
                client=user,
                status__in=['BOOKED', 'PENDING_PAYMENT']
            ).exists()
        context['user_has_booked'] = user_has_booked

        # 2. Check Join Window (15 mins before start until end)
        now = timezone.now()
        start_dt = datetime.combine(workshop.date, workshop.start_time)
        end_dt = datetime.combine(workshop.date, workshop.end_time)
        if timezone.is_naive(start_dt): start_dt = timezone.make_aware(start_dt)
        if timezone.is_naive(end_dt): end_dt = timezone.make_aware(end_dt)
        
        show_join_button = False
        if user_has_booked and workshop.meeting_link:
            if now >= (start_dt - timedelta(minutes=15)) and now < end_dt:
                show_join_button = True
        context['show_join_button'] = show_join_button

        # 3. Google Calendar Add Link
        # Format: YYYYMMDDTHHMMSSZ
        fmt = '%Y%m%dT%H%M%SZ'
        gcal_start = start_dt.astimezone(pytz.utc).strftime(fmt)
        gcal_end = end_dt.astimezone(pytz.utc).strftime(fmt)
        
        gcal_link = f"https://calendar.google.com/calendar/render?action=TEMPLATE&text={workshop.name}&dates={gcal_start}/{gcal_end}&details={workshop.description}&location={workshop.meeting_link or ''}"
        context['google_calendar_link'] = gcal_link

        return context

class WorkshopCreateView(LoginRequiredMixin, CreateView):
    model = Workshop
    form_class = WorkshopForm
    template_name = 'coaching_core/workshop_form.html'
    success_url = reverse_lazy('coaching_core:workshop-list')

    def form_valid(self, form):
        workshop = form.save(commit=False)
        workshop.created_by = self.request.user
        workshop.slug = slugify(f"{workshop.name}-{workshop.date.strftime('%Y-%m-%d')}")
        workshop.save()
        return super().form_valid(form)

class WorkshopUpdateView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    model = Workshop
    form_class = WorkshopForm
    template_name = 'coaching_core/workshop_form.html'
    success_url = reverse_lazy('coaching_core:workshop-list')

    def test_func(self):
        workshop = self.get_object()
        return self.request.user == workshop.coach.user

class WorkshopDeleteView(LoginRequiredMixin, UserPassesTestMixin, DeleteView):
    model = Workshop
    template_name = 'coaching_core/workshop_confirm_delete.html'
    success_url = reverse_lazy('coaching_core:workshop-list')

    def test_func(self):
        workshop = self.get_object()
        return self.request.user == workshop.coach.user


class OfferingListView(StaffRequiredMixin, ListView):
    model = Offering
    template_name = 'coaching_core/offering_list.html'
    context_object_name = 'offerings'

    def get_queryset(self):
        return Offering.objects.prefetch_related('coaches__user')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['workshops'] = Workshop.objects.filter(active_status=True)

        # --- SEASONAL HERO LOGIC ---
        current_month = timezone.now().month
        season_map = {
            12: 'winter', 1: 'winter', 2: 'winter',
            3: 'spring', 4: 'spring', 5: 'spring',
            6: 'summer', 7: 'summer', 8: 'summer',
            9: 'Fall', 10: 'Fall', 11: 'Fall',
        }
        season_name = season_map.get(current_month, 'winter')
        
        context['seasonal_hero_image'] = f"images/{season_name}_banner.webp"
        return context

class OfferingDetailView(StaffRequiredMixin, DetailView):
    model = Offering
    template_name = 'coaching_core/offering_detail.html'
    context_object_name = 'offering'

class OfferingCreateView(StaffRequiredMixin, CreateView):
    model = Offering
    form_class = OfferingCreationForm
    template_name = 'coaching_core/offering_form.html'
    success_url = reverse_lazy('coaching_core:offering-list')

    def form_valid(self, form):
        offering = form.save(commit=False)
        offering.slug = slugify(offering.name)
        # Assuming a created_by field exists on the model
        # offering.created_by = self.request.user
        offering.save()
        return super().form_valid(form)

class OfferingUpdateView(StaffRequiredMixin, UpdateView):
    model = Offering
    form_class = OfferingCreationForm
    template_name = 'coaching_core/offering_form.html'
    success_url = reverse_lazy('coaching_core:offering-list')

class OfferingDeleteView(StaffRequiredMixin, DeleteView):
    model = Offering
    template_name = 'coaching_core/offering_confirm_delete.html'
    success_url = reverse_lazy('coaching_core:offering-list')

@csrf_exempt
def api_recurring_availability(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            # Process the data, e.g., save recurring availability
            # For now, just return a success message
            return JsonResponse({'status': 'success', 'message': 'Recurring availability processed.'})
        except json.JSONDecodeError:
            return JsonResponse({'status': 'error', 'message': 'Invalid JSON'}, status=400)
    return JsonResponse({'status': 'error', 'message': 'Only POST method is allowed'}, status=405)

def workshop_ics_download(request, slug):
    """Download ICS file for a workshop."""
    from django.shortcuts import get_object_or_404
    workshop = get_object_or_404(Workshop, slug=slug)
    ics_data, filename = generate_workshop_ics(workshop)
    response = HttpResponse(ics_data, content_type='text/calendar')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response