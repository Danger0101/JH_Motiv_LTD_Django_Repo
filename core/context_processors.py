def csp_nonce(request):
    """
    Context processor to make the CSP nonce available in templates as {{ csp_nonce }}.
    This relies on 'csp.middleware.CSPMiddleware' attaching the nonce to the request.
    """
    return {
        'csp_nonce': getattr(request, 'csp_nonce', '')
    }