import os
from celery import Celery

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'JH_Motiv_Shop.settings')

app = Celery('JH_Motiv_Shop')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()