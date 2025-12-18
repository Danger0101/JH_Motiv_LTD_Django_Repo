from django.contrib import admin
from django.utils import timezone
from django.contrib import messages
from django.shortcuts import render, redirect
from django.urls import path, reverse
from django.utils.html import format_html
from unfold.admin import ModelAdmin
from .models import NewsletterSubscriber, NewsletterCampaign, CheatUsage, EmailResendLog, Newsletter
from .tasks import send_newsletter_blast_task

# Register your models here.

# --- GLOBAL CONFIGURATION ---
# Place this in core/admin.py (or any main admin.py file loaded at startup)

admin.site.site_header = "JH Motiv Operations"       # Top of every admin page
admin.site.site_title = "JH Motiv Admin"             # Browser tab title
admin.site.index_title = "Business Dashboard"        # Main index page title
admin.site.empty_value_display = "-empty-"           # Replaces "(None)" in lists for cleaner reading

# Optional: Disable the default "Groups" model if you don't use complex permissions
# from django.contrib.auth.models import Group
# admin.site.unregister(Group)

@admin.register(NewsletterSubscriber)
class NewsletterSubscriberAdmin(admin.ModelAdmin):
    list_display = ('email', 'is_active', 'subscribed_at')
    list_filter = ('is_active', 'subscribed_at')
    search_fields = ('email',)

@admin.register(NewsletterCampaign)
class NewsletterCampaignAdmin(admin.ModelAdmin):
    list_display = ('subject', 'status', 'sent_at', 'recipient_count')
    list_filter = ('status', 'sent_at')
    search_fields = ('subject',)

@admin.register(CheatUsage)
class CheatUsageAdmin(admin.ModelAdmin):
    list_display = ('code_used', 'action_triggered', 'user', 'ip_address', 'timestamp')
    list_filter = ('code_used', 'action_triggered', 'timestamp')
    search_fields = ('code_used', 'user__username', 'user__email', 'ip_address')
    readonly_fields = ('timestamp', 'code_used', 'user', 'ip_address', 'action_triggered')

    def has_add_permission(self, request):
        return False

@admin.register(Newsletter)
class NewsletterAdmin(ModelAdmin):
    list_display = ('subject', 'status', 'template', 'sent_at', 'preview_link')
    list_filter = ('status', 'created_at')
    search_fields = ('subject', 'body')
    readonly_fields = ('sent_at',)
    
    def preview_link(self, obj):
        if obj.slug:
            # Assumes you have a public view for this, or uses the admin preview
            return format_html('<a href="{}" target="_blank" class="text-blue-600 hover:text-blue-900">Preview</a>', "#")
    preview_link.short_description = "Preview"

    # --- Custom Actions ---
    
    actions = ['send_campaign']

    @admin.action(description="Send selected campaign to ALL subscribers")
    def send_campaign(self, request, queryset):
        if queryset.count() > 1:
            messages.error(request, "Please select only one newsletter to send at a time.")
            return
        
        newsletter = queryset.first()
        
        if newsletter.status == 'sent':
            messages.warning(request, "This newsletter has already been sent!")
            return

        if newsletter.scheduled_at and newsletter.scheduled_at > timezone.now():
            # Schedule for future
            send_newsletter_blast_task.apply_async(args=[newsletter.id], eta=newsletter.scheduled_at)
            newsletter.status = 'scheduled'
            newsletter.save()
            messages.success(request, f"Newsletter '{newsletter.subject}' scheduled for {newsletter.scheduled_at}.")
        else:
            # Send immediately
            send_newsletter_blast_task.delay(newsletter.id)
            # Update Status
            newsletter.status = 'sent'
            newsletter.sent_at = timezone.now()
            newsletter.save()
            messages.success(request, f"Newsletter '{newsletter.subject}' has been queued for sending.")

    # --- Custom Test Email Button in the Change Form ---
    
    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('<int:object_id>/test-send/', self.admin_site.admin_view(self.send_test_email), name='core_newsletter_test_send'),
        ]
        return custom_urls + urls

    def send_test_email(self, request, object_id):
        newsletter = self.get_object(request, object_id)
        
        if request.method == 'POST':
            email = request.POST.get('test_email')
            if email:
                # Send single test email
                from .tasks import send_transactional_email_task
                
                context = {
                    'newsletter_id': newsletter.id,
                    'unsubscribe_url': "#", # Dummy link for test
                }
                # Select template based on model choice
                template_path = f"emails/newsletters/layout_{newsletter.template}.html"
                
                send_transactional_email_task.delay(
                    email,
                    f"[TEST] {newsletter.subject}",
                    template_path,
                    context
                )
                messages.success(request, f"Test email sent to {email}")
                return redirect(reverse('admin:core_newsletter_change', args=[object_id]))
        
        context = {
            'newsletter': newsletter,
            'title': f"Send Test: {newsletter.subject}",
            'site_title': self.admin_site.site_title,
            'site_header': self.admin_site.site_header,
        }
        return render(request, 'admin/core/newsletter/test_send.html', context)

    def change_view(self, request, object_id, form_url='', extra_context=None):
        extra_context = extra_context or {}
        # Pass the test send URL to the template (Unfold allows adding custom buttons)
        extra_context['test_send_url'] = reverse('admin:core_newsletter_test_send', args=[object_id])
        return super().change_view(request, object_id, form_url, extra_context=extra_context)

@admin.register(EmailResendLog)
class EmailResendLogAdmin(admin.ModelAdmin):
    list_display = ('email', 'ip_address', 'timestamp')
    list_filter = ('timestamp',)
    search_fields = ('email', 'ip_address')
    readonly_fields = ('email', 'ip_address', 'user_agent', 'timestamp')

    def has_add_permission(self, request):
        return False

def dashboard_callback(request, context):
    from django.db.models import Count, Q
    from coaching_core.models import Workshop
    
    now = timezone.now()
    
    # Calculate Workshop Revenue for current month
    # Logic: Sum of (Workshop Price * Confirmed Bookings) for workshops held this month
    workshops = Workshop.objects.filter(
        date__year=now.year,
        date__month=now.month
    ).annotate(
        confirmed_bookings=Count('bookings', filter=Q(bookings__status__in=['BOOKED', 'COMPLETED']))
    )
    
    total_revenue = sum(ws.confirmed_bookings * ws.price for ws in workshops)
    
    context.update({
        "kpi": [
            {
                "title": "Workshop Revenue",
                "metric": f"£{total_revenue:,.2f}",
                "footer": f"Total for {now.strftime('%B %Y')}",
            },
        ]
    })
    return context
