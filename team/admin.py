from django.contrib import admin
from .models import TeamMember

@admin.register(TeamMember)
class TeamMemberAdmin(admin.ModelAdmin):
    list_display = ('name', 'role', 'is_active', 'order')
    list_filter = ('is_active',)
    search_fields = ('name', 'role', 'bio')
    ordering = ('order',)