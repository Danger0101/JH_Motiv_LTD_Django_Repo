from django.core.management.base import BaseCommand
from products.models import Product, Variant, StockPool
from products.printful_service import PrintfulService

class Command(BaseCommand):
    help = 'Syncs products from Printful'

    def handle(self, *args, **kwargs):
        service = PrintfulService()
        printful_products = service.get_store_products()

        for p_data in printful_products:
            # Create or Update Product
            product, created = Product.objects.update_or_create(
                printful_product_id=p_data['id'],
                defaults={
                    'name': p_data['name'],
                    'product_type': 'physical',
                    # You might want to fetch the thumbnail image here too
                }
            )
            
            self.stdout.write(f"Synced Product: {product.name}")

            # Fetch Variants
            variants = service.get_product_variants(p_data['id'])
            for v_data in variants:
                # Create or Update Variant
                Variant.objects.update_or_create(
                    printful_variant_id=v_data['id'],
                    defaults={
                        'product': product,
                        'name': v_data['name'],
                        'price': v_data['retail_price'],
                        'sku': v_data['sku'],
                        # Defaulting to a generic pool or None if you handle stock differently for Printful
                        'stock_pool': None 
                    }
                )
                self.stdout.write(f"  - Synced Variant: {v_data['name']}")
