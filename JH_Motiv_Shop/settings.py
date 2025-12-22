"""
Django settings for JH_Motiv_Shop project.
"""

from pathlib import Path
import os
import ssl
import dj_database_url
from dotenv import load_dotenv
from celery.schedules import crontab
from django.core.exceptions import ImproperlyConfigured
from django.urls import reverse_lazy

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

load_dotenv(os.path.join(BASE_DIR, '.env'))

# Quick-start development settings - unsuitable for production
SECRET_KEY = os.getenv('SECRET_KEY')
DEBUG = False

HEROKU_APP_NAME = os.environ.get('HEROKU_APP_NAME')
ALLOWED_HOSTS = ['jhmotiv-shop-ltd-official-040e4cbd5800.herokuapp.com', 'jhmotiv.shop']
CSRF_TRUSTED_ORIGINS = ['https://jhmotiv-shop-ltd-official-040e4cbd5800.herokuapp.com', 'https://jhmotiv.shop']

# --- CUSTOM URL CONFIGURATION ---
# This is required by the coaching_booking email templates for generating absolute links
SITE_URL = 'https://jhmotiv.shop'
SITE_NAME = 'JH Motiv LTD'

# Application definition
INSTALLED_APPS = [    
    # Add these lines at the very top of INSTALLED_APPS
    "unfold",
    "unfold.contrib.filters",
    "unfold.contrib.forms",

    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.sites',
    'django.contrib.sitemaps',
    'django.contrib.humanize',
    
    # Tailwind CSS
    'tailwind',
    'theme',
    'cloudinary_storage',
    
    # Accounts
    'accounts',
    
    'encrypted_model_fields',
    'django_htmx',
    'django_unicorn',
    'widget_tweaks',

    # Allauth Apps
    'allauth',
    'allauth.account',
    'allauth.socialaccount',
    'allauth.socialaccount.providers.google',

    # Project Apps
    'core',
    'products',
    'cart',
    'payments',
    'dreamers',
    'team',
    'gcal',
    'facts',
    
    # Coaching Apps
    'coaching_core',
    'coaching_booking',
    'coaching_availability',
    'coaching_client',
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
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'JH_Motiv_Shop.wsgi.application'


# Database
DATABASES = {
    'default': dj_database_url.config(
        conn_max_age=600, 
        ssl_require=True,
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

# Required for the browser auto-reload during development
INTERNAL_IPS = [
    "127.0.0.1",
]

# Redirects and Logout Behavior
LOGIN_REDIRECT_URL = '/'
ACCOUNT_LOGOUT_REDIRECT_URL = '/'
ACCOUNT_LOGOUT_ON_GET = True 

SOCIALACCOUNT_BASE_TEMPLATE = "base.html" 

# Internationalization
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True


# =======================================================
# STATIC & MEDIA FILES (Updated for Django 5.x + Cloudinary)
# =======================================================

STATIC_URL = '/static/'
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')
STATICFILES_DIRS = [
    os.path.join(BASE_DIR, 'static'),
]
MEDIA_URL = '/media/'
MEDIA_ROOT = os.path.join(BASE_DIR, 'media')



# Define Storages (Django 5.x Standard)
STORAGES = {
    "default": {
        "BACKEND": "cloudinary_storage.storage.MediaCloudinaryStorage" if os.getenv('CLOUDINARY_CLOUD_NAME') else "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage",
    },
}

# Legacy Fallbacks (Required for 3rd party libs like django-cloudinary-storage that haven't updated to Django 5)
DEFAULT_FILE_STORAGE = STORAGES["default"]["BACKEND"]
STATICFILES_STORAGE = STORAGES["staticfiles"]["BACKEND"]

# Cloudinary Specific Config
CLOUDINARY_STORAGE = {
    'CLOUD_NAME': os.getenv('CLOUDINARY_CLOUD_NAME'),
    'API_KEY': os.getenv('CLOUDINARY_API_KEY'),
    'API_SECRET': os.getenv('CLOUDINARY_API_SECRET'),
}


# Default primary key field type
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# =======================================================
# EMAIL CONFIGURATION
# =======================================================

if not DEBUG:
    # Production: Google/Gmail SMTP (Using App Password)
    EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
    
    # Google's SMTP Server Settings
    EMAIL_HOST = 'smtp.gmail.com'
    EMAIL_PORT = 587
    EMAIL_USE_TLS = True
    
    # Credentials (pulled from Heroku Config Vars)
    # This must be your full Gmail/Workspace address (e.g., coach@jhmotiv.shop)
    EMAIL_HOST_USER = os.environ.get('GMAIL_HOST_USER') 
    # This must be the 16-character App Password, NOT your main password
    EMAIL_HOST_PASSWORD = os.environ.get('GMAIL_APP_PASSWORD')
    
    # Set the default 'from' email, falling back to the host user
    DEFAULT_FROM_EMAIL = os.environ.get('DEFAULT_FROM_EMAIL', EMAIL_HOST_USER) 

else:
    # Development: Console
    EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'
    DEFAULT_FROM_EMAIL = 'support@jhmotiv.shop'

# Google Calendar API Credentials
GOOGLE_OAUTH2_CLIENT_ID = os.getenv('GOOGLE_OAUTH2_CLIENT_ID')
GOOGLE_OAUTH2_CLIENT_SECRET = os.getenv('GOOGLE_OAUTH2_CLIENT_SECRET')
GOOGLE_OAUTH2_REDIRECT_URI = os.getenv('GOOGLE_OAUTH2_REDIRECT_URI')

if not DEBUG:
    # --- PRODUCTION ENVIRONMENT CHECKS ---
    # Ensure all required external service credentials are set in production
    if not GOOGLE_OAUTH2_CLIENT_ID:
        raise ImproperlyConfigured("GOOGLE_OAUTH2_CLIENT_ID is not set in the environment variables.")
    if not GOOGLE_OAUTH2_CLIENT_SECRET:
        raise ImproperlyConfigured("GOOGLE_OAUTH2_CLIENT_SECRET is not set in the environment variables.")
    if not GOOGLE_OAUTH2_REDIRECT_URI:
        raise ImproperlyConfigured("GOOGLE_OAUTH2_REDIRECT_URI is not set in the environment variables.")
        
    # Gmail SMTP checks for production email
    if not EMAIL_HOST_USER:
         raise ImproperlyConfigured("GMAIL_HOST_USER is not set in the environment variables for production email.")
    if not EMAIL_HOST_PASSWORD:
         raise ImproperlyConfigured("GMAIL_APP_PASSWORD is not set in the environment variables for production email.")

#Encryption:
FIELD_ENCRYPTION_KEY = os.getenv('FIELD_ENCRYPTION_KEY')


# Stripe API Keys
STRIPE_PUBLISHABLE_KEY = os.environ.get('STRIPE_PUBLISHABLE_KEY')
STRIPE_SECRET_KEY = os.environ.get('STRIPE_SECRET_KEY')
STRIPE_WEBHOOK_SECRET = os.environ.get('STRIPE_WEBHOOK_SECRET') # For verifying webhook signatures
# Printful API & Webhooks
PRINTFUL_API_KEY = os.environ.get('PRINTFUL_API_KEY')
PRINTFUL_STORE_ID = os.environ.get('PRINTFUL_STORE_ID')
PRINTFUL_AUTO_FULFILLMENT = False  # Set to True for auto-processing
# Add this line for webhook security verification
PRINTFUL_WEBHOOK_SECRET = os.environ.get('PRINTFUL_WEBHOOK_SECRET')


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
            'level': 'INFO',  # <--- Change this from 'DEBUG' to 'INFO'
            'propagate': True,
        },
        # --- ADD THIS SECTION TO SILENCE TEMPLATE NOISE ---
        'django.template': {
            'handlers': ['console'],
            'level': 'INFO', 
            'propagate': False,
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
    USE_X_FORWARDED_HOST = True
    SECURE_SSL_REDIRECT = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True


# =======================================================
# DJANGO ALLAUTH SOCIAL ACCOUNT SETTINGS
# =======================================================
SOCIALACCOUNT_PROVIDERS = {
    'google': {
        'SCOPE': [
            'profile',
            'email',
            'https://www.googleapis.com/auth/calendar.events',
            'https://www.googleapis.com/auth/meetings.space.created',
        ],
        'AUTH_PARAMS': {
            'access_type': 'offline', # Required for long-term access (refresh tokens)
        },
        # NOTE: allauth uses the DB configuration below, 
        # but defining this here ensures scope definition is correct.
        # 'APP': {
        #     'client_id': os.getenv('GOOGLE_OAUTH2_CLIENT_ID'),
        #     'secret': os.getenv('GOOGLE_OAUTH2_CLIENT_SECRET'),
        # }
    }
}

# =======================================================
# DJANGO-TAILWIND CONFIGURATION
# =======================================================

TAILWIND_APP_NAME = 'theme'
TAILWIND_CSS_PATH = 'css/styles.css'
TAILWIND_CLI_ARGS = ['--minify']

# =======================================================
# CELERY CONFIGURATION
# =======================================================
CELERY_BROKER_URL = os.environ.get('REDIS_URL') or os.environ.get('REDIS_TLS_URL') or 'redis://localhost:6379/0'
CELERY_RESULT_BACKEND = CELERY_BROKER_URL

# Handle Heroku Redis SSL (Rediss://)
if CELERY_BROKER_URL.startswith("rediss://"):
    CELERY_BROKER_USE_SSL = {
        'ssl_cert_reqs': ssl.CERT_NONE
    }
    CELERY_REDIS_BACKEND_USE_SSL = {
        'ssl_cert_reqs': ssl.CERT_NONE
    }

# Optional: Retry connection on startup
CELERY_BROKER_CONNECTION_RETRY_ON_STARTUP = True

# =======================================================
# CELERY BEAT SCHEDULER CONFIGURATION
# =======================================================

CELERY_TIMEZONE = TIME_ZONE # 'UTC'

CELERY_BEAT_SCHEDULE = {
    # 1. Coaching Session Reminders
    'send-session-reminders-daily': {
        # This points to the task in coaching_booking/tasks.py
        'task': 'coaching_booking.tasks.send_upcoming_session_reminders',
        # Run every day at 10:00 UTC
        'schedule': crontab(hour=10, minute=0), 
        'args': (), 
        'options': {'queue': 'low_priority'},
    },
    
    # 2. Abandoned Cart Reminders (Run every 6 hours)
    'send-abandoned-cart-reminders-quarterly': {
        # This points to the task in payments/tasks.py
        'task': 'payments.tasks.send_abandoned_cart_reminders_task',
        'schedule': crontab(minute='0', hour='*/6'), # Every 6 hours on the hour
        'args': (24,), # Find carts abandoned for 24+ hours
        'options': {'queue': 'low_priority'},
    },
}

# --- ADMIN DASHBOARD THEME (Django Unfold) ---
UNFOLD = {
    "SITE_TITLE": "JH Motiv Control Deck",
    "SITE_HEADER": "JH Motiv Admin",
    "SITE_URL": "/",
    # "SITE_ICON": lambda request: static("images/logo.png"),

    # Primary Color: Matrix Green / Cyber Yellow vibe
    "COLORS": {
        "primary": {
            "50": "240 253 244",
            "100": "220 252 231",
            "200": "187 247 208",
            "300": "134 239 172",
            "400": "74 222 128",
            "500": "34 197 94",  # Main Green
            "600": "22 163 74",
            "700": "21 128 61",
            "800": "22 101 52",
            "900": "20 83 45",
        },
    },

    # CRM-Style Sidebar Navigation
    "SIDEBAR": {
        "show_search": True,
        "show_all_applications": False, # Hide the default messy list
        "navigation": [
            {
                "title": "Commerce Engine",
                "separator": True,
                "items": [
                    {
                        "title": "Orders",
                        "icon": "shopping_cart", # Material Icons
                        "link": reverse_lazy("admin:payments_order_changelist"),
                    },
                    {
                        "title": "Products",
                        "icon": "inventory_2",
                        "link": reverse_lazy("admin:products_product_changelist"),
                    },
                    {
                        "title": "Discounts & Coupons",
                        "icon": "local_offer",
                        "link": reverse_lazy("admin:payments_coupon_changelist"),
                    },
                ],
            },
            {
                "title": "Coaching Ops",
                "separator": True,
                "items": [
                    {
                        "title": "Session Bookings",
                        "icon": "calendar_month",
                        "link": reverse_lazy("admin:coaching_booking_sessionbooking_changelist"),
                    },
                    {
                        "title": "Coaches",
                        "icon": "school",
                        "link": reverse_lazy("admin:accounts_coachprofile_changelist"),
                    },
                    {
                        "title": "Workshops",
                        "icon": "groups",
                        "link": reverse_lazy("admin:coaching_core_workshop_changelist"),
                    },
                ],
            },
            {
                "title": "User Management",
                "separator": True,
                "items": [
                    {
                        "title": "All Users",
                        "icon": "group",
                        "link": reverse_lazy("admin:accounts_user_changelist"),
                    },
                    {
                        "title": "Newsletter Subs",
                        "icon": "mail",
                        "link": reverse_lazy("admin:core_newslettersubscriber_changelist"),
                    },
                ],
            },
        ],
    },
    "DASHBOARD_CALLBACK": "core.admin.dashboard_callback",
}
