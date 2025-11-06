from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import User, MarketingPreference, Address, CoachProfile

# Inlines for UserAdmin
class CoachProfileInline(admin.StackedInline):
    model = CoachProfile
    can_delete = False
    verbose_name_plural = 'Coach Profiles'

class MarketingPreferenceInline(admin.StackedInline):
    model = MarketingPreference
    can_delete = False
    verbose_name_plural = 'Marketing Preferences'
    fields = ('is_subscribed',)

class AddressInline(admin.StackedInline):
    model = Address
    extra = 1
    can_delete = True
    verbose_name_plural = 'Addresses'

# Custom UserAdmin
class UserAdmin(BaseUserAdmin):
    inlines = (CoachProfileInline, MarketingPreferenceInline, AddressInline)
    list_display = ('username', 'email', 'first_name', 'last_name', 'is_staff', 'is_coach', 'is_on_vacation')
    list_filter = BaseUserAdmin.list_filter + ('is_coach', 'is_on_vacation')
    fieldsets = (
        (None, {'fields': ('username', 'password')}),
        ('Personal info', {'fields': ('first_name', 'last_name', 'email')}),
        ('Permissions & Roles', {'fields': ('is_active', 'is_staff', 'is_superuser', 'is_coach', 'groups', 'user_permissions')}),
        ('Coach Settings', {'fields': ('is_on_vacation', 'user_timezone', 'billing_notes')}),
        ('Important dates', {'fields': ('last_login', 'date_joined')}),
    )

# Register the custom User admin, ensuring the default is unregistered first
if admin.site.is_registered(User):
    admin.site.unregister(User)
admin.site.register(User, UserAdmin)

@admin.register(CoachProfile)
class CoachProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'time_zone', 'is_available_for_new_clients')
    list_filter = ('is_available_for_new_clients', 'time_zone')
    search_fields = ['user__email', 'bio']
    # Note: The requested UserDetailInline was not created because CoachProfile
    # is the child in the User-CoachProfile relationship. The standard practice
    # is to inline the 'child' (CoachProfile) on the 'parent' (User) admin,
    # which has been done in the UserAdmin above.

# Also register Address model to be managed independently
@admin.register(Address)
class AddressAdmin(admin.ModelAdmin):
    list_display = ('user', 'full_name', 'street_address', 'city', 'postcode', 'country', 'is_default')
    list_filter = ('is_default', 'country')
    search_fields = ('user__username', 'full_name', 'street_address', 'city', 'postcode')