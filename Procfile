release: python manage.py tailwind install --no-input && python manage.py tailwind build --no-input && python manage.py migrate
web: gunicorn JH_Motiv_Shop.wsgi