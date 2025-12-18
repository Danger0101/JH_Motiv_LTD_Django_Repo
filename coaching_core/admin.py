from django.contrib import admin
from django.urls import path, reverse
from django.shortcuts import render, redirect, get_object_or_404
from django.utils.html import format_html
from django.contrib import messages
from django.db.models import Count, Q
from datetime import timedelta
from dateutil.relativedelta import relativedelta
from .models import Offering, Workshop
from .forms import WorkshopRecurrenceForm
from unfold.admin import ModelAdmin

# --- INLINES ---

class CoachAssignmentInline(admin.TabularInline):
    model = Offering.coaches.through
    extra = 1
    verbose_name = "Coach Assignment"
    verbose_name_plural = "Coach Assignments"
    autocomplete_fields = ('coachprofile',) # Requires search_fields on CoachProfileAdmin

# --- MODEL ADMINS ---

@admin.register(Offering)
class OfferingAdmin(ModelAdmin):
    list_display = ('name', 'duration_display', 'price', 'active_status', 'coach_count')
    list_filter = ('active_status', 'duration_type', 'is_whole_day')
    search_fields = ['name', 'description']
    readonly_fields = ('slug', 'created_at', 'updated_at', 'created_by', 'updated_by')    
    inlines = [CoachAssignmentInline]
    exclude = ('coaches',) # Manage via inline to prevent massive multiselect box loading

    def get_queryset(self, request):
        return super().get_queryset(request).prefetch_related('coaches')

    @admin.display(description='Duration')
    def duration_display(self, obj):
        return obj.display_length

    @admin.display(description='Coaches Assigned')
    def coach_count(self, obj): # Renamed from 'Coaches' to 'Coaches Assigned'
        return obj.coaches.count()

    fieldsets = (
        ('Service Details', {
            'fields': ('name', 'slug', 'description', 'active_status')
        }),
        ('Pricing & Structure', {
            'fields': ('price', 'duration_type', 'total_length_units', 'session_length_minutes', 'total_number_of_sessions', 'is_whole_day')
        }),
        ('Financials', {
            'fields': ('coach_revenue_share', 'referral_commission_type', 'referral_commission_value'),
            'classes': ('collapse',),
        }),
        ('Audit', {
            'fields': ('created_by', 'created_at', 'updated_by', 'updated_at'),
            'classes': ('collapse',),
        }),
    )

    def save_model(self, request, obj, form, change):
        if not change:
            obj.created_by = request.user
        obj.updated_by = request.user
        super().save_model(request, obj, form, change)

@admin.register(Workshop)
class WorkshopAdmin(ModelAdmin):
    list_display = ('name', 'coach_link', 'date', 'price', 'occupancy_bar', 'revenue_display', 'active_status')
    list_editable = ('active_status',)
    list_filter = ('active_status', 'is_free', 'date', 'coach')
    search_fields = ('name', 'coach__user__email', 'coach__user__last_name')
    readonly_fields = ('display_slug', 'created_at', 'updated_at', 'created_by', 'updated_by')
    autocomplete_fields = ('coach',) # Critical for usability if you have many coaches
    list_select_related = ('coach', 'coach__user')    
    date_hierarchy = 'date'
    actions = ['duplicate_workshop_action']

    @admin.action(description="Repeat/Duplicate selected workshop")
    def duplicate_workshop_action(self, request, queryset):
        if queryset.count() != 1:
            self.message_user(request, "Please select exactly one workshop to repeat.", level=messages.WARNING)
            return
        return redirect(reverse('admin:coaching_core_workshop_recurrence', args=[queryset.first().id]))

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.annotate(
            booked_count=Count('bookings', filter=Q(bookings__status__in=['BOOKED', 'PENDING_PAYMENT', 'COMPLETED']))
        )

    @admin.display(description='Coach', ordering='coach__user__last_name')
    def coach_link(self, obj):
        return obj.coach.user.get_full_name()

    @admin.display(description='Time')
    def time_range(self, obj):
        return f"{obj.start_time.strftime('%H:%M')} - {obj.end_time.strftime('%H:%M')}"

    @admin.display(description='Occupancy')
    def occupancy_bar(self, obj):
        # Uses the annotated booked_count from get_queryset
        booked = getattr(obj, 'booked_count', 0)
        total = obj.total_attendees
        
        percent = 0
        if total > 0:
            percent = int((booked / total) * 100)
        
        # Tailwind progress bar colors
        color = "bg-green-500"
        if percent > 80: color = "bg-red-500"
        elif percent > 50: color = "bg-yellow-500"
        
        return format_html(
            '''
            <div class="w-full bg-gray-200 rounded-full h-2.5 dark:bg-gray-700 min-w-[100px]">
                <div class="{}" style="width: {}%"></div>
            </div>
            <span class="text-xs text-gray-500">{} / {} ({}%)</span>
            ''',
            color, percent, booked, total, percent
        )

    @admin.display(description='Est. Revenue')
    def revenue_display(self, obj):
        booked = getattr(obj, 'booked_count', 0)
        return f"£{booked * obj.price}"

    @admin.display(description='Slug')
    def display_slug(self, obj):
        return obj.slug

    fieldsets = (
        ('Workshop Info', {
            'fields': ('name', 'display_slug', 'description', 'coach')
        }),
        ('Schedule', {
            'fields': ('date', 'start_time', 'end_time', 'meeting_link')
        }),
        ('Capacity & Pricing', {
            'fields': ('price', 'is_free', 'total_attendees', 'active_status')
        }),
        ('Audit', {
            'fields': ('created_by', 'created_at'),
            'classes': ('collapse',),
        }),
    )

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('<int:workshop_id>/recurrence/', self.admin_site.admin_view(self.recurrence_view), name='coaching_core_workshop_recurrence'),
        ]
        return custom_urls + urls

    def recurrence_view(self, request, workshop_id):
        workshop = get_object_or_404(Workshop, pk=workshop_id)
        if request.method == 'POST':
            form = WorkshopRecurrenceForm(request.POST)
            if form.is_valid():
                freq = form.cleaned_data['frequency']
                count = form.cleaned_data['occurrences']
                
                created_count = 0
                current_date = workshop.date
                
                for i in range(count):
                    if freq == '30':
                        current_date = current_date + relativedelta(months=1)
                    else:
                        current_date = current_date + timedelta(days=int(freq))
                    
                    # Clone
                    Workshop.objects.create(
                        coach=workshop.coach,
                        name=workshop.name,
                        slug=None, # Auto-generate
                        description=workshop.description,
                        price=workshop.price,
                        date=current_date,
                        start_time=workshop.start_time,
                        end_time=workshop.end_time,
                        total_attendees=workshop.total_attendees,
                        is_free=workshop.is_free,
                        active_status=workshop.active_status,
                        created_by=request.user
                    )
                    created_count += 1
                
                self.message_user(request, f"Successfully created {created_count} recurring workshops.")
                return redirect('admin:coaching_core_workshop_changelist')
        else:
            form = WorkshopRecurrenceForm()

        context = {
            'title': f"Repeat Workshop: {workshop.name}",
            'workshop': workshop,
            'form': form,
            'opts': self.model._meta,
            'site_header': self.admin_site.site_header,
            'site_title': self.admin_site.site_title,
        }
        return render(request, 'admin/coaching_core/workshop/recurrence_form.html', context)

    def change_view(self, request, object_id, form_url='', extra_context=None):
        extra_context = extra_context or {}
        extra_context['recurrence_url'] = reverse('admin:coaching_core_workshop_recurrence', args=[object_id])
        return super().change_view(request, object_id, form_url, extra_context=extra_context)