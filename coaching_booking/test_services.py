from django.test import TestCase
from django.utils import timezone
from datetime import datetime, time, date
import pytz

from accounts.models import User, CoachProfile
from coaching_core.models import Workshop
from coaching_booking.services import BookingService

class BookingServiceTests(TestCase):
    def setUp(self):
        self.user = User.objects.create(username='coach', email='coach@test.com', is_coach=True)
        self.coach = CoachProfile.objects.create(user=self.user, time_zone='UTC')
        
        # Create a workshop for tomorrow at 10:00 AM UTC
        self.workshop_date = (timezone.now() + timezone.timedelta(days=1)).date()
        self.workshop_start_time = time(10, 0)
        self.workshop_end_time = time(11, 0)
        
        self.workshop = Workshop.objects.create(
            coach=self.coach,
            name="Test Workshop",
            description="A test workshop",
            price=10.00,
            date=self.workshop_date,
            start_time=self.workshop_start_time,
            end_time=self.workshop_end_time,
            total_attendees=10,
            active_status=True
        )

    def test_get_month_schedule_includes_workshop(self):
        """
        Test that get_month_schedule correctly finds and formats a workshop
        using the new date/time logic.
        """
        year = self.workshop_date.year
        month = self.workshop_date.month
        
        # Call the service method
        schedule = BookingService.get_month_schedule(
            self.coach, 
            year, 
            month, 
            user_timezone_str='UTC'
        )
        
        # Find the day in the schedule corresponding to the workshop
        workshop_day = None
        for day in schedule:
            if day['date'] == self.workshop_date:
                workshop_day = day
                break
        
        self.assertIsNotNone(workshop_day, "Workshop date not found in schedule grid")
        
        # Check if the workshop slot is present
        workshop_slot = None
        for slot in workshop_day['slots']:
            if slot.get('type') == 'WORKSHOP' and slot.get('id') == self.workshop.id:
                workshop_slot = slot
                break
        
        self.assertIsNotNone(workshop_slot, "Workshop slot not found in day slots")
        
        # Verify slot details
        expected_iso = timezone.make_aware(datetime.combine(self.workshop_date, self.workshop_start_time)).isoformat()
        self.assertEqual(workshop_slot['iso_value'], expected_iso)
        self.assertEqual(workshop_slot['title'], "Test Workshop")
        self.assertEqual(workshop_slot['display_time'], "10:00 AM")