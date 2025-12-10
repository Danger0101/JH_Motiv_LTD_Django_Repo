from django.conf import settings
from django.shortcuts import render, get_object_or_404
from django.views.decorators.http import require_POST
from django.contrib import messages
from django.urls import reverse
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import TemplateView
from django.http import HttpResponse, JsonResponse
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.db.models import Q
from django.template.loader import render_to_string
import logging
from .models import MarketingPreference
from allauth.account.views import LoginView, SignupView, PasswordResetView, PasswordChangeView, PasswordSetView, LogoutView, PasswordResetDoneView, PasswordResetDoneView, EmailView
from allauth.socialaccount.views import ConnectionsView
from cart.utils import get_or_create_cart, get_cart_summary_data
from coaching_booking.models import ClientOfferingEnrollment, SessionBooking, OneSessionFreeOffer
from coaching_core.models import Offering
from accounts.models import CoachProfile 
from gcal.models import GoogleCredentials
from coaching_availability.forms import DateOverrideForm, CoachVacationForm, WeeklyScheduleForm
from django.forms import modelformset_factory
from coaching_availability.models import CoachAvailability, CoachVacation, DateOverride
from django.db import transaction, models
from collections import defaultdict
from django.views import View
from django.contrib.auth import get_user_model
from datetime import timedelta, date, datetime
import json
from decimal import Decimal

logger = logging.getLogger(__name__)

try:
    from weasyprint import HTML
except ImportError:
    HTML = None

# --- FIX IMPORTS HERE ---
try:
    from dreamers.models import Dreamer
except ImportError:
    Dreamer = None

try:
    from products.models import StockItem
except ImportError:
    StockItem = None
    
try:
    from payments.models import Order, CoachingOrder, OrderItem
    from payments.models import Coupon
except ImportError:
    Order = None
    CoachingOrder = None
    OrderItem = None
    Coupon = None
# ------------------------

from coaching_availability.utils import get_coach_available_slots 


class CustomLoginView(LoginView):
    template_name = 'account/login.html'
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        cart = get_or_create_cart(self.request)
        context['summary'] = get_cart_summary_data(cart)
        context['ACCOUNT_ALLOW_REGISTRATION'] = getattr(settings, 'ACCOUNT_ALLOW_REGISTRATION', True) 
        return context

    def form_valid(self, form):
        response = super().form_valid(form)
        if self.request.htmx:
            return HttpResponse(status=204, headers={'HX-Redirect': response.url})
        return response

class CustomSignupView(SignupView):
    template_name = 'account/signup.html'

class CustomPasswordResetView(PasswordResetView):
    template_name = 'account/password_reset.html'

class CustomPasswordChangeView(PasswordChangeView):
    template_name = 'account/password_change.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['base_template'] = 'socialaccount/empty_base.html' if self.request.htmx else 'base.html'
        return context

class CustomPasswordSetView(PasswordSetView):
    template_name = 'account/password_set.html'

class CustomLogoutView(LogoutView):
    template_name = 'account/logout.html'

class CustomEmailView(EmailView):
    template_name = 'account/email.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['base_template'] = 'socialaccount/empty_base.html' if self.request.htmx else 'base.html'
        return context

class CustomPasswordResetDoneView(PasswordResetDoneView):
    template_name = 'account/password_reset_done.html'

class CustomSocialAccountListView(ConnectionsView):
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if self.request.htmx:
            context['base_template'] = 'socialaccount/empty_base.html'
        else:
            context['base_template'] = 'base.html'
        return context

class ProfileView(LoginRequiredMixin, TemplateView):
    template_name = 'account/profile.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # --- COACHING DASHBOARD DATA ---
        context['coach_upcoming_sessions'] = []
        context['pending_taster_requests'] = [] # Initialize

        if hasattr(self.request.user, 'coach_profile'):
            coach_profile = self.request.user.coach_profile
            # ... existing session query ...
            context['coach_upcoming_sessions'] = SessionBooking.objects.filter(
                coach=coach_profile,
                start_datetime__gte=timezone.now(),
                status__in=['BOOKED', 'RESCHEDULED']
            ).select_related('client').order_by('start_datetime')

            # Fetch Pending Taster Requests
            context['pending_taster_requests'] = OneSessionFreeOffer.objects.filter(
                coach=coach_profile,
                is_approved=False,
                is_redeemed=False,
                redemption_deadline__gte=timezone.now()
            ).select_related('client')

        # For Client: My Taster Status (Already accessible via user.free_offers.all in template, 
        # but explicitly adding it can be cleaner)
        context['my_taster_status'] = OneSessionFreeOffer.objects.filter(
            client=self.request.user
        ).order_by('-date_offered').first()

        # Initialized as empty; loaded via HTMX
        context['coach_clients'] = []
        
        # --- STAFF DASHBOARD METRICS ---
        context['is_staff'] = self.request.user.is_staff
        if self.request.user.is_staff:
            now = timezone.now()
            last_30_days_start = now.replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=29)
            last_7_days = now - timedelta(days=7)

            # 1. Financial Pulse (Last 30 Days Revenue)
            retail_revenue = Decimal('0.00')
            coaching_revenue = Decimal('0.00')

            if Order:
                retail_revenue = Order.objects.filter(
                    created_at__gte=last_30_days_start,
                    status__in=['paid', 'shipped', 'delivered']
                ).aggregate(total=models.Sum('total_paid'))['total'] or Decimal('0.00')

            if CoachingOrder:
                coaching_revenue = CoachingOrder.objects.filter(
                    created_at__gte=last_30_days_start
                ).exclude(payout_status='void').aggregate(total=models.Sum('amount_gross'))['total'] or Decimal('0.00')

            context['staff_30d_revenue'] = retail_revenue + coaching_revenue

            # --- NEW: Chart Data ---
            daily_revenue = { (last_30_days_start + timedelta(days=i)).date(): Decimal('0.00') for i in range(30) }

            if Order:
                retail_daily = Order.objects.filter(
                    created_at__gte=last_30_days_start,
                    status__in=['paid', 'shipped', 'delivered']
                ).extra(
                    select={'day': 'date(created_at)'}
                ).values('day').annotate(daily_total=models.Sum('total_paid'))
                for entry in retail_daily:
                    day = entry['day']
                    if isinstance(day, str): day = datetime.strptime(day, '%Y-%m-%d').date()
                    if day in daily_revenue: daily_revenue[day] += entry['daily_total']

            if CoachingOrder:
                coaching_daily = CoachingOrder.objects.filter(
                    created_at__gte=last_30_days_start
                ).exclude(payout_status='void').extra(
                    select={'day': 'date(created_at)'}
                ).values('day').annotate(daily_total=models.Sum('amount_gross'))
                for entry in coaching_daily:
                    day = entry['day']
                    if isinstance(day, str): day = datetime.strptime(day, '%Y-%m-%d').date()
                    if day in daily_revenue: daily_revenue[day] += entry['daily_total']

            context['revenue_chart_labels'] = json.dumps([d.strftime('%b %d') for d in daily_revenue.keys()])
            context['revenue_chart_data'] = json.dumps([float(v) for v in daily_revenue.values()])

            # 2. Growth Pulse (New Users Last 7 Days)
            context['staff_new_users_7d'] = get_user_model().objects.filter(date_joined__gte=last_7_days).count()

            # 3. Operational Pulse (Active Coaching Clients)
            if ClientOfferingEnrollment:
                context['staff_active_clients'] = ClientOfferingEnrollment.objects.filter(is_active=True).count()

            # 4. Inventory Risks (Low Stock Items)
            if StockItem:
                # Find variants with < 5 items in their pool
                low_stock_qs = StockItem.objects.filter(quantity__lt=5).select_related('variant', 'variant__product')
                context['staff_low_stock_count'] = low_stock_qs.count()
                context['staff_low_stock_items'] = low_stock_qs[:5] # Show top 5 risks

            # 5. Recent Orders (Existing logic, ensured)
            if Dreamer:
                context['staff_dreamer_count'] = Dreamer.objects.count()

            # 6. Unpaid Commissions
            if CoachingOrder:
                unpaid_totals = CoachingOrder.objects.filter(payout_status='unpaid').aggregate(
                    coach_total=models.Sum('amount_coach'), referrer_total=models.Sum('amount_referrer')
                )
                context['staff_unpaid_commissions'] = (unpaid_totals['coach_total'] or Decimal('0.00')) + (unpaid_totals['referrer_total'] or Decimal('0.00'))

            if Order:
                context['staff_recent_orders'] = Order.objects.select_related('user').order_by('-created_at')[:5]

        # --- "My Payouts" for Coach/Dreamer ---
        is_coach_profile = hasattr(self.request.user, 'coach_profile')
        is_dreamer_profile = hasattr(self.request.user, 'dreamer_profile')
        context['has_earnings_profile'] = is_coach_profile or is_dreamer_profile

        total_unpaid_coach = Decimal('0.00')
        total_unpaid_referrer = Decimal('0.00')
        
        if is_coach_profile and CoachingOrder:
            coach_unpaid = CoachingOrder.objects.filter(
                enrollment__coach=self.request.user.coach_profile, 
                payout_status='unpaid'
            ).aggregate(total=models.Sum('amount_coach'))['total'] or Decimal('0.00')
            total_unpaid_coach = coach_unpaid

        if is_dreamer_profile and CoachingOrder:
            ref_unpaid = CoachingOrder.objects.filter(
                referrer=self.request.user.dreamer_profile, 
                payout_status='unpaid'
            ).aggregate(total=models.Sum('amount_referrer'))['total'] or Decimal('0.00')
            total_unpaid_referrer = ref_unpaid

        context['my_total_unpaid_earnings'] = total_unpaid_coach + total_unpaid_referrer

        # --- CLIENT ORDER HISTORY ---
        if Order:
            context['ecomm_orders'] = Order.objects.filter(user=self.request.user).order_by('-created_at')
        
        if CoachingOrder:
            # Coaching orders are linked via ClientOfferingEnrollment
            context['coaching_orders'] = CoachingOrder.objects.filter(
                enrollment__client=self.request.user
            ).select_related('enrollment', 'enrollment__offering').order_by('-created_at')

        # --- EXISTING CONTEXT ---
        cart = get_or_create_cart(self.request)
        context['summary'] = get_cart_summary_data(cart)
        
        preference, created = MarketingPreference.objects.get_or_create(user=self.request.user)
        context['marketing_preference'] = preference
        context['user_offerings'] = ClientOfferingEnrollment.objects.filter(client=self.request.user).order_by('-enrolled_on')

        context['is_coach'] = self.request.user.is_coach
        
        google_calendar_connected = False
        if self.request.user.is_coach:
            try:
                if hasattr(self.request.user, 'coach_profile'):
                    google_calendar_connected = GoogleCredentials.objects.filter(coach=self.request.user.coach_profile).exists()
            except Exception:
                pass 
        context['google_calendar_connected'] = google_calendar_connected

        context['weekly_schedule_formset'] = None
        context['vacation_form'] = None
        context['override_form'] = None
        context['days_of_week'] = None

        if hasattr(self.request.user, 'coach_profile'):
            coach_profile = self.request.user.coach_profile
            WeeklyScheduleFormSet = modelformset_factory(
                CoachAvailability,
                form=WeeklyScheduleForm,
                extra=0,
                can_delete=True
            )
            queryset = CoachAvailability.objects.filter(coach=self.request.user).order_by('day_of_week')
            context['weekly_schedule_formset'] = WeeklyScheduleFormSet(queryset=queryset)
            context['vacation_form'] = CoachVacationForm()
            context['override_form'] = DateOverrideForm()
            context['days_of_week'] = CoachAvailability.DAYS_OF_WEEK

        context['available_credits'] = ClientOfferingEnrollment.objects.filter(
            client=self.request.user,
            remaining_sessions__gt=0,
            is_active=True,
            expiration_date__gte=timezone.now()
        ).order_by('-enrolled_on')

        # --- NEW: "My Rewards" Wallet ---
        now = timezone.now()
        # 1. Public, active coupons that are not user-specific
        public_coupons = Coupon.objects.filter(
            active=True, valid_from__lte=now, valid_to__gte=now, user_specific=None
        )
        # 2. Coupons specifically assigned to this user
        user_specific_coupons = Coupon.objects.filter(
            active=True, valid_from__lte=now, valid_to__gte=now, user_specific=self.request.user
        )
        # Combine and remove duplicates
        context['my_coupons'] = list(set(list(public_coupons) + list(user_specific_coupons)))
        # You might want to add logic here to exclude coupons the user has already used.
        # For example: .exclude(usages__user=self.request.user)
        
        context['active_tab'] = 'account'
        return context

@login_required
def update_marketing_preference(request):
    if request.method == 'POST':
        is_subscribed = request.POST.get('is_subscribed') == 'on' 
        preference, created = MarketingPreference.objects.get_or_create(user=request.user)
        
        # --- ADD THIS LOGIC ---
        if is_subscribed and not preference.is_subscribed:
            # If they are turning it ON, record the timestamp
            # Ensure your model has a 'subscribed_at' field, or add it to models.py first
            preference.subscribed_at = timezone.now() 
        # ----------------------

        preference.is_subscribed = is_subscribed
        preference.save()
        return render(request, 'account/partials/marketing_status_fragment.html', 
                      {'marketing_preference': preference})
    return HttpResponse("Invalid request", status=400)

# HTMX Profile Views
@login_required
def profile_offerings_partial(request):
    user_offerings = ClientOfferingEnrollment.objects.filter(client=request.user).order_by('-enrolled_on')
    available_credits = ClientOfferingEnrollment.objects.filter(
        client=request.user,
        remaining_sessions__gt=0,
        is_active=True,
        expiration_date__gte=timezone.now().date()
    ).order_by('-enrolled_on')
    return render(request, 'account/partials/profile_offerings_list.html', {
        'user_offerings': user_offerings,
        'available_credits': available_credits,
        'active_tab': 'offerings'
    })

@login_required
def profile_bookings_partial(request):
    now = timezone.now()
    active_tab = request.GET.get('tab', 'upcoming')
    bookings_qs = SessionBooking.objects.filter(client=request.user)

    if active_tab == 'upcoming':
        bookings_list = bookings_qs.filter(
            status__in=['BOOKED', 'RESCHEDULED'],
            start_datetime__gte=now
        ).order_by('start_datetime')
    elif active_tab == 'past':
        bookings_list = bookings_qs.filter(
            Q(status='COMPLETED') |
            Q(status__in=['BOOKED', 'RESCHEDULED'], start_datetime__lt=now)
        ).order_by('-start_datetime')
    elif active_tab == 'canceled':
        bookings_list = bookings_qs.filter(status='CANCELED').order_by('-start_datetime')
    else:
        active_tab = 'upcoming'
        bookings_list = bookings_qs.filter(
            status__in=['BOOKED', 'RESCHEDULED'],
            start_datetime__gte=now
        ).order_by('start_datetime')

    paginator = Paginator(bookings_list, 10)
    page_number = request.GET.get('page')
    user_bookings_page = paginator.get_page(page_number)

    context = {
        'user_bookings_page': user_bookings_page,
        'active_tab': active_tab,
    }
    return render(request, 'account/partials/_booking_list.html', context)

@login_required
def get_coaches_for_offering(request):
    enrollment_id_str = request.GET.get('enrollment_id')
    html_options = '<option value="">-- Select a Coach --</option>'

    if enrollment_id_str:
        try:
            enrollment_id = int(enrollment_id_str)
            enrollment = ClientOfferingEnrollment.objects.get(id=enrollment_id, client=request.user)
            
            if enrollment.coach:
                coaches_to_display = [enrollment.coach]
            else:
                coaches_to_display = enrollment.offering.coaches.filter(
                    user__is_active=True, 
                    is_available_for_new_clients=True
                ).distinct()
            
            for coach in coaches_to_display:
                html_options += f'<option value="{coach.id}">{coach.user.get_full_name() or coach.user.username}</option>'

        except (ValueError, ClientOfferingEnrollment.DoesNotExist):
            pass
    
    return HttpResponse(html_options)

@login_required
def coach_clients_partial(request):
    # Ensure user is a coach
    if not hasattr(request.user, 'coach_profile'):
        return HttpResponse("Unauthorized", status=401)

    coach_profile = request.user.coach_profile
    now = timezone.now()
    
    # 1. Enrollments explicitly assigned to this coach
    direct_query = Q(coach=coach_profile) & (
        Q(is_active=True) | 
        Q(expiration_date__gte=now)
    )

    # 2. Enrollments linked via upcoming sessions
    session_enrollment_ids = SessionBooking.objects.filter(
        coach=coach_profile,
        start_datetime__gte=now,
        status__in=['BOOKED', 'RESCHEDULED'],
        enrollment__isnull=False
    ).values_list('enrollment_id', flat=True).distinct()

    implied_query = Q(id__in=session_enrollment_ids) & Q(is_active=True)

    # Combine queries
    client_enrollments_qs = ClientOfferingEnrollment.objects.filter(
        direct_query | implied_query
    ).distinct().select_related('client', 'offering').order_by('client__last_name')

    # Pagination
    paginator = Paginator(client_enrollments_qs, 10) 
    page_number = request.GET.get('page')
    coach_clients_page = paginator.get_page(page_number)

    context = {
        'coach_clients_page': coach_clients_page,
    }
    return render(request, 'account/partials/_coach_clients_list.html', context)

@login_required
def generate_invoice_pdf(request, order_id):
    """
    Generates a PDF invoice for a given e-commerce or coaching order.
    Users can only access their own invoices, unless they are staff.
    """
    order = None
    coaching_order = None
    order_type = ''

    if Order:
        try:
            possible_order = Order.objects.select_related('user').prefetch_related('items__variant__product').get(id=order_id)
            if possible_order.user == request.user or request.user.is_staff:
                order = possible_order
                order_type = 'E-commerce'
        except Order.DoesNotExist:
            pass

    if not order and CoachingOrder:
        try:
            possible_coaching_order = CoachingOrder.objects.select_related('enrollment__client', 'enrollment__offering').get(id=order_id)
            if possible_coaching_order.enrollment.client == request.user or request.user.is_staff:
                coaching_order = possible_coaching_order
                order_type = 'Coaching'
        except CoachingOrder.DoesNotExist:
            pass

    if not order and not coaching_order:
        messages.error(request, "Invoice not found or you do not have permission to view it.")
        return HttpResponse("Order not found or unauthorized", status=404)

    # --- Calculate totals for the invoice ---
    if order:
        try:
            order_items = order.items.all()
            for item in order_items:
                item.line_total = item.price * item.quantity

            subtotal = sum(item.line_total for item in order_items)
            discount = order.discount_amount or Decimal('0.00')
            grand_total = order.total_paid
            delivery_cost = grand_total - (subtotal - discount)

            order.subtotal = subtotal
            order.delivery_cost = delivery_cost
            order.grand_total = grand_total
            order.total_before_vat = subtotal - discount + delivery_cost
            order.vat_amount = Decimal('0.00')

        except Exception as e:
            messages.error(request, f"Could not calculate all order totals: {e}")
            return HttpResponse("Error generating invoice data.", status=500)

    elif coaching_order:
        coaching_order.total_before_vat = coaching_order.total_paid
        coaching_order.vat_amount = Decimal('0.00')
        coaching_order.grand_total = coaching_order.total_paid


    # Prepare context for the template
    context = {
        'order': order,
        'coaching_order': coaching_order,
        'order_type': order_type,
        'user': request.user,
    }

    # Render HTML template to a string
    html_string = render_to_string('account/invoice_template.html', context)

    if not HTML:
        messages.error(request, "Could not generate PDF invoice. The PDF generation service is currently unavailable. Please contact support.")
        return HttpResponse("PDF generation service is unavailable.", status=500)

    # Generate PDF
    html = HTML(string=html_string, base_url=request.build_absolute_uri('/'))
    pdf = html.write_pdf()

    # Create HTTP response to trigger download
    response = HttpResponse(pdf, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="invoice_{order_id}.pdf"'
    
    return response

from django.contrib.admin.views.decorators import staff_member_required

@staff_member_required
def staff_update_order(request, order_id):
    """
    HTMX view to handle updating order status and shipping info from the staff profile.
    """
    order = get_object_or_404(Order, id=order_id)

    if request.method == "POST":
        # Update fields from the form
        order.status = request.POST.get('status', order.status)
        order.carrier = request.POST.get('carrier', order.carrier)
        order.tracking_number = request.POST.get('tracking_number', order.tracking_number)
        order.tracking_url = request.POST.get('tracking_url', order.tracking_url)
        order.save()
        
        # Return the read-only row with updated info
        return render(request, 'account/partials/staff_order_row.html', {'order': order})

    # GET request returns the edit form
    return render(request, 'account/partials/staff_order_form.html', {'order': order})


@staff_member_required
def staff_get_order_row(request, order_id):
    """
    HTMX view to get a single, read-only order row. Used for canceling an edit.
    """
    order = get_object_or_404(Order, id=order_id)
    return render(request, 'account/partials/staff_order_row.html', {'order': order})


@staff_member_required
def staff_customer_lookup(request):
    """
    HTMX view for searching users and displaying their mini-CRM profile.
    """
    User = get_user_model()
    query = request.GET.get('q', '')
    user_id = request.GET.get('user_id')

    # 1. HANDLE DETAIL VIEW (When a user is clicked)
    if user_id:
        customer = get_object_or_404(User, id=user_id)
        
        # --- ADD THIS LOGGING LINE ---
        logger.info(f"AUDIT: Staff member {request.user.id} ({request.user.email}) accessed profile of customer {customer.id} ({customer.email})")
        # -----------------------------

        # Fetch key data
        recent_orders = Order.objects.filter(user=customer).order_by('-created_at')[:5]
        active_enrollments = ClientOfferingEnrollment.objects.filter(
            client=customer, 
            is_active=True
        ).select_related('offering')
        
        context = {
            'customer': customer,
            'recent_orders': recent_orders,
            'active_enrollments': active_enrollments,
        }
        return render(request, 'account/partials/staff_customer_detail.html', context)

    # 2. HANDLE SEARCH (As you type)
    if query:
        results = User.objects.filter(
            Q(email__icontains=query) | 
            Q(first_name__icontains=query) | 
            Q(last_name__icontains=query) |
            Q(username__icontains=query)
        ).exclude(is_staff=True)[:10] # Exclude staff to keep it clean, limit to 10
        
        return render(request, 'account/partials/staff_customer_search_results.html', {'results': results})

    return HttpResponse("") # Return nothing if no query