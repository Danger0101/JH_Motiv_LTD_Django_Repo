from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import User, CoachProfile, Address, MarketingPreference
from unfold.admin import ModelAdmin

@admin.register(User)
class CustomUserAdmin(ModelAdmin, UserAdmin):
    actions = ['delete_selected']
    fieldsets = UserAdmin.fieldsets + (
        ('Roles', {'fields': ('is_guest', 'is_coach', 'is_client', 'is_dreamer')}),
        ('Business Info', {'fields': ('business_name', 'billing_notes', 'stripe_customer_id')}),
        ('Preferences', {'fields': ('user_timezone',)}),
    )
    list_display = ('username', 'email', 'is_coach', 'is_client', 'is_guest', 'is_active')
    list_filter = ('is_coach', 'is_client', 'is_guest', 'is_active')

@admin.register(CoachProfile)
class CoachProfileAdmin(ModelAdmin):
    list_display = ('user', 'is_available_for_new_clients', 'average_dice_rating', 'review_count', 'last_synced')
    list_filter = ('is_available_for_new_clients',)
    search_fields = ('user__email', 'user__first_name', 'user__last_name')
    readonly_fields = ('average_dice_rating', 'review_count', 'last_synced')

@admin.register(Address)
class AddressAdmin(ModelAdmin):
    list_display = ('user', 'city', 'country', 'is_default')
    search_fields = ('user__email', 'street_address', 'postcode')

@admin.register(MarketingPreference)
class MarketingPreferenceAdmin(ModelAdmin):
    list_display = ('user', 'is_subscribed', 'updated_at')
    list_filter = ('is_subscribed',)