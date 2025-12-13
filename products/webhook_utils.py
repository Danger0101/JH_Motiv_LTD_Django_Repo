import hmac
import hashlib
from django.conf import settings

def verify_printful_webhook(request):
    """
    Verifies the X-PF-HMAC-SHA256 header from Printful to ensure the request 
    is legitimate and hasn't been tampered with.
    
    Args:
        request: The Django HttpRequest object.
        
    Returns:
        bool: True if the signature is valid, False otherwise.
    """
    secret = getattr(settings, 'PRINTFUL_WEBHOOK_SECRET', None)
    if not secret:
        return False
        
    signature = request.headers.get('X-PF-HMAC-SHA256')
    if not signature:
        return False
        
    try:
        # Printful signs the raw request body
        body = request.body
        calculated_signature = hmac.new(secret.encode('utf-8'), body, hashlib.sha256).hexdigest()
        return hmac.compare_digest(signature, calculated_signature)
    except Exception:
        return False