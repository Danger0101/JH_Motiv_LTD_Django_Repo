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
            self.stdout.write(self.style.WARNING("No products found or API error."))
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
                    # Attempt to parse Size and Color from name (standard Printful format: "Product - Color / Size")
                    # This is needed because your Variant model enforces unique_together on (product, color, size)
                    variant_name = v_data.get('name', '')
                    parts = variant_name.split(' - ')
                    
                    color = "Default"
                    size = "One Size"
                    
                    # Basic parsing logic (Printful names vary, this is a best-effort attempt)
                    if len(parts) > 1:
                        details = parts[-1] # e.g. "Black / L" or "11oz"
                        if '/' in details:
                            detail_parts = details.split('/')
                            color = detail_parts[0].strip()
                            size = detail_parts[1].strip()
                        else:
                            size = details.strip()
                    
                    # Create or Update Variant
                    # We use defaults for color/size to avoid overwriting manual corrections in admin
                    obj, v_created = Variant.objects.update_or_create(
                        printful_variant_id=str(v_data['id']),
                        defaults={
                            'product': product,
                            'name': variant_name,
                            'price': v_data.get('retail_price', 0.00),
                            'sku': v_data.get('sku', ''),
                            'stock_pool': None,
                            # Ensure we satisfy unique constraint if it's a new record
                            'color': color[:50], # Truncate to fit max_length
                            'size': size[:20],   # Truncate to fit max_length
                        }
                    )
                    action = "Created" if v_created else "Updated"
                    self.stdout.write(f"  - {action} Variant: {variant_name} (Size: {size}, Color: {color})")

            except Exception as e:
                self.stdout.write(self.style.ERROR(f"Failed to process product {p_data.get('name')}: {e}"))
                # Continue to next product instead of stopping completely
                continue

        self.stdout.write(self.style.SUCCESS("Printful sync completed."))