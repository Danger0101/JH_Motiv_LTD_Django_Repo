from django.contrib import admin
from .models import TasterSessionRequest

@admin.register(TasterSessionRequest)
class TasterRequestAdmin(admin.ModelAdmin):
    list_display = ('client', 'requested_at', 'status', 'approver', 'decision_at')
    list_filter = ('status',)
    search_fields = ['client__email', 'notes']
    fieldsets = (
        ('Request Details', {
            'fields': ('client', 'requested_at')
        }),
        ('Decision', {
            'fields': ('status', 'approver', 'decision_at', 'notes')
        }),
    )
    readonly_fields = ('client', 'requested_at')