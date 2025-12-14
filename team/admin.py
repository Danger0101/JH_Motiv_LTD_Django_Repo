from django.contrib import admin
from django.utils.html import format_html
from .models import TeamMember

@admin.register(TeamMember)
class TeamMemberAdmin(admin.ModelAdmin):
    # Added 'character_class' to display and editable list
    list_display = ('avatar_preview', 'name', 'character_class', 'role', 'is_active', 'order')
    list_display_links = ('name',)
    list_editable = ('is_active', 'order', 'character_class') 
    list_filter = ('is_active', 'character_class')
    search_fields = ('name', 'role', 'bio')
    ordering = ('order',)

    @admin.display(description='Photo')
    def avatar_preview(self, obj):
        if obj.profile_image:
            return format_html('<img src="{}" style="width: 40px; height: 40px; object-fit: cover; border-radius: 50%;" />', obj.profile_image.url)
        return "-"