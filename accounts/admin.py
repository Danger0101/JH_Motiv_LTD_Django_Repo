from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import User, MarketingPreference

class MarketingPreferenceInline(admin.StackedInline):
    model = MarketingPreference
    can_delete = False
    verbose_name_plural = 'Marketing Preferences'
    fields = ('is_subscribed',)

class UserAdmin(BaseUserAdmin):
    inlines = (MarketingPreferenceInline,)
    list_display = ('username', 'email', 'first_name', 'last_name', 'is_staff', 'is_coach')
    fieldsets = (
        (None, {'fields': ('username', 'password')}),
        ('Personal info', {'fields': ('first_name', 'last_name', 'email')}),
        ('Permissions', {'fields': ('is_active', 'is_staff', 'is_superuser', 'is_coach', 'groups', 'user_permissions')}),
        ('Important dates', {'fields': ('last_login', 'date_joined')}),
    )

# Register the custom User admin
admin.site.register(User, UserAdmin)
