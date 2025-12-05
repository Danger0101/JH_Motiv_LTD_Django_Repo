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
                    # Parse logic to extract Size and Color from name
                    # Printful names vary, e.g., "Product - Color / Size" or "Product / Size"
                    variant_name = v_data.get('name', '')
                    product_name = p_data.get('name', '')
                    
                    color = "Default"
                    size = "One Size"

                    # Strategy 1: "Product - Color / Size" (Hyphen Separator)
                    if ' - ' in variant_name:
                        parts = variant_name.split(' - ')
                        details = parts[-1] # e.g. "Black / L" or "11oz"
                        if '/' in details:
                            detail_parts = details.split('/')
                            color = detail_parts[0].strip()
                            size = detail_parts[1].strip()
                        else:
                            size = details.strip()
                    
                    # Strategy 2: "Product / Size" (No Hyphen, just appended options)
                    elif variant_name.startswith(product_name):
                        # Remove product name and leading delimiters (slash or space)
                        suffix = variant_name[len(product_name):].strip(' -/')
                        if suffix:
                            if '/' in suffix:
                                detail_parts = suffix.split('/')
                                color = detail_parts[0].strip()
                                size = detail_parts[1].strip()
                            else:
                                size = suffix.strip()

                    # Create or Update Variant
                    # We use defaults for color/size to avoid overwriting manual corrections in admin
                    # if the parsing matches existing logic, but we must ensure uniqueness.
                    obj, v_created = Variant.objects.update_or_create(
                        printful_variant_id=str(v_data['id']),
                        defaults={
                            'product': product,
                            'name': variant_name,
                            'price': v_data.get('retail_price', 0.00),
                            'sku': v_data.get('sku', ''),
                            'stock_pool': None,
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