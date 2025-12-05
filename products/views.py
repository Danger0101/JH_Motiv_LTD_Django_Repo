import json
import hmac
import hashlib
from django.conf import settings
from django.views.generic import ListView, DetailView
from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from .models import Product, Variant # Ensure Variant is imported
from payments.models import Order
from core.email_utils import send_transactional_email

class ProductListView(ListView):
    model = Product
    template_name = 'products/product_list.html'
    context_object_name = 'products'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['search_query'] = self.request.GET.get('q', '')
        context['per_page'] = self.request.GET.get('per_page', '12') # Default to 12 or whatever your default is
        return context

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
            
            # Printful Specifics (Common)
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
        }
        
        clean_name = color_name.strip()
        
        # Fallback smart matching
        if clean_name not in color_map:
            if "Heather" in clean_name: return '#757575'
            if "Navy" in clean_name: return '#0D47A1'
            if "Black" in clean_name: return '#212121'
            if "Red" in clean_name: return '#D32F2F'
            if "Blue" in clean_name: return '#1976D2'
        
        return color_map.get(clean_name, '#E0E0E0') # Default Light Grey

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        product = context['product']
        
        # Initialize default values for the template
        context['unique_colors'] = []
        context['unique_sizes'] = []
        context['variant_lookup_json'] = json.dumps({}) # Set to an empty JSON object
        
        # If there are no variants, there's nothing to process, so return early.
        if not product.variants.exists():
            return context

        unique_colors = set()
        unique_sizes = set()
        variant_map = {} # This will become the JSON lookup table
        
        # 1. Build the Lookup Map and collect unique options
        for variant in product.variants.all():
            color = variant.color or "Default"
            size = variant.size or "One Size"

            # Check stock status using the modular method from the Variant model
            is_in_stock = variant.is_available() 

            # Create the unique key used by Alpine.js: Color_Size
            lookup_key = f"{color}_{size}" 
            
            variant_map[lookup_key] = {
                'id': variant.id,
                'price': float(variant.price), # Use float for easier JS pricing
                'in_stock': is_in_stock 
            }
            
            # Collect unique options
            if color:
                color_hex = self.get_color_hex(color)
                unique_colors.add((color, color_hex)) 
            if size:
                unique_sizes.add(size)
        
        # 2. Add context variables required by the template
        # Convert sets/dicts to JSON-serializable structures
        context['unique_colors'] = sorted(list(unique_colors))
        context['unique_sizes'] = sorted(list(unique_sizes))
        
        # Serialize the lookup map for Alpine.js consumption
        context['variant_lookup_json'] = json.dumps(variant_map)

        return context

# ----------------------------------------------------------------------
# WEBHOOK VIEW
# ----------------------------------------------------------------------

@csrf_exempt
@require_POST
def printful_webhook(request):
    """
    Handles webhooks from Printful.
    Verifies signature and processes 'package_shipped' events.
    """
    payload = request.body
    # Printful sends signature in X-PF-Signature header
    signature = request.headers.get('X-PF-Signature') or request.META.get('HTTP_X_PF_SIGNATURE')

    if not signature:
        return HttpResponse("Signature header missing", status=401)

    secret = getattr(settings, 'PRINTFUL_WEBHOOK_SECRET', '')
    if not secret:
        print("CRITICAL: PRINTFUL_WEBHOOK_SECRET is missing in settings.")
        return HttpResponse("Server configuration error", status=500)

    # Verify Signature
    try:
        # Ensure secret is bytes
        secret_bytes = secret.encode('utf-8')
        computed_signature = hmac.new(secret_bytes, payload, hashlib.sha256).hexdigest()
    except Exception as e:
        print(f"Signature computation error: {e}")
        return HttpResponse("Signature computation failed", status=500)

    if not hmac.compare_digest(computed_signature, signature):
        print(f"Invalid Signature. Received: {signature}, Computed: {computed_signature}")
        return HttpResponse("Invalid signature", status=401)

    try:
        event_data = json.loads(payload)
        event_type = event_data.get('type')
        
        print(f"Received Printful Webhook: {event_type}")

        if event_type == 'package_shipped':
            order_data = event_data.get('data', {}).get('order', {})
            printful_order_id = str(order_data.get('id'))
            
            if not printful_order_id:
                return HttpResponse("Missing Printful order ID", status=400)

            try:
                order = Order.objects.get(printful_order_id=printful_order_id)
                
                # Avoid duplicate emails if already marked shipped
                if order.printful_order_status != 'shipped':
                    order.printful_order_status = 'shipped'
                    order.save()

                    # Get tracking details
                    shipment = event_data.get('data', {}).get('shipment', {})
                    tracking_number = shipment.get('tracking_number')
                    tracking_url = shipment.get('tracking_url')
                    carrier = shipment.get('carrier')
                    
                    if order.email:
                        email_context = {
                            'order': order,
                            'tracking_number': tracking_number,
                            'tracking_url': tracking_url,
                            'carrier': carrier,
                            'user': order.user,
                            'dashboard_url': request.build_absolute_uri('/accounts/profile/orders/')
                        }
                        
                        send_transactional_email(
                            recipient_email=order.email,
                            subject=f"Order #{order.id} Shipped!",
                            template_name='emails/shipping_confirmation.html',
                            context=email_context
                        )
                        print(f"Sent shipping confirmation for Order #{order.id}")
                    else:
                        print(f"Order #{order.id} has no email address. Skipping notification.")
                else:
                    print(f"Order #{order.id} was already marked as shipped.")

            except Order.DoesNotExist:
                print(f"Order not found for Printful ID {printful_order_id}. Ignoring.")
                # Return 200 so Printful stops retrying
                return JsonResponse({"status": "ignored", "reason": "Order not found"})

        return JsonResponse({"status": "success"})

    except json.JSONDecodeError:
        return HttpResponse("Invalid JSON", status=400)
    except Exception as e:
        print(f"Webhook Error: {e}")
        return HttpResponse("Internal server error", status=500)