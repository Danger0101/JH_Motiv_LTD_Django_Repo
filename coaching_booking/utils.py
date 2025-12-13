import uuid
from datetime import datetime
from django.conf import settings
from django.utils import timezone
import pytz

def generate_ics(booking):
    """
    Generates a VCALENDAR 2.0 string for a booking.
    Returns bytes content and a filename.
    """
    # 1. Determine Title & Description
    if booking.workshop:
        summary = f"Workshop: {booking.workshop.title}"
        description = f"Join {booking.workshop.coach.user.get_full_name()} for an interactive workshop."
    else:
        summary = f"1-on-1: {booking.coach.user.get_full_name()}"
        description = "Private coaching session."

    # 2. Format Dates (Must be UTC format: YYYYMMDDTHHMMSSZ)
    def to_ics_format(dt):
        # Ensure dt is in UTC
        if timezone.is_aware(dt):
            dt = dt.astimezone(pytz.utc)
        return dt.strftime('%Y%m%dTH%H%M%SZ')

    dt_start = to_ics_format(booking.start_datetime)
    dt_end = to_ics_format(booking.end_datetime)
    dt_stamp = to_ics_format(timezone.now())
    
    # Unique ID for the event
    domain = settings.ALLOWED_HOSTS[0] if settings.ALLOWED_HOSTS else "example.com"
    if domain == '*':
        domain = "example.com"
        
    uid = f"{booking.id}-{uuid.uuid4()}@{domain}"

    # 3. Construct the ICS Content (Strict RFC 5545 format)
    ics_content = f"""BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//Your Company//Coaching App//EN
CALSCALE:GREGORIAN
METHOD:PUBLISH
BEGIN:VEVENT
UID:{uid}
DTSTAMP:{dt_stamp}
DTSTART:{dt_start}
DTEND:{dt_end}
SUMMARY:{summary}
DESCRIPTION:{description}
STATUS:CONFIRMED
END:VEVENT
END:VCALENDAR"""

    # Return bytes and a clean filename
    filename = "booking_invite.ics"
    return ics_content.encode('utf-8'), filename