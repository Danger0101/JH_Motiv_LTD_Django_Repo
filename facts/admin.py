from django.contrib import admin
from .models import Fact

@admin.register(Fact)
class FactAdmin(admin.ModelAdmin):
    list_display = ('statistic_description', 'source_title', 'source_link')