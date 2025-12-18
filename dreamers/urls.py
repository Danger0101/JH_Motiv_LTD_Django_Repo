from django.urls import path
from . import views

app_name = 'dreamers'

urlpatterns = [
    path('apply/', views.DreamerApplicationView.as_view(), name='apply'),
    path('staff/manage/', views.StaffDreamerManageView.as_view(), name='staff_manage'),
    path('staff/action/<int:pk>/', views.StaffDreamerActionView.as_view(), name='staff_action'),
    path('<slug:slug>/', views.DreamerLandingView.as_view(), name='dreamer_landing'),
]