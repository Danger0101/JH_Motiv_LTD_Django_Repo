from django.test import TestCase
from django.utils import timezone
from dateutil.relativedelta import relativedelta
from django.contrib.auth import get_user_model
from .models import SessionCredit, UserOffering, CoachOffering

User = get_user_model()

class SessionCreditModelTests(TestCase):

    def setUp(self):
        """Set up non-modified objects used by all test methods."""
        self.user = User.objects.create_user(username='testuser', password='password')
        self.coach = User.objects.create_user(username='testcoach', password='password', is_coach=True)
        
        self.offering = CoachOffering.objects.create(
            name="Test Program",
            description="A test program.",
            duration_minutes=60,
            price=100.00,
            credits_granted=4,
            duration_months=3
        )
        self.offering.coaches.add(self.coach)

    def test_taster_credit_expiration(self):
        """
        Test that a taster credit (not linked to a UserOffering)
        expires 365 days from its purchase date.
        """
        credit = SessionCredit.objects.create(user=self.user, is_taster=True)
        expected_expiration = credit.purchase_date + timezone.timedelta(days=365)
        self.assertAlmostEqual(credit.expiration_date, expected_expiration, delta=timezone.timedelta(seconds=1))
        self.assertTrue(credit.is_valid())

    def test_user_offering_credit_expiration(self):
        """
        Test that a credit linked to a UserOffering expires on the
        UserOffering's end_date.
        """
        user_offering = UserOffering.objects.create(
            user=self.user,
            offering=self.offering,
            purchase_date=timezone.now().date()
        )
        credit = SessionCredit.objects.create(user=self.user, user_offering=user_offering)

        # The expiration should be the end of the day of the user_offering's end_date
        expected_expiration = timezone.make_aware(
            timezone.datetime.combine(user_offering.end_date, timezone.datetime.max.time())
        )
        self.assertEqual(credit.expiration_date, expected_expiration)
        self.assertTrue(credit.is_valid())

    def test_is_valid_false_when_expired(self):
        """
        Test that is_valid() returns False for an expired credit.
        """
        credit = SessionCredit.objects.create(user=self.user, is_taster=True)
        # Manually set the expiration date to the past
        credit.expiration_date = timezone.now() - timezone.timedelta(days=1)
        credit.save()
        self.assertFalse(credit.is_valid())

    def test_is_valid_false_when_session_used(self):
        """
        Test that is_valid() returns False when the credit is linked to a session.
        """
        # In a real scenario, a CoachingSession object would be created and linked.
        # For this test, we can simulate it by assigning a non-null value to the session field.
        # This requires creating a dummy session instance first.
        from .models import CoachingSession
        session = CoachingSession.objects.create(
            coach=self.coach,
            client=self.user,
            start_time=timezone.now(),
            offering=self.offering
        )
        credit = SessionCredit.objects.create(user=self.user, session=session)
        self.assertFalse(credit.is_valid())
