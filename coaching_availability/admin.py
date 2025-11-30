from django.contrib import admin
from .models import CoachAvailability, DateOverride, CoachVacation

admin.site.register(CoachAvailability)
admin.site.register(DateOverride)
admin.site.register(CoachVacation)
