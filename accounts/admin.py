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

# Register the custom User admin
admin.site.register(User, UserAdmin)
