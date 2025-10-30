import json
from django.views.generic import ListView, DetailView
from .models import Product, Variant # Ensure Variant is imported

class ProductListView(ListView):
    model = Product
    template_name = 'products/product_list.html'
    context_object_name = 'products'
    # Add other pagination/filtering logic here

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