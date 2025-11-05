from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import User, MarketingPreference, Address

class MarketingPreferenceInline(admin.StackedInline):
    model = MarketingPreference
    can_delete = False
    verbose_name_plural = 'Marketing Preferences'
    fields = ('is_subscribed',)

class AddressInline(admin.StackedInline):
    model = Address
    extra = 1 # Show one extra form for adding an address
    can_delete = True
    verbose_name_plural = 'Addresses'

class UserAdmin(BaseUserAdmin):
    inlines = (MarketingPreferenceInline, AddressInline)
    list_display = ('username', 'email', 'first_name', 'last_name', 'is_staff', 'is_coach', 'is_on_vacation')
    list_filter = BaseUserAdmin.list_filter + ('is_coach', 'is_on_vacation')
    fieldsets = (
        (None, {'fields': ('username', 'password')}),
        ('Personal info', {'fields': ('first_name', 'last_name', 'email')}),
        ('Permissions & Roles', {'fields': ('is_active', 'is_staff', 'is_superuser', 'is_coach', 'groups', 'user_permissions')}),
        ('Coach Settings', {'fields': ('is_on_vacation', 'user_timezone', 'billing_notes')}),
        ('Important dates', {'fields': ('last_login', 'date_joined')}),
    )

# Register the custom User admin
admin.site.register(User, UserAdmin)

# Also register Address model to be managed independently
@admin.register(Address)
class AddressAdmin(admin.ModelAdmin):
    list_display = ('user', 'full_name', 'street_address', 'city', 'postcode', 'country', 'is_default')
    list_filter = ('is_default', 'country')
    search_fields = ('user__username', 'full_name', 'street_address', 'city', 'postcode')
