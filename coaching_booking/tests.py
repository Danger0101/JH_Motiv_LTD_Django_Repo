from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone
from datetime import time, date, timedelta

from accounts.models import User, CoachProfile
from coaching_core.models import Offering
from coaching_availability.models import CoachAvailability
from .models import ClientOfferingEnrollment, SessionBooking

class BookingLogicTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        """Set up non-modified objects used by all test methods."""
        # Create Users
        cls.client_user = User.objects.create_user(
            username='testclient',
            email='client@example.com',
            password='password123',
            is_client=True,
            is_coach=False
        )
        cls.coach_user = User.objects.create_user(
            username='testcoach',
            email='coach@example.com',
            password='password123',
            is_coach=True,
            is_client=False
        )

        # Create Coach Profile
        cls.coach_profile = CoachProfile.objects.create(
            user=cls.coach_user,
            bio='A test coach.',
            time_zone='UTC'
        )

        # Create a coaching offering
        cls.offering = Offering.objects.create(
            name='Test Offering',
            description='A test description.',
            price=100.00,
            duration_type='PACKAGE',
            total_length_units=1,
            session_length_minutes=60,
            total_number_of_sessions=5,
        )
        cls.offering.coaches.add(cls.coach_profile)

        # Set up a recurring availability for the coach
        # Let's use a weekday 2 days from now to ensure it's in the future
        cls.future_day = (timezone.now() + timedelta(days=2)).weekday()
        cls.available_start_time = time(14, 0)  # 2:00 PM
        
        CoachAvailability.objects.create(
            coach=cls.coach_user,
            day_of_week=cls.future_day,
            start_time=cls.available_start_time,
            end_time=time(17, 0)  # 5:00 PM
        )

    def setUp(self):
        """Set up objects that may be modified by tests."""
        # Create a fresh enrollment for each test
        self.enrollment = ClientOfferingEnrollment.objects.create(
            client=self.client_user,
            offering=self.offering,
            coach=self.coach_profile,
        )
        # Log in the client
        self.client = Client()
        self.client.login(username='testclient', password='password123')

        # Define the exact start datetime for booking attempts
        today = timezone.now().date()
        days_ahead = self.future_day - today.weekday()
        if days_ahead <= 0:
            days_ahead += 7
        self.booking_date = today + timedelta(days=days_ahead)
        self.booking_datetime_naive = timezone.datetime.combine(self.booking_date, self.available_start_time)
        self.booking_datetime_str = self.booking_datetime_naive.strftime('%Y-%m-%d %H:%M')


    def test_book_session_success(self):
        """
        Tests that a client can successfully book an available time slot.
        """
        self.assertEqual(self.enrollment.remaining_sessions, 5)

        response = self.client.post(reverse('coaching_booking:book_session'), {
            'enrollment_id': self.enrollment.id,
            'coach_id': self.coach_profile.id,
            'start_time': self.booking_datetime_str,
        })

        # Check for successful booking and redirect
        self.assertEqual(response.status_code, 204)
        self.assertIn('HX-Redirect', response)
        self.assertEqual(response['HX-Redirect'], reverse('accounts:account_profile'))

        # Verify a SessionBooking was created
        self.assertTrue(SessionBooking.objects.filter(
            client=self.client_user,
            coach=self.coach_profile,
            enrollment=self.enrollment
        ).exists())

        # Verify the session count was decremented
        self.enrollment.refresh_from_db()
        self.assertEqual(self.enrollment.remaining_sessions, 4)

    def test_prevent_double_booking(self):
        """
        Tests that a second client cannot book an already taken time slot.
        """
        # First booking (successful)
        SessionBooking.objects.create(
            client=self.client_user,
            coach=self.coach_profile,
            enrollment=self.enrollment,
            start_datetime=timezone.make_aware(self.booking_datetime_naive)
        )
        self.enrollment.refresh_from_db()
        self.assertEqual(self.enrollment.remaining_sessions, 4, "First booking should decrement sessions")

        # Create a second client and enrollment
        client2_user = User.objects.create_user('client2', 'client2@test.com', 'pw')
        enrollment2 = ClientOfferingEnrollment.objects.create(
            client=client2_user,
            offering=self.offering,
            coach=self.coach_profile,
        )
        self.assertEqual(enrollment2.remaining_sessions, 5, "New enrollment should have full sessions")

        # Log in client2
        client2 = Client()
        client2.login(username='client2', password='pw')

        # Attempt to book the same slot
        response = client2.post(reverse('coaching_booking:book_session'), {
            'enrollment_id': enrollment2.id,
            'coach_id': self.coach_profile.id,
            'start_time': self.booking_datetime_str,
        })
        
        # Check for HTMX error response
        self.assertEqual(response.status_code, 200)
        self.assertIn('HX-Redirect', response) # The view sends a redirect with a message
        
        # Verify no new booking was created for the second client
        self.assertFalse(SessionBooking.objects.filter(client=client2_user).exists())

        # Verify the session count for the second client did NOT change
        enrollment2.refresh_from_db()
        self.assertEqual(enrollment2.remaining_sessions, 5)