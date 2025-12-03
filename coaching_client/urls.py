from django.urls import path
from . import views

app_name = 'coaching_client'

urlpatterns = [
    # Public facing URLs
    path('request/', views.TasterRequestView.as_view(), name='taster_request'),
    path('request/success/', views.TasterRequestSuccessView.as_view(), name='taster_success'), 
    
    # Internal Action URL (Accept/Deny, used in the coach dashboard)
    path('request/<int:pk>/action/', views.TasterRequestActionView.as_view(), name='taster_action'),
    
    # NOTE: The TasterRequestManagerView is included via a template, not here.
]