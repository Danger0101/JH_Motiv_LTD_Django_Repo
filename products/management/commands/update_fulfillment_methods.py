from django.core.management.base import BaseCommand
from products.models import Product

class Command(BaseCommand):
    help = 'Updates fulfillment_method for existing products based on type, Printful ID, and name keywords.'

    def handle(self, *args, **options):
        # Keywords derived from shipping_utils.py that indicate Printful fulfillment
        printful_keywords = [
            't-shirt', 'shirt', 'tank', 'crop', 'hoodie', 'sweat', 'jacket', 
            'pant', 'jogger', 'legging', 'bag', 'tote', 'hat', 'beanie', 
            'mug', 'bottle', 'sticker', 'poster', 'canvas'
        ]

        self.stdout.write("Starting update of product fulfillment methods...")
        
        updated_count = 0
        products = Product.objects.all()

        for product in products:
            original_method = product.fulfillment_method
            new_method = original_method
            reason = None

            # 1. Check Product Type (Digital/Service)
            if product.product_type in ['digital', 'service']:
                new_method = 'digital'
                reason = f"Type is '{product.product_type}'"

            # 2. Check for Printful ID (Definitive Printful)
            elif product.printful_product_id:
                new_method = 'printful'
                reason = "Has Printful ID"

            # 3. Check Name Keywords (Heuristic for Printful)
            # Only apply if currently 'local' (default) to avoid overriding manual overrides
            elif original_method == 'local':
                name_lower = product.name.lower()
                for keyword in printful_keywords:
                    if keyword in name_lower:
                        new_method = 'printful'
                        reason = f"Name contains '{keyword}'"
                        break
            
            # Apply Change
            if new_method != original_method:
                product.fulfillment_method = new_method
                product.save(update_fields=['fulfillment_method'])
                self.stdout.write(f"Updated '{product.name}': {original_method} -> {new_method} ({reason})")
                updated_count += 1

        self.stdout.write(self.style.SUCCESS(f"Update complete. Modified {updated_count} products."))