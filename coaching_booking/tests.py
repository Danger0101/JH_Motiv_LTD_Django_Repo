from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone
from datetime import time, date, timedelta
from django.core import mail
from django.core.management import call_command

from accounts.models import User, CoachProfile
from coaching_core.models import Offering, Workshop
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

class GuestAccessTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.coach_user = User.objects.create_user(
            username='coach_guest', email='coach_guest@test.com', password='password', is_coach=True
        )
        self.coach_profile = CoachProfile.objects.create(user=self.coach_user)
        
        self.workshop = Workshop.objects.create(
            coach=self.coach_profile,
            name="Guest Access Workshop",
            slug="guest-access-workshop",
            description="Test",
            date=timezone.now().date() + timedelta(days=1),
            start_time=time(10, 0),
            end_time=time(12, 0),
            total_attendees=5,
            price=0, # Free ensures immediate booking without Stripe mocking
            active_status=True
        )

    def test_guest_token_lifecycle(self):
        """
        Verifies that:
        1. Booking as a guest generates a token in billing_notes.
        2. Accessing the guest_access view logs the user in.
        3. The token is cleared after use.
        """
        guest_email = "newguest@example.com"
        
        # 1. Book Workshop as Guest
        url = reverse('coaching_booking:book_workshop', args=[self.workshop.slug])
        self.client.post(url, {
            'email': guest_email,
            'full_name': 'Guest User',
            'business_name': 'Guest Corp'
        })
        
        # Verify User Created & Token Saved
        user = User.objects.get(email=guest_email)
        self.assertTrue(user.billing_notes, "Token should be saved in billing_notes")
        token = user.billing_notes
        
        # 2. Access Magic Link (Logout first to simulate fresh session)
        self.client.logout()
        access_url = reverse('coaching_booking:guest_access', args=[token])
        response = self.client.get(access_url)
        
        # Verify Redirect & Login
        self.assertRedirects(response, reverse('accounts:account_profile'))
        self.assertEqual(int(self.client.session['_auth_user_id']), user.pk)
        
        # 3. Verify Token Cleared
        user.refresh_from_db()
        self.assertEqual(user.billing_notes, "", "Token should be cleared after use")
        
        # 4. Verify Token cannot be reused
        self.client.logout()
        response = self.client.get(access_url)
        self.assertEqual(response.status_code, 404)

class StaffGuestCreationTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.staff_user = User.objects.create_user(
            username='staff', email='staff@example.com', password='password', is_staff=True
        )
        self.offering = Offering.objects.create(
            name='Premium Coaching Package',
            description='Test Description',
            price=100.00,
            duration_type='PACKAGE',
            total_length_units=1,
            session_length_minutes=60,
            total_number_of_sessions=5,
            active_status=True
        )

    def test_create_guest_with_enrollment_email_content(self):
        """
        Verifies that when a staff member creates a guest and enrolls them,
        the sent email contains the offering name.
        """
        self.client.login(username='staff', password='password')
        guest_email = "vip_guest@example.com"
        
        url = reverse('coaching_booking:staff_create_guest')
        response = self.client.post(url, {
            'email': guest_email,
            'full_name': 'VIP Guest',
            'offering_id': self.offering.id
        })
        
        # Verify Email Content
        self.assertEqual(len(mail.outbox), 1)
        email = mail.outbox[0]
        self.assertIn(guest_email, email.to)
        self.assertIn("Premium Coaching Package", email.body)
        self.assertIn("You have been enrolled in:", email.body)

class GuestCleanupCommandTests(TestCase):
    def test_cleanup_guests_command(self):
        """
        Verifies that the cleanup_guests command deletes old unactivated guests
        but preserves recent guests and activated users.
        """
        # 1. Old Guest (Should be deleted)
        old_guest = User.objects.create_user(
            username='old_guest', email='old@test.com', password='pw'
        )
        old_guest.billing_notes = "token_123" # Unactivated
        old_guest.date_joined = timezone.now() - timedelta(days=31)
        old_guest.save()

        # 2. Recent Guest (Should be kept)
        recent_guest = User.objects.create_user(
            username='recent_guest', email='recent@test.com', password='pw'
        )
        recent_guest.billing_notes = "token_456" # Unactivated
        recent_guest.date_joined = timezone.now() - timedelta(days=10)
        recent_guest.save()

        # 3. Old Activated User (Should be kept)
        activated_user = User.objects.create_user(
            username='activated', email='active@test.com', password='pw'
        )
        activated_user.billing_notes = "" # Activated (empty token)
        activated_user.date_joined = timezone.now() - timedelta(days=40)
        activated_user.save()

        # Run Command
        call_command('cleanup_guests')

        # Verify
        self.assertFalse(User.objects.filter(id=old_guest.id).exists(), "Old guest should be deleted")
        self.assertTrue(User.objects.filter(id=recent_guest.id).exists(), "Recent guest should remain")
        self.assertTrue(User.objects.filter(id=activated_user.id).exists(), "Activated user should remain")