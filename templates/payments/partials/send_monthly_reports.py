from django.core.management.base import BaseCommand
from django.core.mail import EmailMessage
from django.template.loader import render_to_string
from django.utils import timezone
from django.conf import settings
from django.db import models
from datetime import timedelta

from accounts.models import CoachProfile
from payments.models import CoachingOrder
try:
    import weasyprint
except (OSError, ImportError):
    weasyprint = None

class Command(BaseCommand):
    help = 'Generates and emails monthly earnings reports to all active coaches.'

    def handle(self, *args, **options):
        if weasyprint is None:
            self.stdout.write(self.style.ERROR("WeasyPrint is not installed. Cannot generate PDF reports."))
            return

        today = timezone.now()
        first_day_of_last_month = (today.replace(day=1) - timedelta(days=1)).replace(day=1)
        last_day_of_last_month = today.replace(day=1) - timedelta(days=1)
        month_name = first_day_of_last_month.strftime('%B %Y')

        coaches = CoachProfile.objects.filter(user__is_active=True)
        self.stdout.write(f"Found {coaches.count()} active coaches. Processing reports for {month_name}...")

        for coach in coaches:
            earnings_records = CoachingOrder.objects.filter(
                enrollment__coach=coach,
                created_at__gte=first_day_of_last_month,
                created_at__lte=last_day_of_last_month,
                amount_coach__gt=0
            ).annotate(
                earning_type=models.Value('Coach Fee', output_field=models.CharField()),
                user_share=models.F('amount_coach')
            ).order_by('created_at')

            if not earnings_records.exists():
                self.stdout.write(f"No earnings for {coach.user.email} in {month_name}. Skipping.")
                continue

            # Generate PDF
            html_string = render_to_string('payments/earnings_pdf.html', {
                'earnings_records': earnings_records,
                'user': coach.user,
            })
            
            pdf_file = weasyprint.HTML(string=html_string).write_pdf()

            # Send Email
            subject = f"Your Earnings Report for {month_name}"
            body = f"Hi {coach.user.first_name},\n\nPlease find your earnings report for {month_name} attached.\n\nRegards,\nJH Motiv LTD"
            
            email = EmailMessage(
                subject,
                body,
                settings.DEFAULT_FROM_EMAIL,
                [coach.user.email],
            )
            email.attach(f'earnings_report_{month_name.replace(" ", "_")}.pdf', pdf_file, 'application/pdf')
            
            try:
                email.send()
                self.stdout.write(self.style.SUCCESS(f"Successfully sent report to {coach.user.email}"))
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"Failed to send report to {coach.user.email}: {e}"))