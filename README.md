# JH Motiv: The Real-Life RPG Platform 🎮

> **"Stop Living Like an NPC."**

This is the official repository for **JH Motiv LTD**, a gamified e-commerce and coaching platform built with **Django 5**. It bridges the gap between high-performance coaching ("Strategy") and streetwear ("Armor"), treating personal development like a video game where users equip gear, unlock strategies, and level up their real lives.

## 🚀 Project Overview

This project is a sophisticated hybrid application that combines a full-featured **Print-on-Demand E-Commerce store** with a custom **Coaching Booking Engine**. The frontend is heavily interactive, utilizing a "Htmx + Alpine.js" stack to deliver a single-page-application (SPA) feel without the complexity of React or Vue.

### Key Features

#### 🛡️ The Armory (E-Commerce)
* **Print-on-Demand Integration:** Deep integration with the **Printful API** for automated product syncing, webhooks, and order fulfillment.
* **Dynamic Inventory:** Smart stock management using `StockPools` to handle shared inventory across different product variants.
* **Gamified Cart:** "Loot" terminology, visual feedback, and a robust coupon system with "Free Shipping" overrides.
* **Seasonal Themes:** The site automatically adapts its visuals (banners, footers) based on the real-world season, or via user "cheat codes."

#### 🗺️ Strategy Guide (Coaching Engine)
* **Custom Booking System:** A dedicated engine (`coaching_booking`) handling 1:1 sessions, workshops, and taster sessions.
* **Google Calendar Sync:** Two-way synchronization using Google OAuth2 to prevent double bookings and manage coach availability.
* **Timezone Intelligence:** Automatic conversion between coach and client timezones for seamless international scheduling.
* **Stripe Payments:** Secure, integrated checkout flows for high-ticket coaching packages.

#### 👾 The "Cheat Code" Engine
* **Konami Code Support:** A global JavaScript event listener allows users to enter the classic Konami code to unlock secret coupons.
* **Visual Mods:** Users can type keywords like `doom` (Nightmare Mode) or `bighead` (NBA Jam style) to alter the UI in real-time.
* **Persistence:** Cheat states are saved in `localStorage`, persisting across page navigations for a consistent experience.
* **Error Simulation:** Hidden commands to safely trigger and view custom 403, 404, and 500 error pages.

---

## 🛠️ Tech Stack

### Backend
* **Framework:** Python 3.12+, Django 5.2.7
* **Database:** PostgreSQL (via `dj-database-url`)
* **Task Queue:** Celery 5.6 + Redis 7.1 (handling emails, webhooks, and calendar sync)
* **Server:** Gunicorn / Uvicorn (ASGI supported)

### Frontend
* **Styling:** Tailwind CSS (via `django-tailwind`)
* **Interactivity:** Alpine.js 3.x, HTMX 1.9
* **Components:** Django Unicorn (for reactive components)
* **Templating:** Standard Django Templates with partials

### Integrations
* **Payments:** Stripe API
* **Fulfillment:** Printful API
* **Scheduling:** Google Calendar API
* **Storage:** Cloudinary (Media files)
* **Email:** Gmail SMTP / SendGrid (Production)

---

## 💻 Project Setup

### Prerequisites
* Python 3.10+
* PostgreSQL
* Redis (Required for Celery tasks)
* Node.js & NPM (Required for Tailwind CSS build process)

### Installation Guide

1.  **Clone the Repository:**
    ```bash
    git clone [https://github.com/your-username/JH_Motiv_LTD_Django_Repo.git](https://github.com/your-username/JH_Motiv_LTD_Django_Repo.git)
    cd JH_Motiv_LTD_Django_Repo
    ```

2.  **Set up Virtual Environment:**
    ```bash
    python -m venv venv
    source venv/bin/activate  # On Windows: venv\Scripts\activate
    ```

3.  **Install Python Dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

4.  **Install Frontend Dependencies (Tailwind):**
    ```bash
    python manage.py tailwind install
    ```

5.  **Configure Environment Variables:**
    Create a `.env` file in the root directory. Use the template below:

    ```dotenv
    # Core
    SECRET_KEY='your-super-secret-key'
    DEBUG=True
    ALLOWED_HOSTS=127.0.0.1,localhost
    HEROKU_APP_NAME='jhmotiv-local'

    # Database
    DATABASE_URL='postgres://user:password@localhost:5432/jhmotiv_db'

    # Payments & Commerce
    STRIPE_PUBLISHABLE_KEY='pk_test_...'
    STRIPE_SECRET_KEY='sk_test_...'
    STRIPE_WEBHOOK_SECRET='whsec_...'
    
    PRINTFUL_API_KEY='your-printful-key'
    PRINTFUL_STORE_ID='your-store-id'
    PRINTFUL_WEBHOOK_SECRET='your-printful-webhook-secret'

    # Google Integrations (Calendar & Auth)
    GOOGLE_OAUTH2_CLIENT_ID='...'
    GOOGLE_OAUTH2_CLIENT_SECRET='...'
    GOOGLE_OAUTH2_REDIRECT_URI='http://localhost:8000/accounts/google/login/callback/'
    
    # Media Storage
    CLOUDINARY_CLOUD_NAME='...'
    CLOUDINARY_API_KEY='...'
    CLOUDINARY_API_SECRET='...'
    CLOUDINARY_URL='cloudinary://...'

    # Email (Gmail SMTP)
    GMAIL_HOST_USER='your-email@gmail.com'
    GMAIL_APP_PASSWORD='your-app-password'
    
    # Cache / Celery
    REDIS_URL='redis://localhost:6379/0'
    ```

6.  **Initialize Database:**
    ```bash
    python manage.py migrate
    ```

7.  **Build CSS:**
    In a separate terminal, start the Tailwind watcher:
    ```bash
    python manage.py tailwind start
    ```

8.  **Run Development Server:**
    ```bash
    python manage.py runserver
    ```

9.  **Run Celery Worker (Optional - for Async Tasks):**
    ```bash
    celery -A JH_Motiv_Shop worker -l info
    ```

---

## 🕹️ Developer Cheats (Easter Eggs)

The site includes a hidden debug and entertainment layer powered by `static/js/konami_cheat.js`. Type these codes anywhere on the site to trigger effects.

| Code Sequence | Effect | Description |
| :--- | :--- | :--- |
| **`↑ ↑ ↓ ↓ ← → ← → B A`** | 🎁 Loot Drop | The "Konami Code". Generates a 10% Off + Free Shipping coupon for the user. |
| **`devmode`** | 👨‍💻 Matrix UI | Toggles a high-contrast green-on-black terminal theme. |
| **`doom`** | 😈 Nightmare | Applies a high-contrast red/black visual filter. |
| **`bighead`** | 🏀 Big Head | Scales up all images on the page by 150%. |
| **`fps`** | ⚡ Stats | Toggles a fake FPS counter in the top corner. |
| **`winter`** | ❄️ Winter | Manually forces the Winter seasonal theme. |
| **`summer`** | ☀️ Summer | Manually forces the Summer seasonal theme. |
| **`spring`** | 🌸 Spring | Manually forces the Spring seasonal theme. |
| **`fall`** | 🍂 Fall | Manually forces the Fall seasonal theme. |
| **`seasonpass`** | 🔄 Reset Time | Resets the theme to match the server's actual current date. |
| **`loot`** | 💰 Inventory | Instantly redirects you to the Cart. |
| **`idkfa`** | 🌀 God Mode | Rotates the screen 180 degrees (Temporary). |
| **`ban`** | ⛔ 403 Sim | Simulates the 403 Forbidden error page. |
| **`lost`** | 🗺️ 404 Sim | Simulates the 404 Not Found error page. |
| **`crash`** | 🔥 500 Sim | Simulates the 500 Server Error page. |

---

## 🧪 Running Tests

To ensure the booking engine, payments, and integrations work as expected:

```bash
# Run all tests
python manage.py test

# Run specific app tests (e.g., Booking Logic)
python manage.py test coaching_booking

# Run payment calculation tests
python manage.py test payments