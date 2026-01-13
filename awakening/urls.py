from django.urls import path
from . import views

app_name = 'awakening'

urlpatterns = [
    # The Entry Point (The Terminal Container)
    path('', views.funnel_landing, name='landing'),
    
    # HTMX Partials (The Steps)
    path('step-1-hook/', views.render_hook, name='step_1_hook'),
    path('step-2-offers/', views.render_offers, name='step_2_offers'),
    path('step-3-checkout/<int:variant_id>/', views.render_checkout, name='step_3_checkout'),
    
    # The "System Log" API
    path('api/system-log/', views.simulation_log_api, name='api_log'),
]