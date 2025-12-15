from django.contrib import admin
from .models import NewsletterSubscriber, NewsletterCampaign, CheatUsage

# Register your models here.

# --- GLOBAL CONFIGURATION ---
# Place this in core/admin.py (or any main admin.py file loaded at startup)

admin.site.site_header = "JH Motiv Operations"       # Top of every admin page
admin.site.site_title = "JH Motiv Admin"             # Browser tab title
admin.site.index_title = "Business Dashboard"        # Main index page title
admin.site.empty_value_display = "-empty-"           # Replaces "(None)" in lists for cleaner reading

# Optional: Disable the default "Groups" model if you don't use complex permissions
# from django.contrib.auth.models import Group
# admin.site.unregister(Group)

@admin.register(NewsletterSubscriber)
class NewsletterSubscriberAdmin(admin.ModelAdmin):
    list_display = ('email', 'is_active', 'subscribed_at')
    list_filter = ('is_active', 'subscribed_at')
    search_fields = ('email',)

@admin.register(NewsletterCampaign)
class NewsletterCampaignAdmin(admin.ModelAdmin):
    list_display = ('subject', 'status', 'sent_at', 'recipient_count')
    list_filter = ('status', 'sent_at')
    search_fields = ('subject',)

@admin.register(CheatUsage)
class CheatUsageAdmin(admin.ModelAdmin):
    list_display = ('code_used', 'action_triggered', 'user', 'ip_address', 'timestamp')
    list_filter = ('code_used', 'action_triggered', 'timestamp')
    search_fields = ('code_used', 'user__username', 'user__email', 'ip_address')
    readonly_fields = ('timestamp', 'code_used', 'user', 'ip_address', 'action_triggered')

    def has_add_permission(self, request):
        return False
