from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.core import mail
from django.contrib.auth.tokens import default_token_generator
from django.utils.http import urlsafe_base64_encode
from django.utils.encoding import force_bytes

User = get_user_model()

class AuthenticationTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user_password = 'TestPassword123!'
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password=self.user_password,
            first_name='Test',
            last_name='User'
        )

    def test_signup_duplicate_email(self):
        """
        Verify that signing up with an existing email raises a validation error
        and suggests password reset.
        """
        url = reverse('accounts:signup')
        reset_url = reverse('accounts:password_reset')
        data = {
            'username': 'newuser',
            'email': 'test@example.com', # Existing email
            'password': 'NewPassword123!',
            'first_name': 'New',
            'last_name': 'User',
            'policy_agreement': True
        }
        response = self.client.post(url, data)
        
        self.assertEqual(response.status_code, 200) # Should re-render form with errors
        
        expected_error = f'An account with this email already exists. <a href="{reset_url}" class="text-indigo-600 hover:text-indigo-500 underline">Forgot your password?</a>'
        self.assertFormError(response, 'form', 'email', expected_error)

    def test_deactivate_account(self):
        """
        Verify account deactivation flow: user becomes inactive and email is sent.
        """
        self.client.login(username='testuser', password=self.user_password)
        url = reverse('accounts:deactivate_account')
        
        # GET request should render confirmation page
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'account/deactivate_confirm.html')

        # POST request should deactivate
        response = self.client.post(url)
        
        # Refresh user from DB
        self.user.refresh_from_db()
        
        self.assertFalse(self.user.is_active)
        self.assertRedirects(response, reverse('accounts:login'))
        
        # Check email sent
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("Account Deactivated - Reactivation Link", mail.outbox[0].subject)
        self.assertIn(self.user.username, mail.outbox[0].body)

    def test_reactivate_account(self):
        """
        Verify account reactivation via token link.
        """
        # Deactivate user first
        self.user.is_active = False
        self.user.save()
        
        # Generate valid token
        token = default_token_generator.make_token(self.user)
        uid = urlsafe_base64_encode(force_bytes(self.user.pk))
        
        url = reverse('accounts:reactivate_account', kwargs={'uidb64': uid, 'token': token})
        
        response = self.client.get(url)
        
        self.user.refresh_from_db()
        self.assertTrue(self.user.is_active)
        self.assertRedirects(response, reverse('accounts:password_change'))

    def test_reactivate_account_invalid_token(self):
        """
        Verify reactivation fails with invalid token.
        """
        self.user.is_active = False
        self.user.save()
        
        uid = urlsafe_base64_encode(force_bytes(self.user.pk))
        url = reverse('accounts:reactivate_account', kwargs={'uidb64': uid, 'token': 'invalid-token'})
        
        response = self.client.get(url)
        
        self.user.refresh_from_db()
        self.assertFalse(self.user.is_active)
        self.assertRedirects(response, reverse('accounts:login'))

    def test_password_reset_from_key_invalid_token(self):
        """
        Verify that accessing the password reset view with an invalid token
        renders the correct template with token_fail=True.
        """
        invalid_key = 'invalid-key'
        url = reverse('accounts:account_reset_password_from_key', kwargs={'key': invalid_key})
        
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'account/password_reset_from_key.html')
        self.assertTrue(response.context.get('token_fail'))

    def test_email_confirmation_url_reversal(self):
        """
        Verify that the email confirmation URL can be reversed correctly.
        """
        key = 'some-random-key'
        url = reverse('accounts:account_confirm_email', kwargs={'key': key})
        self.assertEqual(url, f'/accounts/confirm-email/{key}/')