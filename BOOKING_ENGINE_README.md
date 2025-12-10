# Django Booking Engine Implementation Guide

This implementation guide consolidates our entire architectural session into a single execution plan. This is your roadmap to building the Django Booking Engine.

## 📁 Project Structure

This is where the new files belong in your coaching app.

```text
coaching/
├── models.py            # Booking, Coach, Workshop, AvailabilityBlock, CoachBusySlot
├── services.py          # The "Brain": BookingService (Get slots, Create booking)
├── views.py             # The "Controller": HTMX partials & Stripe redirects
├── tasks.py             # Celery: Email sending, Google Sync, Hold cleanup
├── signals.py           # Trigger email tasks on booking confirmation
├── utils.py             # Helpers: ICS generation, Magic Links
├── webhooks.py          # Stripe Webhook handler
├── integrations/
│   ├── __init__.py
│   └── google.py        # Google Calendar API logic
├── templates/
│   └── coaching/
│       ├── booking_page.html          # Main container
│       ├── manage_booking.html        # Guest self-service dashboard
│       └── partials/
│           ├── calendar_grid.html     # The Month/Week view
│           ├── booking_form.html      # The Slide-over modal
│           └── booking_success.html   # Confirmation message
```

## 🚀 Phase 1: Data Layer (The Foundation)

Goal: Establish the schema to support flexible scheduling.

- **Refactor models.py**:
  - Create `AvailabilityBlock` (UTC times) for 1-on-1 rules.
  - Update `Booking` to be polymorphic (ForeignKeys to both Coach and Workshop).
  - Add `CoachBusySlot` for the Google Calendar cache.
  - Add Stripe fields (`is_paid`, `amount_paid`) to Booking.
- **Run Migrations**: `makemigrations coaching` -> `migrate`.

## ⚙️ Phase 2: The "Brain" (Logic)

Goal: Decouple logic from views to handle complexity cleanly.

- **Create services.py**:
  - Implement `get_month_schedule(coach, year, month)`:
    - Fetch `AvailabilityBlock`.
    - Subtract `Booking` (Conflicting).
    - Subtract `CoachBusySlot` (Google Busy).
    - Merge Workshop events into the grid.
  - Implement `create_booking(...)`:
    - Handle Race Conditions (`select_for_update` for Workshops).
    - Handle Guest vs User logic.
    - Handle Payment Fork (Return Stripe URL if paid, Booking object if free).

## 🖥️ Phase 3: The Frontend (HTMX + Tailwind)

Goal: A "Single Page App" feel without the JavaScript fatigue.

- **Views (views.py)**:
  - `booking_calendar_view`: Handles the month grid (supports HX-Request for switching months).
  - `confirm_booking_modal`: Returns the slide-over form.
  - `create_booking_view`: Handles the POST. Returns either specific HTMX redirects (for Stripe) or success HTML.
- **Templates**:
  - **Grid**: Use `hx-get` on "Next Month" buttons to swap just the grid `<div>`.
  - **Form**: Use `hx-post` on the form to submit without reload.
  - **Timezones**: Add the JS one-liner in `booking_page.html` to set the `USER_TIMEZONE` cookie.

## 💳 Phase 4: Commerce (Stripe)

Goal: Secure revenue collection.

- **Setup**: Install `stripe`. Add keys to `settings.py`.
- **Checkout**: Update `BookingService` to create Stripe Sessions for paid workshops.
- **Webhook**: Create `webhooks.py` to listen for `checkout.session.completed`.
  - _Crucial_: This is the only place that marks a paid booking as `CONFIRMED`.
- **Cleanup**: Add a Celery task to delete `PENDING_PAYMENT` bookings older than 15 mins.

## 📧 Phase 5: Notifications & Integrations

Goal: Reliability and "Stickiness".

- **Email**:
  - Create `tasks.py` for `send_booking_confirmation_email`.
  - Use `utils.py` to generate the `.ICS` attachment (Calendar file).
  - Use `signals.py` to trigger the task `on_commit` of the DB transaction.
- **Google Sync**:
  - Implement `GoogleCalendarService` in `integrations/google.py`.
  - **Push**: Trigger sync on booking creation.
  - **Pull**: Schedule a Celery Beat task every 15 mins to fetch "Busy" slots.

## 🛠️ Phase 6: Admin & Operations

Goal: Make it usable for the business owner.

- **Admin**: Add the "Bulk Add Slots" tool in `admin.py`.
- **Self-Service**: Create the Magic Link flow (`utils.py` signer) so guests can cancel/reschedule without logging in.

## ✅ Execution Checklist

- [ ] Models defined & migrated.
- [ ] Admin "Bulk Add" tool working.
- [ ] Calendar Grid rendering (Check timezone conversion).
- [ ] Booking Flow (Free) working.
- [ ] Booking Flow (Paid) redirects to Stripe & Webhook confirms it.
- [ ] Emails arriving with .ICS files attached.
- [ ] Google Calendar blocking off slots in your local database.
