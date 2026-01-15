import logging
import json
from decimal import Decimal
import stripe

from django.conf import settings
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.db import transaction
from django.core.mail import send_mail

from cart.models import Cart
from coaching_booking.models import ClientOfferingEnrollment, SessionBooking
from coaching_core.models import Offering
from accounts.models import CoachProfile
from awakening.models import FunnelTier # Import FunnelTier to check for perks
from products.models import StockPool
from products.printful_service import PrintfulService
from core.email_utils import send_transactional_email

from .models import Order, Coupon, CouponUsage, CoachingOrder
from .finance_utils import calculate_coaching_split
from .shipping_utils import calculate_cart_shipping

logger = logging.getLogger(__name__)
User = get_user_model()


def handle_ecommerce_checkout(session, request):
    """
    Handles the post-payment logic for an e-commerce cart checkout.
    - Updates order status.
    - Manages stock.
    - Fulfills with Printful.
    - Sends confirmation emails.
    """
    metadata = session.get('metadata', {})
    order_id = metadata.get('order_id')
    if not order_id:
        logger.error("FATAL ERROR in E-commerce Webhook: order_id not found in metadata.")
        return

    try:
        order = Order.objects.select_for_update().get(id=order_id)

        if order.status != Order.STATUS_PENDING:
            logger.info(f"Webhook for order {order_id} already processed. Status: {order.status}")
            return

        # Update Order status and details
        order.status = Order.STATUS_PAID
        order.total_paid = session.amount_total / 100
        order.stripe_checkout_id = session.id

        # Clear coupon from cart
        if order.coupon and metadata.get('cart_id'):
            Cart.objects.filter(id=metadata.get('cart_id')).update(coupon=None)

        # Update guest email
        if not order.user and session.get('customer_details', {}).get('email'):
            order.email = session.get('customer_details', {}).get('email')

        # Update shipping data if needed
        if not order.shipping_data:
            shipping_json = metadata.get('shipping_address_json')
            shipping_data_from_metadata = json.loads(shipping_json) if shipping_json else {}
            if shipping_data_from_metadata:
                order.shipping_data = shipping_data_from_metadata
            else:
                shipping_details = session.get('shipping_details') or {}
                address = shipping_details.get('address') or {}
                order.shipping_data = {
                    'name': shipping_details.get('name'),
                    'address1': address.get('line1'),
                    'address2': address.get('line2'),
                    'city': address.get('city'),
                    'state_code': address.get('state'),
                    'country_code': address.get('country'),
                    'zip': address.get('postal_code'),
                }
        order.save()

        # Record coupon usage
        if order.coupon:
            try:
                coupon = order.coupon.__class__.objects.select_for_update().get(id=order.coupon.id)
                if coupon.usage_limit is not None and coupon.usages.count() >= coupon.usage_limit:
                    logger.warning(f"Coupon {coupon.code} was oversold on Order {order.id}. Usage limit was exceeded.")
                CouponUsage.objects.create(coupon=coupon, order=order, user=order.user, email=order.email)
            except order.coupon.DoesNotExist:
                logger.error(f"Could not log usage for a coupon on Order {order.id} because it was deleted mid-transaction.")

        _fulfill_ecommerce_order(order, request)

    except Order.DoesNotExist:
        logger.error(f"FATAL ERROR in E-commerce Webhook: Order matching ID {order_id} does not exist.")
    except Exception as e:
        logger.critical(f"Order {order_id} processing failed. Error: {e}", exc_info=True)


def handle_payment_intent_checkout(payment_intent, request=None):
    """
    Handles the post-payment logic for the new 2-step checkout (PaymentIntent).
    - Creates the Order from the Cart (since it wasn't created before).
    - Calls fulfillment logic.
    """
    metadata = payment_intent.get('metadata', {})
    cart_id = metadata.get('cart_id')
    user_id = metadata.get('user_id')
    
    # Idempotency Check
    if Order.objects.filter(stripe_checkout_id=payment_intent.id).exists():
        return Order.objects.get(stripe_checkout_id=payment_intent.id)

    try:
        cart = Cart.objects.get(id=cart_id)
    except Cart.DoesNotExist:
        logger.error(f"Cart {cart_id} not found for PaymentIntent {payment_intent.id}")
        return None

    # Extract Shipping Data
    shipping_data = {}
    if payment_intent.get('shipping'):
        shipping = payment_intent.get('shipping')
        address = shipping.get('address', {})
        shipping_data = {
            'name': shipping.get('name'),
            'address1': address.get('line1'),
            'address2': address.get('line2'),
            'city': address.get('city'),
            'state_code': address.get('state'),
            'country_code': address.get('country'),
            'zip': address.get('postal_code'),
        }

    # Determine User and Email
    user = None
    if user_id:
        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            pass
    
    email = payment_intent.get('receipt_email')
    if not email and user:
        email = user.email

    # Create Order
    with transaction.atomic():
        order = Order.objects.create(
            user=user,
            email=email,
            total_paid=Decimal(payment_intent.amount) / 100,
            stripe_checkout_id=payment_intent.id,
            status=Order.STATUS_PAID,
            shipping_data=shipping_data,
            coupon=cart.coupon,
            coupon_code_snapshot=cart.coupon.code if cart.coupon else None,
            # Note: discount_amount is not easily available on the cart object directly 
            # without recalculating, but we can infer or leave as 0 for now if not critical.
            # Ideally, we should store this in metadata or calculate it.
        )

        # Create Order Items
        from .models import OrderItem
        for item in cart.items.all():
            OrderItem.objects.create(
                order=order,
                variant=item.variant,
                price=item.variant.price,
                quantity=item.quantity
            )

        # Record Coupon Usage
        if order.coupon:
            CouponUsage.objects.create(coupon=order.coupon, order=order, user=order.user, email=order.email)

        # Run Fulfillment
        _fulfill_ecommerce_order(order, request, original_cart_id=cart.id)
        
        return order


def _fulfill_ecommerce_order(order, request=None, original_cart_id=None):
    """
    Shared logic for stock deduction, Printful sync, and emails.
    """
    try:
        printful_items = []
        # Process items, deduct stock, and prepare Printful order
        for item in order.items.all():
            if item.variant.printful_variant_id:
                printful_items.append({
                    "variant_id": item.variant.printful_variant_id,
                    "quantity": item.quantity,
                })
            if item.variant.product.product_type == 'physical' and item.variant.stock_pool:
                try:
                    pool = StockPool.objects.select_for_update().get(id=item.variant.stock_pool.id)
                    if pool.available_stock < 9000:
                        if pool.available_stock >= item.quantity:
                            pool.available_stock -= item.quantity
                            pool.save()
                        else:
                            logger.critical(f"Oversold {pool.name}. Had {pool.available_stock}, sold {item.quantity}.")
                            pool.available_stock = 0
                            pool.save()
                except StockPool.DoesNotExist:
                    logger.error(f"Error: StockPool not found for variant {item.variant.id}")

        # Clear the original cart
        cart_id = original_cart_id
        if cart_id:
            try:
                original_cart = Cart.objects.get(id=cart_id)
                original_cart.items.all().delete()
                logger.info(f"Cart {cart_id} cleared after order {order.id} completion.")
            except Cart.DoesNotExist:
                pass

        # Handle Printful fulfillment
        if printful_items:
            if getattr(settings, 'PRINTFUL_AUTO_FULFILLMENT', False):
                printful_service = PrintfulService()
                recipient = {
                    "name": order.shipping_data.get('name'),
                    "address1": order.shipping_data.get('address1'),
                    "address2": order.shipping_data.get('address2', ''),
                    "city": order.shipping_data.get('city'),
                    "state_code": order.shipping_data.get('state_code'),
                    "country_code": order.shipping_data.get('country_code'),
                    "zip": order.shipping_data.get('zip'),
                    "email": order.email
                }
                response = printful_service.create_order(recipient, printful_items)
                if 'result' in response and response['result'].get('id'):
                    order.printful_order_id = response['result']['id']
                    order.printful_order_status = response['result']['status']
                else:
                    logger.error(f"Printful Auto-Sync Failed for order {order.id}: {response}")
                    order.printful_order_status = 'failed_auto_sync'
            else:
                order.printful_order_status = 'pending_approval'
            order.save()

        # Send confirmation emails
        customer_email = order.email
        if not customer_email:
            raise ValueError("Customer email not found on order after webhook processing.")

        site_url = getattr(settings, 'SITE_URL', 'https://jhmotiv.com')
        dashboard_url = site_url + (
            reverse('accounts:account_profile') if order.user else reverse('payments:order_detail_guest', args=[order.guest_order_token])
        )

        # Generate a secure invoice download URL
        invoice_download_url = ''
        if order.user:
            invoice_download_url = site_url + reverse('payments:download_invoice', args=[order.id])
        elif order.guest_order_token:
            invoice_download_url = site_url + reverse('payments:download_invoice_guest', args=[order.guest_order_token])

        # Fix: Pass IDs instead of objects to avoid JSON serialization errors in Celery
        email_context = {
            'order_id': order.id, 
            'user_id': order.user.id if order.user else None, 
            'user_email': order.email,
            'dashboard_url': dashboard_url,
            'invoice_download_url': invoice_download_url,
        }

        # --- ADD PERK LINKS FOR AWAKENING FUNNEL ---
        # Check if this order came from the Awakening funnel and add perk links if they exist.
        linked_perks = []
        try:
            # This logic mirrors the order_success view to find the main item.
            main_item = None
            for item in order.items.all():
                if FunnelTier.objects.filter(variant=item.variant, quantity=item.quantity).exists():
                    main_item = item
                    break
            
            if main_item:
                purchased_tier = FunnelTier.objects.get(variant=main_item.variant, quantity=main_item.quantity)
                linked_perks = purchased_tier.perks.filter(link_url__isnull=False).exclude(link_url__exact='')
        except (FunnelTier.DoesNotExist, AttributeError):
            pass # No tier matched or main_item not found.
        
        email_context['linked_perks'] = {
            'items': linked_perks,
            'has_links': bool(linked_perks)
        }

        send_transactional_email(
            recipient_email=customer_email,
            subject=f"Your JH Motiv LTD Order #{order.id} is Confirmed",
            template_name='emails/order_confirmation.html',
            context=email_context
        )
        send_transactional_email(
            recipient_email=customer_email,
            subject=f"Your Payment Receipt for Order #{order.id}",
            template_name='emails/payment_receipt.html',
            context=email_context
        )

    except Exception as e:
        logger.critical(f"Order {order.id} fulfillment failed. Error: {e}", exc_info=True)


def handle_coaching_enrollment(session):
    """
    Handles the post-payment logic for a coaching offering purchase.
    - Creates enrollment and coaching order.
    - Calculates commission splits.
    - Records coupon usage.
    """
    metadata = session.get('metadata', {})
    user_id = metadata.get('user_id')
    offering_id = metadata.get('offering_id')
    coach_id = metadata.get('coach_id')
    total_paid_amount = Decimal(session.amount_total) / Decimal('100')

    try:
        user = User.objects.get(id=user_id)
        offering = Offering.objects.get(id=offering_id)
        
        selected_coach = None
        if coach_id:
            selected_coach = CoachProfile.objects.filter(id=coach_id).first()
        
        # Fallback Validation: Ensure the selected coach is actually associated with this offering.
        if selected_coach and not offering.coaches.filter(id=selected_coach.id).exists():
            warning_msg = f"Webhook Warning: Attempted to enroll user {user_id} with coach {coach_id} who is not in offering {offering_id}. Reverting to default coach."
            logger.warning(warning_msg)
            
            # Notify Admin
            try:
                send_mail(
                    subject="⚠️ Invalid Coach Selection Detected",
                    message=warning_msg,
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[settings.DEFAULT_FROM_EMAIL],
                    fail_silently=True
                )
            except Exception:
                pass

            selected_coach = None # Invalidate selection

        # Fallback: If no coach selected, default to the first one available
        if not selected_coach:
            selected_coach = offering.coaches.first()

        enrollment = ClientOfferingEnrollment.objects.create(
            client=user, 
            offering=offering, 
            coach=selected_coach
        )

        coupon_code = metadata.get('coupon_code')
        referrer = None
        coupon = None
        if coupon_code:
            try:
                coupon = Coupon.objects.get(code__iexact=coupon_code)
                referrer = coupon.affiliate_dreamer
            except Coupon.DoesNotExist:
                pass

        discount_amount = Decimal(metadata.get('discount_amount', '0.00'))

        coaching_order = CoachingOrder.objects.create(
            enrollment=enrollment, referrer=referrer,
            amount_gross=total_paid_amount, stripe_checkout_id=session.id,
            coupon_code=coupon_code, discount_amount=discount_amount
        )

        if coupon:
            CouponUsage.objects.create(coupon=coupon, user=user, email=user.email, coaching_order=coaching_order)

        splits = calculate_coaching_split(total_paid_amount, enrollment.offering, referrer, client=user)
        coaching_order.amount_coach = splits['coach']
        coaching_order.amount_referrer = splits['referrer']
        coaching_order.amount_company = splits['company']
        coaching_order.save()

    except (User.DoesNotExist, Offering.DoesNotExist) as e:
        logger.error(f"FATAL ERROR in Coaching Webhook: Could not find object. {e}. Metadata: {metadata}")
    except Exception as e:
        logger.error(f"FATAL ERROR in Coaching Webhook processing: {e}. Metadata: {metadata}", exc_info=True)


def calculate_coach_earnings(coach, start_date, end_date):
    """
    Calculates earnings for a specific coach based on sessions DELIVERED 
    (Provider) in a given date range.
    """
    earnings_report = {
        'total_earnings': Decimal('0.00'),
        'sessions_count': 0,
        'breakdown': []
    }

    # Query: Find all COMPLETED sessions where this coach was the PROVIDER
    sessions = SessionBooking.objects.filter(
        coach=coach,
        status='COMPLETED',
        start_datetime__date__range=(start_date, end_date)
    ).select_related('enrollment', 'enrollment__offering', 'client', 'offering')

    for session in sessions:
        session_value = Decimal('0.00')
        revenue_share_percentage = Decimal('70.00') # Default fallback

        # A. Get the Raw Value of the Session
        if session.amount_paid > 0:
            # 1. Direct Paid Session (e.g. Drop-in / One-off)
            # amount_paid is usually in cents if using Stripe, convert to standard unit
            session_value = Decimal(session.amount_paid) / 100
            
            if session.offering:
                revenue_share_percentage = session.offering.coach_revenue_share
            elif session.enrollment and session.enrollment.offering:
                 revenue_share_percentage = session.enrollment.offering.coach_revenue_share

        elif session.enrollment:
            # 2. Package Session (Pre-paid)
            # Calculate pro-rated value: Package Price / Total Sessions
            offering = session.enrollment.offering
            if offering.total_number_of_sessions > 0:
                session_value = offering.price / offering.total_number_of_sessions
            
            revenue_share_percentage = offering.coach_revenue_share

        # B. Calculate Coach's Cut
        # Formula: Session Value * (Coach Share / 100)
        coach_cut = session_value * (revenue_share_percentage / 100)
        
        # Rounding (Currency standard)
        coach_cut = coach_cut.quantize(Decimal('0.01'))

        # C. Add to Report
        earnings_report['total_earnings'] += coach_cut
        earnings_report['sessions_count'] += 1
        earnings_report['breakdown'].append({
            'date': session.start_datetime,
            'client': session.client.get_full_name(),
            'type': 'Coverage' if session.is_coverage_session else 'Primary',
            'session_value': session_value,
            'coach_earnings': coach_cut
        })

    return earnings_report

def calculate_coach_earnings_for_period(coach, start_date, end_date):
    """
    Calculates earnings for a specific coach based on sessions DELIVERED 
    (Provider) in a given date range. This ignores who sold the package
    and focuses on who did the work.
    """
    earnings_report = {
        'total_earnings': Decimal('0.00'),
        'sessions_count': 0,
        'breakdown': []
    }

    # Query: Find all COMPLETED sessions where this coach was the PROVIDER
    sessions = SessionBooking.objects.filter(
        coach=coach,
        status='COMPLETED',
        start_datetime__date__range=(start_date, end_date)
    ).select_related('enrollment', 'enrollment__offering', 'client')

    for session in sessions:
        session_value = Decimal('0.00')
        revenue_share_percentage = Decimal('70.00') # Default fallback

        # A. Get the Raw Value of the Session
        if session.amount_paid > 0:
            # 1. Direct Paid Session (e.g. Drop-in / One-off)
            session_value = Decimal(session.amount_paid) / 100
            
            if session.offering:
                revenue_share_percentage = session.offering.coach_revenue_share
            elif session.workshop:
                # Logic for workshop share could go here
                pass

        elif session.enrollment:
            # 2. Package Session (Pre-paid)
            # Calculate pro-rated value: Package Price / Total Sessions
            offering = session.enrollment.offering
            if offering.total_number_of_sessions > 0:
                session_value = offering.price / offering.total_number_of_sessions
            
            revenue_share_percentage = offering.coach_revenue_share

        # B. Calculate Coach's Cut
        # Formula: Session Value * (Coach Share / 100)
        coach_cut = session_value * (revenue_share_percentage / 100)
        
        # Rounding
        coach_cut = coach_cut.quantize(Decimal('0.01'))

        # C. Add to Report
        earnings_report['total_earnings'] += coach_cut
        earnings_report['sessions_count'] += 1
        earnings_report['breakdown'].append({
            'date': session.start_datetime,
            'client': session.client.get_full_name(),
            'type': 'Coverage' if session.is_coverage_session else 'Primary',
            'session_value': session_value,
            'coach_earnings': coach_cut
        })

    return earnings_report