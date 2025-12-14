from django.contrib.sitemaps import Sitemap
from products.models import Product

class ProductSitemap(Sitemap):
    changefreq = "weekly"
    priority = 0.8

    def items(self):
        # Returns all products. You might want to filter by .filter(is_active=True)
        return Product.objects.all()

    def lastmod(self, obj):
        # Returns the last modification date. Ensure your model has an 'updated_at' or similar field.
        return getattr(obj, 'updated_at', None)