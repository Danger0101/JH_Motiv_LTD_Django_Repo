from django.core.management.base import BaseCommand
from django.core.files.base import ContentFile
import requests
from products.models import Product, Variant, StockPool
from products.printful_service import PrintfulService

class Command(BaseCommand):
    help = 'Syncs products from Printful'

    def handle(self, *args, **kwargs):
        self.stdout.write("Starting Printful Sync...")
        service = PrintfulService()
        
        # 1. Fetch Products
        printful_products = service.get_store_products()
        if not printful_products:
            self.stdout.write(self.style.WARNING("No products found or API error. (See console above for details)"))
            return

        for p_data in printful_products:
            try:
                self.stdout.write(f"Processing Product: {p_data['name']} (ID: {p_data['id']})")
                
                # Create or Update Product
                product, created = Product.objects.update_or_create(
                    printful_product_id=str(p_data['id']),
                    defaults={
                        'name': p_data['name'],
                        'product_type': 'physical',
                    }
                )
                
                # Optional: Fetch Product Thumbnail if available
                if created and p_data.get('thumbnail_url'):
                    try:
                        img_resp = requests.get(p_data['thumbnail_url'])
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
                    
                    # --- PARSING STRATEGY 1: Standard Printful ("Product - Color / Size") ---
                    if ' - ' in variant_name:
                        parts = variant_name.split(' - ')
                        details = parts[-1] 
                        if '/' in details:
                            detail_parts = details.split('/')
                            color = detail_parts[0].strip()
                            size = detail_parts[1].strip()
                        else:
                            size = details.strip()

                    # --- PARSING STRATEGY 2: WooCommerce/Direct ("Product / Size" or "Product Size") ---
                    # Checks if variant starts with product name to strip it out
                    elif variant_name.startswith(product_name):
                        # Remove product name from the start
                        suffix = variant_name[len(product_name):].strip()
                        # Remove leading separators like " / " or " - "
                        suffix = suffix.lstrip(' -/')
                        
                        if suffix:
                            if '/' in suffix:
                                detail_parts = suffix.split('/')
                                color = detail_parts[0].strip()
                                size = detail_parts[1].strip()
                            else:
                                size = suffix.strip()

                    # Create or Update Variant
                    obj, v_created = Variant.objects.update_or_create(
                        printful_variant_id=str(v_data['id']),
                        defaults={
                            'product': product,
                            'name': variant_name,
                            'price': v_data.get('retail_price', 0.00),
                            'sku': v_data.get('sku', ''),
                            'stock_pool': None,
                            'color': color[:50], 
                            'size': size[:20],   
                        }
                    )
                    action = "Created" if v_created else "Updated"
                    self.stdout.write(f"  - {action} Variant: {variant_name} (Size: {size}, Color: {color})")

            except Exception as e:
                self.stdout.write(self.style.ERROR(f"Failed to process product {p_data.get('name')}: {e}"))
                continue

        self.stdout.write(self.style.SUCCESS("Printful sync completed."))