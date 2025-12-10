from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils.html import format_html
from django.urls import reverse
from .models import User, MarketingPreference, Address, CoachProfile

# --- INLINES ---

class CoachProfileInline(admin.StackedInline):
    model = CoachProfile
    can_delete = False
    verbose_name_plural = 'Coach Profile'
    fk_name = 'user' # Explicitly link to the parent user
    
    # Optimization: prevents loading extra related data unnecessarily
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('user')

class MarketingPreferenceInline(admin.StackedInline):
    model = MarketingPreference
    can_delete = False
    verbose_name_plural = 'Marketing Preferences'
    fields = ('is_subscribed', 'subscribed_at')
    readonly_fields = ('subscribed_at',)

class AddressInline(admin.StackedInline):
    model = Address
    extra = 0
    can_delete = True
    verbose_name_plural = 'Addresses'

# --- MODEL ADMINS ---

@admin.register(User)
class UserAdmin(BaseUserAdmin):
    inlines = (CoachProfileInline, MarketingPreferenceInline, AddressInline)
    list_display = ('username', 'email', 'full_name_display', 'is_coach', 'is_client', 'date_joined')
    list_filter = BaseUserAdmin.list_filter + ('is_coach', 'is_client', 'is_on_vacation')
    search_fields = ('username', 'first_name', 'last_name', 'email', 'stripe_customer_id')
    ordering = ('-date_joined',) # Show newest users first
    
    # Optimization: Select related profile data if you display it in list view
    # For standard UserAdmin, this helps if you add profile columns later
    list_select_related = ('coach_profile',)

    @admin.display(description='Full Name')
    def full_name_display(self, obj):
        return obj.get_full_name()

    fieldsets = (
        (None, {'fields': ('username', 'password')}),
        ('Personal Info', {'fields': ('first_name', 'last_name', 'email')}),
        ('Permissions', {
            'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions'),
            'classes': ('collapse',),
        }),
        ('Roles & Status', {
            'fields': ('is_coach', 'is_client', 'is_on_vacation', 'user_timezone', 'billing_notes', 'stripe_customer_id')
        }),
        ('Important Dates', {'fields': ('last_login', 'date_joined')}),
    )

@admin.register(CoachProfile)
class CoachProfileAdmin(admin.ModelAdmin):
    list_display = ('user_link', 'time_zone', 'is_available_for_new_clients', 'has_gcal_connected')
    list_filter = ('is_available_for_new_clients', 'time_zone')
    search_fields = ('user__email', 'user__first_name', 'user__last_name', 'bio')
    list_select_related = ('user', 'google_credentials') 
    
    @admin.display(description='User', ordering='user__username')
    def user_link(self, obj):
        url = reverse("admin:accounts_user_change", args=[obj.user.pk])
        return format_html('<a href="{}">{}</a>', url, obj.user.get_full_name() or obj.user.username)

    @admin.display(boolean=True, description='GCal Synced?')
    def has_gcal_connected(self, obj):
        return hasattr(obj, 'google_credentials')

# Also register Address model to be managed independently
@admin.register(Address)
class AddressAdmin(admin.ModelAdmin):
    list_display = ('user_link', 'full_name', 'city', 'country', 'is_default')
    list_filter = ('is_default', 'country')
    search_fields = ('user__email', 'street_address', 'postcode')
    list_select_related = ('user',)

    @admin.display(description='User', ordering='user')
    def user_link(self, obj):
        if obj.user:
            url = reverse("admin:accounts_user_change", args=[obj.user.pk])
            return format_html('<a href="{}">{}</a>', url, obj.user.username)
        return "-"