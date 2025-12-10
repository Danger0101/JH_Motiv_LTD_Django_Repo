from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from .models import Dreamer, DreamerProfile, ChannelLink

# --- INLINES ---

class ChannelLinkInline(admin.TabularInline):
    model = ChannelLink
    extra = 1
    verbose_name = "Social Channel"
    verbose_name_plural = "Social Channels"

# --- MODEL ADMINS ---

@admin.register(Dreamer)
class DreamerAdmin(admin.ModelAdmin):
    """Admin for newsletter subscribers/community members."""
    list_display = ('email', 'first_name', 'last_name', 'active', 'created_at')
    list_filter = ('active', 'created_at')
    search_fields = ('email', 'first_name', 'last_name')
    ordering = ('-created_at',)

@admin.register(DreamerProfile)
class DreamerProfileAdmin(admin.ModelAdmin):
    """Admin for public-facing Dreamer profiles (Affiliates)."""
    list_display = ('name', 'user_link', 'is_featured', 'order', 'channel_count')
    list_editable = ('is_featured', 'order')
    list_filter = ('is_featured',)
    search_fields = ('name', 'user__email', 'user__username')
    readonly_fields = ('slug',)
    inlines = [ChannelLinkInline]
    
    # Optimization
    list_select_related = ('user',)

    @admin.display(description='User Account', ordering='user__username')
    def user_link(self, obj):
        if obj.user:
            url = reverse("admin:accounts_user_change", args=[obj.user.pk])
            return format_html('<a href="{}">{}</a>', url, obj.user.username)
        return "No User Linked"

    @admin.display(description='Channels')
    def channel_count(self, obj):
        return obj.channels.count()

    fieldsets = (
        ('Profile Info', {'fields': ('name', 'slug', 'story_excerpt', 'user')}),
        ('Visibility & Ordering', {'fields': ('is_featured', 'order'),}),
        ('Financials', {'fields': ('payout_details',), 'classes': ('collapse',),}),
    )