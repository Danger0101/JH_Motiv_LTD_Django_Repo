from django.urls import reverse_lazy
from django.utils.text import slugify
from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
import json

from .models import Offering
from .forms import OfferingCreationForm

class StaffRequiredMixin(LoginRequiredMixin, UserPassesTestMixin):
    """Mixin to ensure the user is a logged-in staff member."""
    def test_func(self):
        return self.request.user.is_staff

class OfferingListView(StaffRequiredMixin, ListView):
    model = Offering
    template_name = 'coaching_core/offering_list.html'
    context_object_name = 'offerings'

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