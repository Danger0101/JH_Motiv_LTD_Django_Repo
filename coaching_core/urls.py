from django.urls import path
from . import views

app_name = 'coaching'

urlpatterns = [
    path('api/recurring-availability/', views.api_recurring_availability, name='api_recurring_availability'),
    
    # Workshop URLs
    path('workshops/', views.WorkshopListView.as_view(), name='workshop-list'),
    path('workshops/create/', views.WorkshopCreateView.as_view(), name='workshop-create'),
    path('workshops/<slug:slug>/', views.WorkshopDetailView.as_view(), name='workshop-detail'),
    path('workshops/<slug:slug>/update/', views.WorkshopUpdateView.as_view(), name='workshop-update'),
    path('workshops/<slug:slug>/delete/', views.WorkshopDeleteView.as_view(), name='workshop-delete'),

    # Offering URLs
    path('offerings/', views.OfferingListView.as_view(), name='offering-list'),
    path('offerings/create/', views.OfferingCreateView.as_view(), name='offering-create'),
    path('offerings/<slug:slug>/', views.OfferingDetailView.as_view(), name='offering-detail'),
    path('offerings/<slug:slug>/update/', views.OfferingUpdateView.as_view(), name='offering-update'),
    path('offerings/<slug:slug>/delete/', views.OfferingDeleteView.as_view(), name='offering-delete'),
]