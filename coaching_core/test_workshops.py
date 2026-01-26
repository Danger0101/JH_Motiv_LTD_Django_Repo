from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone
from datetime import timedelta

from accounts.models import User, CoachProfile
from coaching_core.models import Workshop
from coaching_booking.models import SessionBooking
from coaching_core.forms import WorkshopBookingForm


class WorkshopViewsTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username='testuser', email='test@example.com', password='password')
        self.coach_user = User.objects.create_user(username='coachuser', email='coach@example.com', password='password', is_coach=True)
        self.coach_profile = CoachProfile.objects.create(user=self.coach_user)

        self.workshop = Workshop.objects.create(
            coach=self.coach_profile,
            name="Test Workshop",
            description="A workshop for testing.",
            price=100.00,
            date=timezone.now().date() + timedelta(days=10),
            start_time=timezone.now().time(),
            end_time=(timezone.now() + timedelta(hours=1)).time(),
            total_attendees=10,
        )

    def test_coach_landing_view(self):
        response = self.client.get(reverse('coaching_booking:coach_landing'))
        self.assertEqual(response.status_code, 200)
        self.assertIn('upcoming_workshops', response.context)
        self.assertIn(self.workshop, response.context['upcoming_workshops'])

    def test_workshop_detail_view(self):
        response = self.client.get(reverse('coaching_core:workshop_detail', kwargs={'slug': self.workshop.slug}))
        self.assertEqual(response.status_code, 200)
        self.assertIn('form', response.context)
        self.assertIsInstance(response.context['form'], WorkshopBookingForm)

    def test_workshop_detail_view_invalid(self):
        response = self.client.get(reverse('coaching_core:workshop_detail', kwargs={'slug': 'invalid-slug'}))
        self.assertEqual(response.status_code, 404)

    def test_workshop_booking_form_valid(self):
        form_data = {'full_name': 'Test User', 'email': 'test@example.com'}
        form = WorkshopBookingForm(data=form_data)
        self.assertTrue(form.is_valid())

    def test_workshop_booking_form_invalid(self):
        form_data = {'full_name': '', 'email': 'not-an-email'}
        form = WorkshopBookingForm(data=form_data)
        self.assertFalse(form.is_valid())

    def test_unauthenticated_user_booking(self):
        response = self.client.post(reverse('coaching_booking:book_workshop', kwargs={'slug': self.workshop.slug}), {
            'full_name': 'New User',
            'email': 'newuser@example.com',
        })
        self.assertEqual(response.status_code, 302) # Redirects to profile
        self.assertTrue(User.objects.filter(email='newuser@example.com').exists())
        new_user = User.objects.get(email='newuser@example.com')
        self.assertTrue(SessionBooking.objects.filter(client=new_user, workshop=self.workshop).exists())

    def test_authenticated_user_booking(self):
        self.client.login(username='testuser', password='password')
        response = self.client.post(reverse('coaching_booking:book_workshop', kwargs={'slug': self.workshop.slug}), {
            'full_name': self.user.get_full_name(),
            'email': self.user.email,
        })
        self.assertEqual(response.status_code, 302) # Redirects to profile
        self.assertTrue(SessionBooking.objects.filter(client=self.user, workshop=self.workshop).exists())

    def test_booking_full_workshop(self):
        self.workshop.total_attendees = 1
        self.workshop.save()
        
        # First user books
        user1 = User.objects.create_user(username='user1', email='user1@example.com', password='password')
        SessionBooking.objects.create(client=user1, workshop=self.workshop, status='BOOKED')

        # Second user tries to book
        self.client.login(username='testuser', password='password')
        response = self.client.post(reverse('coaching_booking:book_workshop', kwargs={'slug': self.workshop.slug}), {
            'full_name': self.user.get_full_name(),
            'email': self.user.email,
        })
        # The view redirects to the workshop detail page with a message
        self.assertEqual(response.status_code, 302)
        # Check that the second user was not booked
        self.assertFalse(SessionBooking.objects.filter(client=self.user, workshop=self.workshop).exists())
