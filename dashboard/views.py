from django.shortcuts import render
from django.views.generic import TemplateView
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import HttpResponseRedirect
from django.urls import reverse

@login_required
def dashboard_view(request):
    if request.user.is_coach:
        return HttpResponseRedirect(reverse('coach_dashboard'))
    else:
        return HttpResponseRedirect(reverse('client_dashboard'))

class StaffDashboardView(LoginRequiredMixin, TemplateView):
    template_name = 'dashboard/staff_dashboard.html'

class CoachDashboardView(LoginRequiredMixin, TemplateView):
    template_name = 'dashboard/coach_dashboard.html'

class ClientDashboardView(LoginRequiredMixin, TemplateView):
    template_name = 'dashboard/client_dashboard.html'