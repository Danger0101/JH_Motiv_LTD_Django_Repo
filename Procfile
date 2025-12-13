web: gunicorn JH_Motiv_Shop.wsgi
worker: celery -A JH_Motiv_Shop worker --loglevel=info --concurrency=2
beat: celery -A JH_Motiv_Shop beat -l info --scheduler django_celery_beat.schedulers.DatabaseScheduler