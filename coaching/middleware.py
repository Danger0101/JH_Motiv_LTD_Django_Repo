class SecurityAndCacheHeadersMiddleware:
    """
    This middleware adds essential security and cache-control headers
    to every response.
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)

        # --- Security Headers ---
        # Prevents the browser from MIME-sniffing the content-type.
        response['X-Content-Type-Options'] = 'nosniff'

        # --- Caching Headers ---
        # Instructs browsers and proxies not to cache dynamic pages.
        # This is a safe default. Caching for specific views can be enabled via decorators.
        response.setdefault('Cache-Control', 'no-cache, no-store, must-revalidate')

        return response