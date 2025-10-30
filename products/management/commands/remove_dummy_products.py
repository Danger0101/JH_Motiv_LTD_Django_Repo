# products/management/commands/remove_dummy_products.py
from django.core.management.base import BaseCommand
from products.models import Product, StockPool

class Command(BaseCommand):
    help = 'Removes ALL products and ALL StockPools created for testing'

    # Note: No add_arguments method is needed for a simple cleanup command

    def handle(self, *args, **kwargs):
        
        # --- Perform Cleanup ---
        product_count = Product.objects.count()
        pool_count = StockPool.objects.count()
        
        if product_count > 0:
            Product.objects.all().delete()
            self.stdout.write(self.style.SUCCESS(f'Deleted {product_count} products.'))
            
        if pool_count > 0:
            StockPool.objects.all().delete()
            self.stdout.write(self.style.SUCCESS(f'Deleted {pool_count} StockPools.'))
            
        if product_count == 0 and pool_count == 0:
             self.stdout.write(self.style.NOTICE('No dummy data found to delete.'))

        self.stdout.write(self.style.SUCCESS('Cleanup complete.'))