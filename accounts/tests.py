from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from django.urls import reverse

# Use a try-except block similar to the views to handle model availability
try:
    from payments.models import Order
except ImportError:
    Order = None

User = get_user_model()

class StaffViewPermissionsTest(TestCase):
    """
    Tests to ensure that staff-only views are properly protected.
    """

    @classmethod
    def setUpTestData(cls):
        """Set up users and a test order for all tests in this class."""
        cls.regular_user = User.objects.create_user(
            username='testuser',
            email='testuser@example.com',
            password='password123',
            is_staff=False
        )

        cls.staff_user = User.objects.create_user(
            username='staffuser',
            email='staffuser@example.com',
            password='password123',
            is_staff=True
        )

        # Create a test order if the Order model is available
        if Order:
            cls.order = Order.objects.create(user=cls.regular_user, total_paid='99.99')
            cls.update_order_url = reverse('accounts:staff_update_order', args=[cls.order.id])
        else:
            cls.order = None
            cls.update_order_url = None # Cannot generate URL without an order

        cls.customer_lookup_url = reverse('accounts:staff_customer_lookup')
        cls.login_url = reverse('accounts:login')

    def test_staff_customer_lookup_unauthenticated(self):
        """Test that unauthenticated users are redirected from staff_customer_lookup."""
        response = self.client.get(self.customer_lookup_url)
        self.assertEqual(response.status_code, 302)
        self.assertIn(self.login_url, response.url)

    def test_staff_customer_lookup_non_staff(self):
        """Test that non-staff authenticated users are redirected."""
        self.client.login(username='testuser', password='password123')
        response = self.client.get(self.customer_lookup_url)
        self.assertEqual(response.status_code, 302)
        self.assertIn(self.login_url, response.url)

    def test_staff_customer_lookup_staff_access(self):
        """Test that staff users can access the customer lookup view."""
        self.client.login(username='staffuser', password='password123')
        response = self.client.get(self.customer_lookup_url)
        self.assertEqual(response.status_code, 200)

    def test_staff_update_order_unauthenticated(self):
        """Test that unauthenticated users are redirected from staff_update_order."""
        if not self.update_order_url:
            self.skipTest("Order model not available, skipping test.")
        response = self.client.get(self.update_order_url)
        self.assertEqual(response.status_code, 302)
        self.assertIn(self.login_url, response.url)

    def test_staff_update_order_non_staff(self):
        """Test that non-staff authenticated users are redirected."""
        if not self.update_order_url:
            self.skipTest("Order model not available, skipping test.")
        self.client.login(username='testuser', password='password123')
        response = self.client.get(self.update_order_url)
        self.assertEqual(response.status_code, 302)
        self.assertIn(self.login_url, response.url)

    def test_staff_update_order_staff_access_get(self):
        """Test that staff users can access the update order form (GET)."""
        if not self.update_order_url:
            self.skipTest("Order model not available, skipping test.")
        self.client.login(username='staffuser', password='password123')
        response = self.client.get(self.update_order_url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'account/partials/staff_order_form.html')

    def test_staff_update_order_staff_access_post(self):
        """Test that staff users can submit the update order form (POST)."""
        if not self.update_order_url:
            self.skipTest("Order model not available, skipping test.")
        self.client.login(username='staffuser', password='password123')
        post_data = {'status': 'SHIPPED', 'carrier': 'TestCarrier'}
        response = self.client.post(self.update_order_url, post_data)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'account/partials/staff_order_row.html')
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, 'SHIPPED')
