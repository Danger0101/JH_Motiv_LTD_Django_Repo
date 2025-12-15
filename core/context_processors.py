import subprocess
from django.core.cache import cache

def git_version(request):
    version = cache.get('git_version')

    if version is None:
        try:
            # Get the short hash of the latest commit (e.g., "a1b2c3d")
            version = subprocess.check_output(['git', 'rev-parse', '--short', 'HEAD']).decode('utf-8').strip()
            version = f"v{version}"
        except Exception:
            # Fallback if git is not available or fails
            version = ""
        
        cache.set('git_version', version, 3600)
    
    return {'git_version': version if version else None}