from django.utils.text import slugify

# --- STANDARD COACHING OFFERINGS ---
# These packages are designed for consistent, bi-weekly (every two weeks) sessions.
# Price is the total investment for the package.

COACHING_PACKAGES = [
    {
        'name': 'Mindset to Systems',
        'description': 'Build one core revenue-generating system (e.g., lead generation, sales process) to reduce chaos and create consistency.',
        'price': '3500.00',
        'duration_type': 'MONTH',
        'total_length_units': 3,
        'session_length_minutes': 90,
        'total_number_of_sessions': 6,  # Bi-weekly for 3 months
        'is_whole_day': False,
    },
    {
        'name': 'Mindset-to-Momentum Blueprint',
        'description': 'Full mindset transformation, system implementation, and guaranteed accountability for sustained, measurable business growth. Your flagship program.',
        'price': '5900.00',
        'duration_type': 'MONTH',
        'total_length_units': 6,
        'session_length_minutes': 90,
        'total_number_of_sessions': 12,  # Bi-weekly for 6 months
        'is_whole_day': False,
    },
    {
        'name': 'Advanced Growth Partnership',
        'description': 'Extended support for scaling established systems, team building, and leadership development, ensuring nine months of continuous forward motion.',
        'price': '8250.00',
        'duration_type': 'MONTH',
        'total_length_units': 9,
        'session_length_minutes': 90,
        'total_number_of_sessions': 18,  # Bi-weekly for 9 months
        'is_whole_day': False,
    },
    {
        'name': 'Executive Scale Mastermind',
        'description': 'A year-long retainer for continuous executive coaching, strategy, maximizing long-term legacy goals, and strategic course correction.',
        'price': '11200.00',
        'duration_type': 'MONTH',
        'total_length_units': 12,
        'session_length_minutes': 90,
        'total_number_of_sessions': 24,  # Bi-weekly for 12 months
        'is_whole_day': False,
    },
]

# --- PREMIUM IMMERSION OFFERING ---
# This is a one-time, high-value in-person service.

PREMIUM_OFFERINGS = [
    {
        'name': 'London Executive Immersion',
        'description': 'A full 8-hour day 1:1 in London. I coach you in real-time by shadowing your workflow, observing key meetings, and immediately refining systems and mindset blocks as they happen. Includes a strategic lunch/dinner and a comprehensive Action Plan document compiled afterward.',
        'price': '4500.00',
        'duration_type': 'PACKAGE',
        'total_length_units': 1,
        'session_length_minutes': 480, # 8 hours
        'total_number_of_sessions': 1,
        'is_whole_day': True,
    },
]

# --- COMBINED DATA LIST FOR DATABASE IMPORT ---
# This is the final list that should be iterated over for database insertion.
ALL_COACHING_OFFERINGS_DATA = COACHING_PACKAGES + PREMIUM_OFFERINGS
