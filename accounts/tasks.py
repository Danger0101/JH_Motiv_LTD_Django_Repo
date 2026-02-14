from celery import shared_task
from django.core.management import call_command

@shared_task
def purge_unverified_users():
    """
    Calls the management command to purge unverified users.
    """
    call_command('purge_bots')
