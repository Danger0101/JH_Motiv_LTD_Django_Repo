release: python manage.py migrate && python manage.py tailwind build && python manage.py collectstatic --noinput
web: gunicorn JH_Motiv_Shop.wsgi