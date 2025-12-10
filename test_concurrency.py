from django.test import TransactionTestCase
from django.core.exceptions import ValidationError
from django.db import connections
from concurrent.futures import ThreadPoolExecutor
from coaching_core.models import Workshop
from coaching_booking.models import SessionBooking
from accounts.models import User, CoachProfile
from coaching_booking.services import BookingService
from datetime import datetime, time
from django.utils import timezone
import pytz

class BookingConcurrencyTest(TransactionTestCase):
    # We use TransactionTestCase because standard TestCase wraps everything 
    # in a transaction that other threads can't see.

    def setUp(self):
        # Setup: 1 Coach, 1 Workshop with Capacity = 1
        self.user = User.objects.create(username='coach', email='coach@test.com', is_coach=True)
        self.coach = CoachProfile.objects.create(user=self.user)
        
        # Create a workshop
        # Workshop model has date, start_time, end_time fields
        ws_date = (timezone.now() + timezone.timedelta(days=1)).date()
        
        self.workshop = Workshop.objects.create(
            coach=self.coach,
            name="High Stakes Workshop",
            description="Test",
            price=0,
            date=ws_date,
            start_time=time(10, 0),
            end_time=time(11, 0),
            total_attendees=1,  # <--- CRITICAL: Only 1 spot!
            active_status=True
        )

    def attempt_booking(self, email):
        """
        The worker function that tries to book the slot.
        We must close the DB connection per thread to simulate real request isolation.
        """
        try:
            # Django closes connections at the end of requests, but in threads we must do it manually
            # to force a fresh connection/transaction.
            booking_data = {
                'workshop_id': self.workshop.id,
                'start_time': datetime.combine(self.workshop.date, self.workshop.start_time).isoformat(),
                'email': email,
                'name': 'Tester'
            }
            
            BookingService.create_booking(booking_data, user=None)
            return "SUCCESS"
        except ValidationError:
            return "FAILED_FULL"
        except Exception as e:
            return f"ERROR: {str(e)}"
        finally:
            connections.close_all()

    def test_race_condition_protection(self):
        """
        Fire 5 concurrent booking attempts at a workshop with capacity=1.
        """
        emails = [f"guest{i}@test.com" for i in range(5)]
        
        with ThreadPoolExecutor(max_workers=5) as executor:
            results = list(executor.map(self.attempt_booking, emails))

        # Assertions
        success_count = results.count("SUCCESS")
        failure_count = results.count("FAILED_FULL")

        print(f"\nResults: {results}")

        self.assertEqual(success_count, 1, f"Only 1 booking should succeed! Got {success_count}. Results: {results}")
        self.assertEqual(failure_count, 4, f"4 attempts should fail due to capacity. Got {failure_count}.")
        
        # Verify DB integrity
        self.assertEqual(self.workshop.bookings.count(), 1)