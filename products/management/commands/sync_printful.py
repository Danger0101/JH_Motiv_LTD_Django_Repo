from django.core.management.base import BaseCommand
from django.core.files.base import ContentFile
from django.conf import settings
import requests
from products.models import Product, Variant, StockPool
from products.printful_service import PrintfulService

class Command(BaseCommand):
    help = 'Syncs products from Printful and ensures StockPools are assigned'

    def handle(self, *args, **kwargs):
        self.stdout.write("Starting Printful Sync...")
        service = PrintfulService()
        
        # --- STOCK STRATEGY ---
        # Create a shared StockPool for on-demand items.
        # We assume high availability (9999) because Printful handles the inventory.
        on_demand_pool, _ = StockPool.objects.get_or_create(
            name="Printful On-Demand Pool",
            defaults={
                'available_stock': 9999,
                'low_stock_threshold': 50
            }
        )
        # Ensure it's topped up if it was already created but low
        if on_demand_pool.available_stock < 1000:
            on_demand_pool.available_stock = 9999
            on_demand_pool.save()

        # 1. Fetch Products
        printful_products = service.get_store_products()
        if not printful_products:
            self.stdout.write(self.style.WARNING("No products found or API error."))
            return

        for p_data in printful_products:
            try:
                self.stdout.write(f"Processing Product: {p_data['name']} (ID: {p_data['id']})")
                
                # Helper to guess category from name (Only used on creation)
                name_lower = p_data['name'].lower()
                shipping_cat = 'default'
                if 'hoodie' in name_lower or 'sweatshirt' in name_lower:
                    shipping_cat = 'hoodie'
                elif 'shirt' in name_lower or 'tank' in name_lower:
                    shipping_cat = 't-shirt'
                elif 'mug' in name_lower:
                    shipping_cat = 'mug'
                elif 'hat' in name_lower or 'beanie' in name_lower:
                    shipping_cat = 'hat'
                elif 'bag' in name_lower or 'tote' in name_lower:
                    shipping_cat = 'bag'
                elif 'poster' in name_lower or 'canvas' in name_lower:
                    shipping_cat = 'poster'
                elif 'sticker' in name_lower:
                    shipping_cat = 'sticker'

                # Create or Update Product
                product, created = Product.objects.update_or_create(
                    printful_product_id=str(p_data['id']),
                    defaults={
                        'name': p_data['name'],
                        'product_type': 'physical',
                        'fulfillment_method': 'printful',
                    }
                )
                
                # Only set shipping_category on creation to avoid overwriting admin edits
                if created:
                    product.shipping_category = shipping_cat
                    product.save()
                
                # Fetch Thumbnail
                if created and p_data.get('thumbnail_url'):
                    try:
                        img_resp = requests.get(p_data['thumbnail_url'], timeout=10)
                        if img_resp.status_code == 200:
                            file_name = f"printful_{p_data['id']}.jpg"
                            product.featured_image.save(file_name, ContentFile(img_resp.content), save=True)
                            self.stdout.write(f"  - Saved image for {product.name}")
                    except Exception as img_e:
                        self.stdout.write(self.style.WARNING(f"  - Failed to download image: {img_e}"))

                # 2. Fetch Variants
                variants = service.get_product_variants(p_data['id'])
                
                for v_data in variants:
                    variant_name = v_data.get('name', '')
                    product_name = p_data.get('name', '')
                    
                    color = "Default"
                    size = "One Size"
                    
                    # --- PARSING LOGIC ---
                    if ' - ' in variant_name:
                        parts = variant_name.split(' - ')
                        details = parts[-1] 
                        if '/' in details:
                            detail_parts = details.split('/')
                            color = detail_parts[0].strip()
                            size = detail_parts[1].strip()
                        else:
                            size = details.strip()
                    elif variant_name.startswith(product_name):
                        suffix = variant_name[len(product_name):].strip().lstrip(' -/')
                        if suffix:
                            if '/' in suffix:
                                detail_parts = suffix.split('/')
                                color = detail_parts[0].strip()
                                size = detail_parts[1].strip()
                            else:
                                size = suffix.strip()

                    # Create or Update Variant & LINK STOCK POOL
                    obj, v_created = Variant.objects.update_or_create(
                        printful_variant_id=str(v_data['id']),
                        defaults={
                            'product': product,
                            'name': variant_name,
                            'price': v_data.get('retail_price', 0.00),
                            'sku': v_data.get('sku', ''),
                            'stock_pool': on_demand_pool,  # <--- CRITICAL FIX: Assign Infinite Stock
                            'color': color[:50], 
                            'size': size[:20],   
                        }
                    )
                    
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"Failed to process product {p_data.get('name')}: {e}"))
                continue

        self.stdout.write(self.style.SUCCESS("Printful sync completed. Stock pools assigned."))
