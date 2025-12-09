import csv
from datetime import datetime
from django.core.management.base import BaseCommand, CommandError
from django.db.models import Sum, Count
from django.utils import timezone
from payments.models import CoachingOrder
from accounts.models import CoachProfile
from dreamers.models import DreamerProfile
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

        if not month:
            # Default to the previous month
            first_day_of_current_month = now.replace(day=1)
            last_day_of_previous_month = first_day_of_current_month - timezone.timedelta(days=1)
            month = last_day_of_previous_month.month
            year = last_day_of_previous_month.year

        if not (1 <= month <= 12):
            raise CommandError("Month must be between 1 and 12.")
        min_payout = Decimal(str(options['min_payout']))

        self.stdout.write(self.style.SUCCESS(f"Generating payout report for {datetime(year, month, 1).strftime('%B %Y')}..."))

        # --- Query for Coach Payouts ---
        coach_payouts = CoachingOrder.objects.filter(
            created_at__year=year,
            created_at__month=month,
            payout_status='unpaid',
            amount_coach__gt=0
        ).values('enrollment__coach').annotate(
            total_payout=Sum('amount_coach'),
            order_count=Count('id')
        ).filter(total_payout__gte=min_payout).order_by('-total_payout')

        # --- Query for Referrer Payouts ---
        referrer_payouts = CoachingOrder.objects.filter(
            created_at__year=year,
            created_at__month=month,
            payout_status='unpaid',
            amount_referrer__gt=0
        ).values('referrer').annotate(
            total_payout=Sum('amount_referrer'),
            order_count=Count('id')
        ).filter(total_payout__gte=min_payout).order_by('-total_payout')

        # --- Prepare data for output ---
        report_data = []
        self.stdout.write(self.style.HTTP_INFO("\n--- Coach Payout Summary ---"))

        # OPTIMIZATION: Pre-fetch all relevant coach profiles to avoid N+1 queries
        coach_ids = [item['enrollment__coach'] for item in coach_payouts]
        coaches = CoachProfile.objects.filter(id__in=coach_ids).select_related('user')
        coach_map = {coach.id: coach for coach in coaches}

        if coach_payouts:
            for item in coach_payouts:
                coach = coach_map.get(item['enrollment__coach'])
                if coach:
                    line = f"Coach: {coach.user.get_full_name()} | Amount: £{item['total_payout']:.2f} | Orders: {item['order_count']}"
                    self.stdout.write(line)
                    report_data.append(['Coach', coach.user.get_full_name(), coach.user.email, item['total_payout'], item['order_count']])
        else:
            self.stdout.write("No unpaid coach commissions for this period.")

        self.stdout.write(self.style.HTTP_INFO("\n--- Referrer Payout Summary ---"))

        # OPTIMIZATION: Pre-fetch all relevant referrer profiles
        referrer_ids = [item['referrer'] for item in referrer_payouts]
        referrers = DreamerProfile.objects.filter(id__in=referrer_ids).select_related('user')
        referrer_map = {ref.id: ref for ref in referrers}

        if referrer_payouts:
            for item in referrer_payouts:
                referrer = referrer_map.get(item['referrer'])
                if referrer:
                    line = f"Referrer: {referrer.name} | Amount: £{item['total_payout']:.2f} | Orders: {item['order_count']}"
                    self.stdout.write(line)
                    # FIX: Safely access user email, as user link is optional
                    email = referrer.user.email if referrer.user else "N/A"
                    report_data.append(['Referrer', referrer.name, email, item['total_payout'], item['order_count']])
        else:
            self.stdout.write("No unpaid referrer commissions for this period.")

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