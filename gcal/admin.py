from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils import timezone
from .models import GoogleCredentials

@admin.register(GoogleCredentials)
class GoogleCredentialsAdmin(admin.ModelAdmin):
    list_display = ('coach_link', 'calendar_id', 'token_status', 'token_expiry', 'last_synced')
    list_select_related = ('coach', 'coach__user')
    search_fields = ('coach__user__email', 'coach__user__username', 'calendar_id')
    
    # Make everything read-only to prevent breaking sync logic manually
    readonly_fields = ('coach', 'calendar_id', 'access_token', 'refresh_token', 'token_expiry', 'scopes', 'token_created_at')
    
    fieldsets = (
        ('Coach Connection', {
            'fields': ('coach', 'calendar_id')
        }),
        ('Token Status', {
            'fields': ('token_expiry', 'token_created_at', 'scopes')
        }),
        ('Sensitive Data (Read-Only)', {
            'fields': ('access_token', 'refresh_token'),
            'classes': ('collapse',), # Hide by default for security visual
        }),
    )

    def has_add_permission(self, request):
        # Prevent manual creation; must be done via OAuth flow
        return False

    @admin.display(description='Coach', ordering='coach__user__last_name')
    def coach_link(self, obj):
        url = reverse("admin:accounts_coachprofile_change", args=[obj.coach.pk])
        return format_html('<a href="{}">{}</a>', url, obj.coach.user.get_full_name())

    @admin.display(description='Status', boolean=True)
    def token_status(self, obj):
        """Returns True if token is valid, False if expired."""
        if not obj.token_expiry:
            return False
        return obj.token_expiry > timezone.now()
    
    @admin.display(description='Created At')
    def last_synced(self, obj):
        return obj.token_created_at