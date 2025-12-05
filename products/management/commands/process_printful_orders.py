from django.core.management.base import BaseCommand
from payments.models import Order
from products.printful_service import PrintfulService
import json

class Command(BaseCommand):
    help = 'Process pending Printful orders (Manual Mode)'

    def add_arguments(self, parser):
        parser.add_argument('--order_id', type=int, help='Process a specific order ID')

    def handle(self, *args, **options):
        service = PrintfulService()
        order_id = options.get('order_id')

        # Filter orders that are waiting for approval or failed previously
        if order_id:
            orders = Order.objects.filter(id=order_id, printful_order_status__in=['pending_approval', 'failed_auto_sync'])
        else:
            orders = Order.objects.filter(printful_order_status__in=['pending_approval', 'failed_auto_sync'])

        if not orders.exists():
            self.stdout.write("No pending Printful orders found.")
            return

        self.stdout.write(f"Found {orders.count()} orders to process...")

        for order in orders:
            self.stdout.write(f"Processing Order #{order.id} ({order.email})")
            
            # Reconstruct Payload
            # NOTE: We need to pull address info. 
            # Ideally, you should save the shipping address to the Order model during webhook.
            # Since the current Order model might not have full address fields, 
            # ensure you update your Order model to store 'shipping_address_json' or similar.
            # FOR NOW: This script assumes you might add that or relies on what's available.
            
            # If you haven't stored address in Order, you can't retry easily without it!
            # Recommendation: Add a JSONField 'shipping_data' to your Order model.
            
            items = []
            for item in order.items.all():
                if item.variant.printful_variant_id:
                    items.append({
                        "variant_id": item.variant.printful_variant_id,
                        "quantity": item.quantity
                    })
            
            if not items:
                self.stdout.write(self.style.WARNING(f"  - No Printful items in Order #{order.id}. Skipping."))
                continue

            # MOCK RECIPIENT DATA (You MUST update Order model to save this from webhook!)
            # For robust looping, you need to save the address payload in the webhook to the DB.
            # Assuming you added a 'shipping_data' JSONField to Order:
            # recipient = order.shipping_data 
            
            # Placeholder warning if data is missing
            self.stdout.write(self.style.ERROR(f"  - Cannot process Order #{order.id}: Shipping data not saved in DB."))
            self.stdout.write(self.style.ERROR(f"  - ACTION REQUIRED: Add 'shipping_data = models.JSONField()' to Order model."))
            
            # UNCOMMENT BELOW ONCE YOU HAVE DATA
            # response = service.create_order(recipient, items)
            # if 'result' in response:
            #     order.printful_order_id = response['result']['id']
            #     order.printful_order_status = 'processed'
            #     order.save()
            #     self.stdout.write(self.style.SUCCESS(f"  - Successfully sent to Printful: ID {order.printful_order_id}"))
            # else:
            #     self.stdout.write(self.style.ERROR(f"  - Failed: {response.get('error')}"))