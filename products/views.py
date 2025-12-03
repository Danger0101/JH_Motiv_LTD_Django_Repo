import json
from django.views.generic import ListView, DetailView
from .models import Product, Variant # Ensure Variant is imported

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
        """Helper function to map color name to a hex code for display."""
        # --- IMPORTANT: Map your actual colors to a hex code here ---
        color_map = {
            'Red': '#EF4444',
            'Blue': '#3B82F6',
            'Black': '#1F2937',
            'White': '#F9FAFB', # Use a very light gray border for visibility
            'Green': '#10B981',
            'Yellow': '#FACC15',
        }
        # Fallback color for unmapped names
        return color_map.get(color_name, '#9CA3AF') 

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
            color = variant.color
            size = variant.size
            
            # Skip variants missing required options, or variants with no StockPool assigned
            if not color or not size:
                continue

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

import hmac
import hashlib
from django.conf import settings
from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from payments.models import Order
from core.email_utils import send_transactional_email

@csrf_exempt
@require_POST
def printful_webhook(request):
    """
    Handles webhooks from Printful, specifically for shipping confirmations.
    """
    payload = request.body
    signature = request.headers.get('X-PF-Signature')

    if not signature:
        return HttpResponse("Signature header missing", status=401)

    secret = getattr(settings, 'PRINTFUL_WEBHOOK_SECRET', '').encode('utf-8')
    if not secret:
        return HttpResponse("Printful webhook secret not configured.", status=500)

    computed_signature = hmac.new(secret, payload, hashlib.sha256).hexdigest()

    if not hmac.compare_digest(computed_signature, signature):
        return HttpResponse("Invalid signature", status=401)

    try:
        event_data = json.loads(payload)
        event_type = event_data.get('type')

        if event_type == 'package_shipped':
            order_data = event_data.get('data', {}).get('order', {})
            printful_order_id = order_data.get('id')
            
            if not printful_order_id:
                return HttpResponse("Missing Printful order ID in payload.", status=400)

            try:
                order = Order.objects.get(printful_order_id=printful_order_id)
                
                # Update order status
                order.printful_order_status = 'shipped'
                order.save()

                # Send shipping confirmation email
                shipment_data = event_data.get('data', {}).get('shipment', {})
                tracking_url = shipment_data.get('tracking_url')
                
                customer_email = order.email
                if not customer_email:
                    print(f"Cannot send shipping confirmation for order {order.id}: no email found.")
                    return JsonResponse({"status": "success", "message": "Webhook received, but no email for order."})

                email_context = {
                    'order': order,
                    'tracking_url': tracking_url,
                    'user': order.user,
                }
                
                send_transactional_email(
                    recipient_email=customer_email,
                    subject=f"Your Order #{order.id} Has Shipped!",
                    template_name='emails/shipping_confirmation.html',
                    context=email_context
                )

                print(f"SUCCESS: Shipping confirmation email sent for Order {order.id}")

            except Order.DoesNotExist:
                return HttpResponse(f"Order with Printful ID {printful_order_id} not found.", status=404)

        return JsonResponse({"status": "success", "message": "Webhook received"})

    except json.JSONDecodeError:
        return HttpResponse("Invalid JSON payload", status=400)
    except Exception as e:
        print(f"Error processing Printful webhook: {e}")
        return HttpResponse("Internal server error", status=500)