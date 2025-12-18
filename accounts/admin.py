from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils.html import format_html
from unfold.admin import ModelAdmin
from django.shortcuts import render
from django.http import HttpResponseRedirect
from django.urls import reverse
from .models import User, MarketingPreference, Address, CoachProfile
from django.conf import settings
from django.contrib import messages
from django.core.mail import send_mail
import stripe
import logging
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
class UserAdmin(BaseUserAdmin, ModelAdmin):
    inlines = (CoachProfileInline, MarketingPreferenceInline, AddressInline)
    list_display = ('username', 'email', 'full_name_display', 'is_coach', 'is_client', 'stripe_link', 'date_joined')
    list_filter = BaseUserAdmin.list_filter + ('is_coach', 'is_client', 'is_on_vacation')
    search_fields = ('username', 'first_name', 'last_name', 'email', 'stripe_customer_id')
    ordering = ('-date_joined',)
    
    actions = ['sync_with_stripe', 'send_bulk_email']
    
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

    @admin.display(description='Stripe Profile')
    def stripe_link(self, obj):
        if not obj.stripe_customer_id:
            return "N/A"
        
        is_live = settings.STRIPE_SECRET_KEY and not settings.STRIPE_SECRET_KEY.startswith('sk_test_')
        
        base_url = "https://dashboard.stripe.com"
        path = "" if is_live else "/test"
        url = f"{base_url}{path}/customers/{obj.stripe_customer_id}"
        return format_html('<a href="{}" target="_blank">View on Stripe</a>', url)

    @admin.action(description='Sync selected users with Stripe')
    def sync_with_stripe(self, request, queryset):
        if not settings.STRIPE_SECRET_KEY:
            self.message_user(request, "Stripe is not configured.", level=messages.ERROR)
            return

        stripe.api_key = settings.STRIPE_SECRET_KEY
        synced_count = 0
        skipped_count = 0
        failed_count = 0

        for user in queryset:
            if user.stripe_customer_id:
                skipped_count += 1
                continue

            try:
                customer = stripe.Customer.create(
                    email=user.email,
                    name=user.get_full_name(),
                    metadata={'user_id': user.id, 'username': user.username}
                )
                user.stripe_customer_id = customer.id
                user.save(update_fields=['stripe_customer_id'])
                synced_count += 1
            except Exception as e:
                logging.getLogger(__name__).error(f"Failed to create Stripe customer for user {user.email}: {e}")
                failed_count += 1

        if synced_count > 0:
            self.message_user(request, f"Successfully synced {synced_count} user(s) with Stripe.", level=messages.SUCCESS)
        if skipped_count > 0:
            self.message_user(request, f"Skipped {skipped_count} user(s) who already had a Stripe ID.", level=messages.INFO)
        if failed_count > 0:
            self.message_user(request, f"Failed to sync {failed_count} user(s). Check logs for details.", level=messages.ERROR)

    @admin.action(description='Send Bulk Email (Newsletter)')
    def send_bulk_email(self, request, queryset):
        if 'apply' in request.POST:
            subject = request.POST.get('subject')
            message_body = request.POST.get('message')
            count = 0
            for user in queryset:
                if user.email:
                    try:
                        send_mail(
                            subject,
                            message_body,
                            settings.DEFAULT_FROM_EMAIL,
                            [user.email],
                            fail_silently=False,
                        )
                        count += 1
                    except Exception as e:
                        logging.getLogger(__name__).error(f"Failed to send email to {user.email}: {e}")
            
            self.message_user(request, f"Sent {count} emails.")
            return HttpResponseRedirect(request.get_full_path())
            
        return render(request, 'admin/accounts/user/send_bulk_email.html', context={'users': queryset})

@admin.register(CoachProfile)
class CoachProfileAdmin(ModelAdmin):
    list_display = ('user_link', 'time_zone', 'is_available_for_new_clients', 'has_gcal_connected', 'last_synced')
    list_filter = ('is_available_for_new_clients', 'time_zone')
    list_editable = ('is_available_for_new_clients',)
    search_fields = ('user__email', 'user__first_name', 'user__last_name', 'bio')
    readonly_fields = ('last_synced',)
    list_select_related = ('user',)
    actions = ['trigger_gcal_sync']
    
    @admin.display(description='User', ordering='user__username')
    def user_link(self, obj):
        url = reverse("admin:accounts_user_change", args=[obj.user.pk])
        return format_html('<a href="{}">{}</a>', url, obj.user.get_full_name() or obj.user.username)

    @admin.display(boolean=True, description='GCal Synced?')
    def has_gcal_connected(self, obj):
        return bool(obj.user.google_calendar_credentials)

    @admin.action(description='Force GCal Sync for selected coaches')
    def trigger_gcal_sync(self, request, queryset):
        from coaching_booking.tasks import sync_single_coach_calendar
        
        triggered_count = 0
        for coach_profile in queryset:
            if coach_profile.user.google_calendar_credentials:
                sync_single_coach_calendar.delay(coach_profile.id)
                triggered_count += 1
        
        if triggered_count > 0:
            self.message_user(request, f"Sync queued for {triggered_count} coach(es).", level=messages.SUCCESS)
        else:
            self.message_user(request, "No selected coaches have Google Calendar connected.", level=messages.WARNING)

# Also register Address model to be managed independently
@admin.register(Address)
class AddressAdmin(ModelAdmin):
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