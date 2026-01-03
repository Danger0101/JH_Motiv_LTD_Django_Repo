import json
import logging
import hmac
import hashlib
import time # For development demonstration of loading spinner
from django.conf import settings
from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.views.generic import ListView, DetailView
from django.db.models import Q, Min
from .models import Product, Variant
from payments.models import Order
from core.email_utils import send_transactional_email

# Set up logging
logger = logging.getLogger(__name__)

class ProductListView(ListView):
    model = Product
    template_name = 'products/product_list.html'
    context_object_name = 'products'
    
    def get_queryset(self):
        queryset = Product.objects.filter(is_active=True)
        search_query = self.request.GET.get('q', '')
        if search_query:
            queryset = queryset.filter(
                Q(name__icontains=search_query) | 
                Q(description__icontains=search_query)
            )
            
        # Sorting Logic
        sort_by = self.request.GET.get('sort', 'newest')
        
        if sort_by == 'price_asc':
            queryset = queryset.annotate(min_price=Min('variants__price')).order_by('min_price')
        elif sort_by == 'price_desc':
            queryset = queryset.annotate(min_price=Min('variants__price')).order_by('-min_price')
        elif sort_by == 'name_asc':
            queryset = queryset.order_by('name')
        elif sort_by == 'name_desc':
            queryset = queryset.order_by('-name')
        elif sort_by == 'oldest':
            queryset = queryset.order_by('created_at')
        else: # Default to newest
            queryset = queryset.order_by('-created_at')
            
        return queryset

    def get_paginate_by(self, queryset):
        per_page = self.request.GET.get('per_page', '12')
        return int(per_page) if per_page.isdigit() else 12

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['search_query'] = self.request.GET.get('q', '')
        context['per_page'] = str(self.get_paginate_by(self.object_list))
        context['current_sort'] = self.request.GET.get('sort', 'newest')
        return context

    def render_to_response(self, context, **response_kwargs):
        if self.request.headers.get('HX-Request'):
            if settings.DEBUG:
                time.sleep(0.5)
            
            # Switch the template to the partial for HTMX requests
            self.template_name = 'products/partials/product_list_partial.html'
            
        # Call super() which will use self.template_name internally
        return super().render_to_response(context, **response_kwargs)

# ----------------------------------------------------------------------

class ProductDetailView(DetailView):
    model = Product
    template_name = 'products/product_detail.html'
    context_object_name = 'product'

    def get_color_hex(self, color_name):
        """Helper function to map Printful color names to hex codes."""
        color_map = {
            # Basics
            'White': '#FFFFFF',
            'Black': '#111111',
            'Red': '#D32F2F',
            'Blue': '#1976D2',
            'Navy': '#0D47A1',
            'Green': '#388E3C',
            'Yellow': '#FBC02D',
            'Orange': '#F57C00',
            'Purple': '#7B1FA2',
            'Pink': '#E91E63',
            'Grey': '#9E9E9E',
            'Gray': '#9E9E9E',
            'Dark Heather': '#424242',
            'Sport Grey': '#BDBDBD',
            'Heather Grey': '#9E9E9E',
            'Royal': '#1565C0',
            'Maroon': '#880E4F',
            'Cardinal': '#B71C1C',
            'Charcoal': '#37474F',
            'Forest Green': '#1B5E20',
            'Military Green': '#558B2F',
            'Irish Green': '#4CAF50',
            'Daisy': '#FFEB3B',
            'Gold': '#FFC107',
            'Light Blue': '#81D4FA',
            'Carolina Blue': '#4FC3F7',
            'Sand': '#D7CCC8',
            'Heliconia': '#EC407A',
            'Azalea': '#F48FB1',
            'Chestnut': '#795548',
            'Dark Chocolate': '#3E2723',
            'Light Pink': '#F8BBD0',
            'Lime': '#CDDC39',
            'Indigo Blue': '#3F51B5',
            'Sapphire': '#0288D1',
            'Ash': '#D3D3D3',
        }
        
        clean_name = color_name.strip()
        
        if clean_name not in color_map:
            if "Heather" in clean_name: return '#757575'
            if "Navy" in clean_name: return '#0D47A1'
            if "Black" in clean_name: return '#212121'
            if "Red" in clean_name: return '#D32F2F'
            if "Blue" in clean_name: return '#1976D2'
        
        return color_map.get(clean_name, '#E0E0E0')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        product = context['product']
        
        context['unique_colors'] = []
        context['unique_sizes'] = []
        context['unique_names'] = []
        context['variant_lookup_json'] = json.dumps({})
        
        # Dice Rating Helpers
        context['filled_dice'] = range(product.dice_rating)
        context['empty_dice'] = range(5 - product.dice_rating)
        
        if not product.variants.exists():
            return context

        unique_colors = set()
        unique_sizes = set()
        variant_map = {}
        unique_names = set()
        
        has_real_colors = False
        has_real_sizes = False
        has_named_variants = False
        
        for variant in product.variants.all():
            if variant.color: has_real_colors = True
            if variant.size: has_real_sizes = True
            if variant.name: has_named_variants = True

            color = variant.color or "Default"
            size = variant.size or "One Size"
            name = variant.name or ""
            is_in_stock = variant.is_available() if hasattr(variant, 'is_available') else True

            lookup_key = name if name else f"{color}_{size}"
            
            variant_map[lookup_key] = {
                'id': variant.id,
                'price': float(variant.price),
                'in_stock': is_in_stock,
                'name': name
            }
            
            if color and color != "Default":
                color_hex = self.get_color_hex(color)
                unique_colors.add((color, color_hex)) 
            
            if size and size != "One Size":
                unique_sizes.add(size)
            
            if name:
                unique_names.add(name)
        
        context['unique_colors'] = sorted(list(unique_colors), key=lambda x: x[0])
        context['unique_sizes'] = sorted(list(unique_sizes))
        context['unique_names'] = sorted(list(unique_names))
        context['variant_lookup_json'] = json.dumps(variant_map)
        context['show_color_selector'] = has_real_colors
        context['show_size_selector'] = has_real_sizes
        context['show_name_selector'] = has_named_variants

        return context

# ----------------------------------------------------------------------
# WEBHOOK VIEW (V2 COMPATIBLE - WITH SIGNATURE CHECK)
# ----------------------------------------------------------------------

@csrf_exempt
@require_POST
def printful_webhook(request):
    """
    Handles webhooks from Printful (API V2) with signature verification.
    """
    signature_header = request.headers.get('X-Printful-Signature')
    if not signature_header:
        logger.warning("Printful webhook missing signature header.")
        return HttpResponse("Signature header missing.", status=400)

    try:
        secret = settings.PRINTFUL_WEBHOOK_SECRET
        if not secret:
            logger.error("PRINTFUL_WEBHOOK_SECRET is not configured.")
            return HttpResponse("Webhook secret not configured.", status=500)

        # V2 requires HMAC-SHA256 signature verification
        payload = request.body
        expected_signature = hmac.new(
            key=secret.encode('utf-8'),
            msg=payload,
            digestmod=hashlib.sha256
        ).hexdigest()

        if not hmac.compare_digest(expected_signature, signature_header):
            logger.warning("Invalid Printful webhook signature.")
            return HttpResponse("Invalid signature.", status=403)
            
        event_data = json.loads(payload)
        event_type = event_data.get('type')
        
        logger.info(f"Received verified Printful Webhook: {event_type}")

        if event_type == 'package_shipped':
            order_data = event_data.get('data', {}).get('order', {})
            printful_order_id = str(order_data.get('id'))
            
            if not printful_order_id:
                return HttpResponse("Missing Printful order ID", status=400)

            try:
                order = Order.objects.get(printful_order_id=printful_order_id)
                
                if order.printful_order_status != 'shipped':
                    order.printful_order_status = 'shipped'
                    order.save()

                    # V2 payload for 'package_shipped' is slightly different.
                    # The 'shipment' data is directly inside 'data'.
                    shipment_data = event_data.get('data', {}).get('shipment', {})
                    tracking_number = shipment_data.get('tracking_number')
                    tracking_url = shipment_data.get('tracking_url')
                    carrier = shipment_data.get('carrier')
                    
                    if order.email:
                        email_context = {
                            'order': order,
                            'tracking_number': tracking_number,
                            'tracking_url': tracking_url,
                            'carrier': carrier,
                            'user': order.user,
                            'dashboard_url': "https://jhmotiv.shop/accounts/profile/bookings/" 
                        }
                        
                        send_transactional_email(
                            recipient_email=order.email,
                            subject=f"Order #{order.id} Shipped!",
                            template_name='emails/shipping_confirmation.html',
                            context=email_context
                        )
                        logger.info(f"Sent shipping confirmation for Order #{order.id}")
                    else:
                        logger.warning(f"Order #{order.id} has no email address. Skipping notification.")
                else:
                    logger.info(f"Order #{order.id} was already marked as shipped.")

            except Order.DoesNotExist:
                logger.warning(f"Order not found for Printful ID {printful_order_id}. Ignoring.")
                return JsonResponse({"status": "ignored", "reason": "Order not found"})

        return JsonResponse({"status": "success"})

    except json.JSONDecodeError:
        logger.error("Webhook payload is not valid JSON.")
        return HttpResponse("Invalid JSON", status=400)
    except Exception as e:
        logger.error(f"Webhook Error: {e}", exc_info=True)
        return HttpResponse("Internal server error", status=500)