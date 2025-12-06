# JH Motiv LTD Django Shop

This is the official repository for the JH Motiv LTD e-commerce and coaching platform, built with Django.

## Project Setup

### Prerequisites

*   Python 3.9+
*   PostgreSQL
*   An active virtual environment

### Installation

1.  **Clone the repository:**
    ```bash
    git clone https://github.com/your-username/JH_Motiv_LTD_Django_Repo.git
    cd JH_Motiv_LTD_Django_Repo
    ```

2.  **Install dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

3.  **Set up the Environment File:**

    Create a `.env` file in the root of the project. This file is used to store sensitive credentials and environment-specific settings. Copy the contents of `.env.example` (or create it from scratch) and fill in the required values.

    ```dotenv
    # .env

    # Django Core
    SECRET_KEY='your-super-secret-key'
    DEBUG='True' # Set to 'False' in production
    
    # Database (Heroku-style URL)
    # Example for local development: postgres://user:password@localhost:5432/dbname
    DATABASE_URL='your-database-url'

    # Email (Gmail SMTP with App Password)
    GMAIL_HOST_USER='your-email@gmail.com'
    GMAIL_APP_PASSWORD='your-16-character-app-password'
    DEFAULT_FROM_EMAIL='your-from-email@example.com'

    # Cloudinary (for media storage)
    CLOUDINARY_CLOUD_NAME='your-cloud-name'
    CLOUDINARY_API_KEY='your-api-key'
    CLOUDINARY_API_SECRET='your-api-secret'

    # Google API (for Calendar integration)
    GOOGLE_OAUTH2_CLIENT_ID='your-google-client-id'
    GOOGLE_OAUTH2_CLIENT_SECRET='your-google-client-secret'
    # This should match the authorized redirect URI in your Google Cloud project
    GOOGLE_OAUTH2_REDIRECT_URI='http://localhost:8000/accounts/google/login/callback/'

    # Stripe (for payments)
    STRIPE_PUBLISHABLE_KEY='pk_test_yourpublickey'
    STRIPE_SECRET_KEY='sk_test_yoursecretkey'
    STRIPE_WEBHOOK_SECRET='whsec_yourwebhooksecret'

    # Printful (for merchandise fulfillment)
    PRINTFUL_API_KEY='your-printful-api-key'
    PRINTFUL_STORE_ID='your-store-id'
    PRINTFUL_WEBHOOK_SECRET='your-printful-webhook-secret'

    # Field Encryption
    FIELD_ENCRYPTION_KEY='your-fernet-encryption-key'

    # Heroku (Optional, for production deployment)
    HEROKU_APP_NAME='your-heroku-app-name'
    ```

4.  **Run database migrations:**
    ```bash
    python manage.py migrate
    ```

5.  **Create a superuser:**
    ```bash
    python manage.py createsuperuser
    ```

6.  **Run the development server:**
    ```bash
    python manage.py runserver
    ```
    The application will be available at `http://127.0.0.1:8000/`.


## Running Tests

To run the test suite for a specific application, use the `test` command. For example, to run tests for the `coaching_booking` app:

```bash
python manage.py test coaching_booking
```

To run all tests for the project:

```bash
python manage.py test
```