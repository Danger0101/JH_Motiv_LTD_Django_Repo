"""
Django settings for JH_Motiv_Shop project.
"""

from pathlib import Path
import os
import dj_database_url
from dotenv import load_dotenv
from django.core.exceptions import ImproperlyConfigured

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

load_dotenv(os.path.join(BASE_DIR, '.env'))


# Quick-start development settings - unsuitable for production
SECRET_KEY = os.getenv('SECRET_KEY')
DEBUG = False

HEROKU_APP_NAME = os.environ.get('HEROKU_APP_NAME')
ALLOWED_HOSTS = ['localhost', '127.0.0.1', 'jhmotiv-shop-ltd-official-040e4cbd5800.herokuapp.com']
CSRF_TRUSTED_ORIGINS = ['jhmotiv-shop-ltd-official-040e4cbd5800.herokuapp.com']

# Application definition
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.sites',
    'django.contrib.humanize',
    
    # Accounts
    'accounts',
    
    'encrypted_model_fields',
    'django_htmx',
    'django_unicorn',

    # Allauth Apps
    'allauth',
    'allauth.account',
    'allauth.socialaccount',

    # Project Apps
    'core',
    'products',
    'cart',
    'payments',
    'dreamers',
    'team',
    'gcal',
    # Coaching Apps
    'coaching_core',
    'coaching_booking',
    'coaching_availability',
    'coaching_client',
    'dashboard',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    # Add whitenoise middleware right after SecurityMiddleware
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'django_htmx.middleware.HtmxMiddleware',
    'allauth.account.middleware.AccountMiddleware',
]

ROOT_URLCONF = 'JH_Motiv_Shop.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [os.path.join(BASE_DIR, 'templates')], 
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'JH_Motiv_Shop.wsgi.application'


# Database
# Configure database from DATABASE_URL environment variable.
# Fallbacks to a local SQLite database if DATABASE_URL is not set.
DATABASES = {
    'default': dj_database_url.config(
        default=f'sqlite:///{BASE_DIR / "db.sqlite3"}',
        conn_max_age=600,
        ssl_require='postgres' in os.environ.get('DATABASE_URL', '')
    )
}


# Password validation
AUTH_PASSWORD_VALIDATORS = [
    { 'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator', },
    { 'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator', },
    { 'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator', },
    { 'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator', },
]

# --- USER AND AUTHENTICATION CONFIGURATION ---

AUTH_USER_MODEL = 'accounts.User'

AUTHENTICATION_BACKENDS = (
    'django.contrib.auth.backends.ModelBackend',
    'allauth.account.auth_backends.AuthenticationBackend',
)

SITE_ID = 1

# --- DJANGO ALLAUTH SETTINGS (Cleaned and Finalized) ---

# General settings
ACCOUNT_ADAPTER = 'accounts.adapter.AccountAdapter'
ACCOUNT_RATE_LIMITS = {
    'login_failed': '50/m', 
}

# Forms: Link to custom forms
ACCOUNT_FORMS = {
    'signup': 'accounts.forms.CustomSignupForm',
}

# Login, Signup, and Email settings
ACCOUNT_LOGIN_ON_EMAIL_CONFIRMATION = True
ACCOUNT_LOGIN_METHOD = 'username_email'
ACCOUNT_EMAIL_VERIFICATION = 'optional'


# Redirects and Logout Behavior
LOGIN_REDIRECT_URL = '/'
ACCOUNT_LOGOUT_REDIRECT_URL = '/'
ACCOUNT_LOGOUT_ON_GET = True 

# Internationalization
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True


# Static files
STATIC_URL = 'static/'
STATICFILES_DIRS = [os.path.join(BASE_DIR, 'static')]
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')

# Use WhiteNoise's storage backend in production
if not DEBUG:
    STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

# Media files
MEDIA_URL = '/media/'
MEDIA_ROOT = os.path.join(BASE_DIR, 'media')

# Default primary key field type
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# =======================================================
# EMAIL CONFIGURATION
# =======================================================

if not DEBUG:
    # Production: SendGrid
    EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
    EMAIL_HOST = 'smtp.sendgrid.net'
    EMAIL_HOST_USER = 'apikey'  # This is literally the string 'apikey'
    EMAIL_HOST_PASSWORD = os.environ.get('SENDGRID_API_KEY')
    EMAIL_PORT = 587
    EMAIL_USE_TLS = True
    DEFAULT_FROM_EMAIL = os.environ.get('DEFAULT_FROM_EMAIL', 'support@jhmotiv.shop')
else:
    # Development: Console
    EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'
    DEFAULT_FROM_EMAIL = 'support@jhmotiv.shop'

# Google Calendar API Credentials
GOOGLE_OAUTH2_CLIENT_ID = os.getenv('GOOGLE_OAUTH2_CLIENT_ID', 'your-client-id')
GOOGLE_OAUTH2_CLIENT_SECRET = os.getenv('GOOGLE_OAUTH2_CLIENT_SECRET', 'your-client-secret')
GOOGLE_OAUTH2_REDIRECT_URI = os.getenv('GOOGLE_OAUTH2_REDIRECT_URI', 'http://localhost:8000/gcal/redirect')

#Encryption:
FIELD_ENCRYPTION_KEY = os.getenv('FIELD_ENCRYPTION_KEY')


# Stripe API Keys
STRIPE_PUBLISHABLE_KEY = os.environ.get('STRIPE_PUBLISHABLE_KEY')
STRIPE_SECRET_KEY = os.environ.get('STRIPE_SECRET_KEY')
STRIPE_WEBHOOK_SECRET = os.environ.get('STRIPE_WEBHOOK_SECRET') # For verifying webhook signatures



LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': ('%(asctime)s [%(levelname)s] [%(name)s:%(lineno)s] '
                       '%(message)s'),
            'datefmt': '%Y-%m-%d %H:%M:%S'
        },
    },
    'handlers': {
        'console': {
            'level': 'DEBUG',
            'class': 'logging.StreamHandler',
            'formatter': 'verbose'
        },
    },
    'loggers': {
        'django': {
            'handlers': ['console'],
            'level': 'DEBUG',
            'propagate': True,
        },
    },
    'root': {
        'handlers': ['console'],
        'level': 'INFO',
    },
}



# --- HEROKU PRODUCTION SETTINGS ---
if not DEBUG:
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
    SECURE_SSL_REDIRECT = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
