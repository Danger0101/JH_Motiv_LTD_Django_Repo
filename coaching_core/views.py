from django.urls import reverse_lazy
from django.utils.text import slugify
from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
import json
from django.utils import timezone

from .models import Offering, Workshop
from .forms import OfferingCreationForm, WorkshopForm

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

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['workshops'] = Workshop.objects.filter(active_status=True)

        # --- SEASONAL HERO LOGIC ---
        current_month = timezone.now().month
        if current_month in [3, 4, 5]:
            season_file = 'spring_banner.webp'
        elif current_month in [6, 7, 8]:
            season_file = 'summer_banner.webp'
        elif current_month in [9, 10, 11]:
            season_file = 'Fall_banner.webp'
        else:
            season_file = 'winter_banner.webp'
        
        context['seasonal_hero_image'] = f"images/{season_file}"
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