import subprocess
import logging
import os
from django.core.cache import cache

logger = logging.getLogger(__name__)

def git_version(request):
    version = cache.get('git_version')

    if version is None:
        # 1. Try Environment Variable (Better for Production/Heroku/Docker)
        version = os.getenv('GIT_COMMIT') or os.getenv('HEROKU_SLUG_COMMIT')
        
        if version:
            version = f"v{version[:7]}"
        else:
            # 2. Fallback to local git command
            try:
                version = subprocess.check_output(['git', 'rev-parse', '--short', 'HEAD']).decode('utf-8').strip()
                version = f"v{version}"
            except Exception as e:
                logger.warning(f"Failed to fetch git version: {e}")
                version = ""
        
        cache.set('git_version', version, 3600)
    
    return {'git_version': version if version else None}