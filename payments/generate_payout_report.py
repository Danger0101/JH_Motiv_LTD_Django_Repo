import csv
from datetime import datetime, date
from django.core.management.base import BaseCommand, CommandError
from django.db.models import Sum, Count
from django.utils import timezone
from payments.models import CoachingOrder
from accounts.models import CoachProfile
from dreamers.models import DreamerProfile
from payments.services import calculate_coach_earnings_for_period
from decimal import Decimal

class Command(BaseCommand):
    help = 'Generates a monthly payout report for coaches and referrers for unpaid commissions.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--month',
            type=int,
            help='The month for which to generate the report (1-12). Defaults to the previous month.'
        )
        parser.add_argument(
            '--year',
            type=int,
            help='The year for which to generate the report (e.g., 2024). Defaults to the current year.'
        )
        parser.add_argument(
            '--output',
            type=str,
            help='Optional. Path to a CSV file to save the report (e.g., "payouts.csv").'
        )
        parser.add_argument(
            '--min-payout',
            type=float,
            default=0.0,
            help='Minimum total payout amount to include in the report (e.g., 50.00).'
        )

    def handle(self, *args, **options):
        now = timezone.now()
        year = options['year'] or now.year
        month = options['month']

        import calendar
        if not month:
            # Default to the previous month
            first_day_of_current_month = now.replace(day=1)
            last_day_of_previous_month = first_day_of_current_month - timezone.timedelta(days=1)
            month = last_day_of_previous_month.month
            year = last_day_of_previous_month.year
        
        if not (1 <= month <= 12):
            raise CommandError("Month must be between 1 and 12.")
            
        last_day = calendar.monthrange(year, month)[1]
        start_date = date(year, month, 1)
        end_date = date(year, month, last_day)

        self.stdout.write(self.style.SUCCESS(f"Generating payout report for {start_date.strftime('%B %Y')}..."))
        
        coaches = CoachProfile.objects.filter(user__is_active=True)
        grand_total = 0
        report_data = []

        for coach in coaches:
            report = calculate_coach_earnings_for_period(coach, start_date, end_date)
            if report['total_earnings'] > 0:
                self.stdout.write(f"Coach: {coach.user.get_full_name()} | Amount: £{report['total_earnings']} | Sessions: {report['sessions_count']}")
                grand_total += report['total_earnings']
                report_data.append(['Coach', coach.user.get_full_name(), coach.user.email, report['total_earnings'], report['sessions_count']])

        self.stdout.write("-" * 40)
        self.stdout.write(f"GRAND TOTAL PAYOUT: £{grand_total}")

        # --- Handle CSV Output ---
        output_file = options['output']
        if output_file:
            try:
                with open(output_file, 'w', newline='', encoding='utf-8') as csvfile:
                    writer = csv.writer(csvfile)
                    writer.writerow(['Type', 'Name', 'Email', 'Amount Owed (£)', 'Number of Orders'])
                    writer.writerows(report_data)
                self.stdout.write(self.style.SUCCESS(f"\nSuccessfully saved report to {output_file}"))
            except IOError as e:
                raise CommandError(f"Could not write to file {output_file}. Error: {e}")

        self.stdout.write(self.style.SUCCESS("\nReport generation complete."))

```

### How to Use the Command

You can now run this command from your terminal.

1.  **Generate a report for the previous month (default behavior):**
    ```bash
    python manage.py generate_payout_report
    ```

2.  **Generate a report for a specific month and year:**
    ```bash
    python manage.py generate_payout_report --month=11 --year=2023
    ```

3.  **Generate a report and save it to a CSV file:**
    ```bash
    python manage.py generate_payout_report --month=11 --year=2023 --output=november_payouts.csv
    ```

This command provides a powerful and flexible tool for managing your platform's finances, ensuring your partners are paid accurately and on time.

<!--
[PROMPT_SUGGESTION]Add a "My Payouts" section to the Dreamer and Coach dashboards to show them their earnings.[/PROMPT_SUGGESTION]
[PROMPT_SUGGESTION]Create a dashboard widget for the admin profile page that shows a summary of total unpaid commissions.[/PROMPT_SUGGESTION]
-->