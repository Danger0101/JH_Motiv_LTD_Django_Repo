from django.contrib import admin
from django.utils.html import format_html
from .models import Fact

@admin.register(Fact)
class FactAdmin(admin.ModelAdmin):
    list_display = ('statistic_description', 'source_title', 'source_link_display')
    search_fields = ('statistic_description', 'source_title')

    @admin.display(description='Source Link')
    def source_link_display(self, obj):
        if obj.source_link:
            return format_html('<a href="{}" target="_blank">View Source</a>', obj.source_link)
        return "-"