from django.urls import path
from . import views

app_name = 'coaching_core'

urlpatterns = [
    path('api/recurring-availability/', views.api_recurring_availability, name='api_recurring_availability'),
    
    # Workshop URLs
    path('workshops/', views.WorkshopListView.as_view(), name='workshop_list'),
    path('workshops/create/', views.WorkshopCreateView.as_view(), name='workshop_create'),
    path('workshops/<slug:slug>/', views.WorkshopDetailView.as_view(), name='workshop_detail'),
    path('workshops/<slug:slug>/update/', views.WorkshopUpdateView.as_view(), name='workshop_update'),
    path('workshops/<slug:slug>/delete/', views.WorkshopDeleteView.as_view(), name='workshop_delete'),
    path('workshops/<slug:slug>/ics/', views.workshop_ics_download, name='workshop_ics'),

    # Offering URLs
    path('offerings/', views.OfferingListView.as_view(), name='offering-list'),
    path('offerings/create/', views.OfferingCreateView.as_view(), name='offering-create'),
    path('offerings/<slug:slug>/', views.OfferingDetailView.as_view(), name='offering-detail'),
    path('offerings/<slug:slug>/update/', views.OfferingUpdateView.as_view(), name='offering-update'),
    path('offerings/<slug:slug>/delete/', views.OfferingDeleteView.as_view(), name='offering-delete'),
]