from django.urls import path
from . import views

app_name = 'dreamers'

urlpatterns = [
    path('<slug:slug>/', views.DreamerLandingView.as_view(), name='dreamer_landing'),
]