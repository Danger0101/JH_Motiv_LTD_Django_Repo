"""
URL configuration for JH_Motiv_Shop project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.contrib.sitemaps.views import sitemap
from sitemaps import ProductSitemap
from coaching_booking.webhooks import stripe_webhook

sitemaps = {
    'products': ProductSitemap,
}

urlpatterns = [
    # Core Django Admin
    path('admin/', admin.site.urls),

    # Allauth URLs
    path('accounts/', include('allauth.urls')),
    path('unicorn/', include('django_unicorn.urls')),

    # Coaching System Apps
    path('', include('core.urls', namespace='core')),
    path('coach/', include('coaching_booking.urls')),
    path('info/', include('coaching_client.urls')),
    path('admin/offers/', include('coaching_core.urls', namespace='coaching')),
    path('coach/time/', include('coaching_availability.urls', namespace='coaching_availability')),
    path('oauth/', include('gcal.urls')),
    path('webhooks/stripe/', stripe_webhook, name='stripe_webhook'),

    # Existing and Standard Apps
    path('auth/', include('accounts.urls', namespace='accounts')),
    path('affiliate/', include('dreamers.urls', namespace='dreamers')),
    path('checkout/', include('payments.urls', namespace='payments')),
    path('cart/', include('cart.urls', namespace='cart')),
    path('shop/', include('products.urls')),
    path('awakening/', include('awakening.urls', namespace='awakening')),
    path('sitemap.xml', sitemap, {'sitemaps': sitemaps}, name='django.contrib.sitemaps.views.sitemap'),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)