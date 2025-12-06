import random
from django.core.management.base import BaseCommand
#from faker import Faker
from products.models import Product, Variant, StockPool 

class Command(BaseCommand):
    help = 'Creates dummy products and variants linked to StockPools for testing'

    def add_arguments(self, parser):
        parser.add_argument('count', type=int, help='Indicates the number of complex products to be created')

    def handle(self, *args, **kwargs):
        count = kwargs.get('count')
        #fake = Faker()
        self.stdout.write(self.style.SUCCESS(f'Creating {count} complex dummy products...'))

        # --- Base Data Lists ---
        ALL_COLORS = [('Red', '#EF4444'), ('Blue', '#3B82F6'), ('Black', '#1F2937'), ('White', '#F9FAFB'), 
                      ('Green', '#10B981'), ('Yellow', '#FACC15'), ('Purple', '#8B5CF6')]
        ALL_SIZES = ['XS', 'S', 'M', 'L', 'XL', 'XXL']
        
        # --- 1. Create Base Stock Pools ---
        self.stdout.write('Initializing shared Stock Pools...')
        
        if not StockPool.objects.exists():
            pool_data = [
                ('T-Shirt Blanks (Shared)', 200),
                ('Mug Blanks (Shared)', 150),
                ('Coaching Slots (Virtual)', 50),
            ]
            for name, stock in pool_data:
                StockPool.objects.create(name=name, available_stock=stock)

        pools = list(StockPool.objects.all())
        if not pools:
            self.stderr.write(self.style.ERROR('FATAL: No StockPools available. Aborting.'))
            return
        
        # --- 2. Create Products and Variants ---
        for i in range(count):
            #product_name = fake.bs().title()
            product_name = f"Dummy Product {random.randint(1, 1000)}"
            while Product.objects.filter(name=product_name).exists():
                #product_name = f"{fake.bs().title()} {random.randint(1, 1000)}"
                product_name = f"Dummy Product {random.randint(1, 1000)}"

            product = Product.objects.create(
                name=product_name,
                #description=fake.paragraph(nb_sentences=10),
                description="This is a dummy product description.",
                product_type='physical' if random.choice([True, False]) else 'digital' 
            )

            # --- CHANGE: Select a random, unique subset of colors and sizes for this product ---
            num_colors = random.randint(1, len(ALL_COLORS)) # Choose 1 to max colors
            num_sizes = random.randint(1, len(ALL_SIZES))   # Choose 1 to max sizes
            
            # Select random options
            product_colors = random.sample(ALL_COLORS, num_colors)
            product_sizes = random.sample(ALL_SIZES, num_sizes)
            # -----------------------------------------------------------------------------------

            base_price = round(random.uniform(25.00, 75.00), 2)
            base_pool = random.choice(pools) 
            
            # Create variants based on the product's selected color/size combinations
            for color, _ in product_colors: # Use product_colors
                for size in product_sizes:   # Use product_sizes
                    variant_name = f"{color} - {size}"
                    
                    unique_id_part = f"{i}{random.randint(100, 999)}"
                    
                    Variant.objects.create(
                        product=product,
                        name=variant_name,
                        price=base_price + random.randint(-5, 5), # Slight price variation
                        color=color,
                        size=size,
                        stock_pool=base_pool,
                        sku=f"{unique_id_part}-{color[0]}{size}", 
                    )

        self.stdout.write(self.style.SUCCESS(f'Successfully created {count} products and variants.'))