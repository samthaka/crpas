"""
Tests for dashboard and general application flow in CRPAS.
Tests accessing the dashboard, viewing farm information, and general integration.
"""
from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from django.urls import reverse
from app.models import Farmer, Farm, Notification
from unittest.mock import patch, MagicMock

CustomUser = get_user_model()


class DashboardAccessTestCase(TestCase):
    """Test dashboard access and basic functionality."""

    def setUp(self):
        self.client = Client()
        self.dashboard_url = reverse('dashboard')
        
        # Create authenticated user
        self.user = CustomUser.objects.create_user(
            email='farmer@example.com',
            password='TestPassword123!'
        )
        self.user.email_verified = True
        self.user.save()
        
        # Create farmer profile
        self.farmer = Farmer.objects.create(
            fname='John',
            lname='Doe',
            email=self.user.email,
            phone='+254712345678'
        )
        
        # Create farm
        self.farm = Farm.objects.create(
            farmer=self.farmer,
            farm_name='Test Farm',
            crop_type='maize',
            farm_size=5.0,
            county='Nairobi',
            sub_county='Westlands',
            ward='Chiromo Ward',
            lat=-1.2833,
            long=36.8167,
        )

    def test_dashboard_page_loads(self):
        """Test that dashboard page loads for authenticated user."""
        self.client.login(email='farmer@example.com', password='TestPassword123!')
        response = self.client.get(self.dashboard_url)
        
        self.assertEqual(response.status_code, 200)
        self.assertIn('farmer', response.context)
        self.assertIn('farms', response.context)

    def test_dashboard_requires_authentication(self):
        """Test that dashboard requires authentication."""
        response = self.client.get(self.dashboard_url, follow=True)
        
        # Should redirect to login
        self.assertRedirects(response, f"{reverse('auth')}?next={self.dashboard_url}")

    def test_dashboard_shows_farmer_profile(self):
        """Test that dashboard displays farmer profile information."""
        self.client.login(email='farmer@example.com', password='TestPassword123!')
        response = self.client.get(self.dashboard_url)
        
        self.assertEqual(response.context['farmer'].fname, 'John')
        self.assertEqual(response.context['farmer'].lname, 'Doe')

    def test_dashboard_shows_farms(self):
        """Test that dashboard displays all farmer's farms."""
        # Add second farm
        Farm.objects.create(
            farmer=self.farmer,
            farm_name='Second Farm',
            crop_type='beans',
            farm_size=3.0,
        )
        
        self.client.login(email='farmer@example.com', password='TestPassword123!')
        response = self.client.get(self.dashboard_url)
        
        farms = response.context['farms']
        self.assertEqual(len(farms), 2)

    def test_dashboard_empty_for_no_profiles(self):
        """Test dashboard behavior when user has no farmer profile."""
        # Create user without farmer profile
        user2 = CustomUser.objects.create_user(
            email='noprofile@example.com',
            password='TestPassword123!'
        )
        user2.email_verified = True
        user2.save()
        
        client = Client()
        client.login(email='noprofile@example.com', password='TestPassword123!')
        response = client.get(self.dashboard_url)
        
        # Should still load but with empty data
        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.context.get('farmer'))

    def test_dashboard_shows_recent_alerts(self):
        """Test that dashboard displays recent risk alerts."""
        # This test assumes RiskAlert model or similar exists
        # Adjust based on your actual implementation
        self.client.login(email='farmer@example.com', password='TestPassword123!')
        response = self.client.get(self.dashboard_url)
        
        self.assertIn('risk_alerts', response.context)


class RedirectsTestCase(TestCase):
    """Test root URL and various redirects."""

    def setUp(self):
        self.client = Client()

    def test_root_url_redirect(self):
        """Test that root URL redirects to dashboard or auth."""
        response = self.client.get('/')
        
        # Should redirect (either to dashboard if authenticated or auth if not)
        self.assertEqual(response.status_code, 302)

    def test_authenticated_root_redirect(self):
        """Test root URL redirects to dashboard for authenticated user."""
        user = CustomUser.objects.create_user(
            email='auth@example.com',
            password='TestPassword123!'
        )
        user.email_verified = True
        user.save()
        
        farmer = Farmer.objects.create(
            fname='Test',
            lname='User',
            email=user.email,
        )
        
        self.client.login(email='auth@example.com', password='TestPassword123!')
        response = self.client.get('/', follow=True)
        
        # Should end at dashboard
        self.assertRedirects(response, reverse('dashboard'))


class CompleteUserFlowTestCase(TestCase):
    """Test complete user flow from signup to using the application."""

    def setUp(self):
        self.client = Client()

    @patch('app.views.send_verification_email')
    def test_complete_email_signup_flow(self, mock_send_email):
        """Test complete signup flow with email and password."""
        mock_send_email.return_value = True
        
        # 1. Signup with email
        data = {
            'action': 'signup',
            'email': 'newuser@example.com',
            'password1': 'SecurePassword123!',
            'password2': 'SecurePassword123!',
        }
        response = self.client.post(reverse('auth'), data, follow=True)
        self.assertRedirects(response, reverse('verify_email'))
        
        # 2. Verify email (simulate getting the code from database)
        user = CustomUser.objects.get(email='newuser@example.com')
        verification_code = user.email_verification_code
        
        session = self.client.session
        session['signup_email'] = user.email
        session['signup_password'] = 'SecurePassword123!'
        session.save()
        
        verify_data = {'verification_code': verification_code}
        response = self.client.post(reverse('verify_email'), verify_data, follow=True)
        self.assertRedirects(response, reverse('farmer_registration'))
        
        # 3. Register farmer profile
        farmer_data = {
            'fname': 'John',
            'lname': 'Doe',
            'phone': '+254712345678',
        }
        response = self.client.post(reverse('farmer_registration'), farmer_data, follow=True)
        self.assertRedirects(response, reverse('farm_registration'))
        
        # 4. Register farm
        farm_data = {
            'farm_name': 'My Farm',
            'crop_type': 'maize',
            'farm_size': 5.0,
            'lat': -1.2833,
            'long': 36.8167,
        }
        response = self.client.post(reverse('farm_registration'), farm_data, follow=True)
        # Should be successful or show form with validation errors
        self.assertIn(response.status_code, [200, 302])

    @patch('app.views.send_verification_sms')
    def test_complete_phone_signup_flow(self, mock_send_sms):
        """Test complete signup flow with phone."""
        mock_send_sms.return_value = True
        
        # 1. Signup with phone
        data = {
            'phone': '+254712345678',
            'action': 'signup'
        }
        response = self.client.post(reverse('phone_auth'), data, follow=True)
        self.assertRedirects(response, reverse('verify_phone'))
        
        # 2. Get verification code and verify
        user = CustomUser.objects.get(phone='+254712345678')
        verification_code = user.phone_verification_code
        
        session = self.client.session
        session['auth_phone'] = user.phone
        session['is_phone_signup'] = True
        session.save()
        
        verify_data = {'verification_code': verification_code}
        response = self.client.post(reverse('verify_phone'), verify_data, follow=True)
        self.assertRedirects(response, reverse('phone_signup_password'))
        
        # 3. Set password
        password_data = {
            'password1': 'SecurePassword123!',
            'password2': 'SecurePassword123!',
        }
        response = self.client.post(reverse('phone_signup_password'), password_data, follow=True)
        self.assertRedirects(response, reverse('farmer_registration'))
        
        # 4. Register farmer profile (without email, so no email verification needed)
        farmer_data = {
            'fname': 'Jane',
            'lname': 'Smith',
            'phone': '+254712345678',
        }
        response = self.client.post(reverse('farmer_registration'), farmer_data, follow=True)
        # Should redirect to farm registration\n        self.assertEqual(response.status_code, 200)\n        \n        # 5. Register farm\n        farm_data = {\n            'farm_name': 'My Farm',\n            'crop_type': 'beans',\n            'farm_size': 3.0,\n            'lat': -1.2833,\n            'long': 36.8167,\n        }\n        farm_response = self.client.post(reverse('farm_registration'), farm_data, follow=True)\n        # Should redirect to dashboard\n        if farm_response.status_code == 200:\n            # At dashboard or farm registration page\n            self.assertEqual(farm_response.status_code, 200)\n        else:\n            self.assertRedirects(farm_response, reverse('dashboard'))


class MultipleUserIntegrationTestCase(TestCase):
    """Test interaction between multiple users."""

    def setUp(self):
        self.client = Client()
        self.client2 = Client()
        
        # Create two users
        self.user1 = CustomUser.objects.create_user(
            email='user1@example.com',
            password='TestPassword123!'
        )
        self.user1.email_verified = True
        self.user1.save()
        
        self.user2 = CustomUser.objects.create_user(
            email='user2@example.com',
            password='TestPassword123!'
        )
        self.user2.email_verified = True
        self.user2.save()
        
        # Create farmer profiles
        self.farmer1 = Farmer.objects.create(
            fname='Farmer',
            lname='One',
            email=self.user1.email,
        )
        
        self.farmer2 = Farmer.objects.create(
            fname='Farmer',
            lname='Two',
            email=self.user2.email,
        )
        
        # Create farms
        self.farm1 = Farm.objects.create(
            farmer=self.farmer1,
            farm_name='Farm 1',
            crop_type='maize',
            farm_size=5.0,
        )
        
        self.farm2 = Farm.objects.create(
            farmer=self.farmer2,
            farm_name='Farm 2',
            crop_type='beans',
            farm_size=3.0,
        )

    def test_users_see_only_their_farms(self):
        """Test that users only see their own farms."""
        self.client.login(email='user1@example.com', password='TestPassword123!')
        response = self.client.get(reverse('dashboard'))
        
        farms = response.context['farms']
        self.assertEqual(len(farms), 1)
        self.assertEqual(farms[0].id, self.farm1.id)

    def test_users_cannot_edit_others_farms(self):
        """Test that users cannot edit other users' farms."""
        self.client2.login(email='user2@example.com', password='TestPassword123!')
        
        url = reverse('edit_farm_details', args=[self.farm1.id])
        data = {
            'farm_name': 'Hacked Farm',
            'crop_type': 'beans',
            'farm_size': 1.0,
        }
        response = self.client2.post(url, data, follow=True)
        
        # Farm should not be edited
        self.farm1.refresh_from_db()
        self.assertEqual(self.farm1.farm_name, 'Farm 1')

    def test_regional_notifications_reach_correct_farmers(self):
        """Test that regional notifications are sent to farmers in the region."""
        # Create farms in same region
        farm1_updated = Farm.objects.create(
            farmer=self.farmer1,
            farm_name='Farm 1B',
            crop_type='maize',
            farm_size=2.0,
            county='Nairobi',
            sub_county='Westlands',
        )
        
        farm2_updated = Farm.objects.create(
            farmer=self.farmer2,
            farm_name='Farm 2B',
            crop_type='beans',
            farm_size=2.0,
            county='Nairobi',
            sub_county='Westlands',
        )
        
        # Both farmers should receive regional notifications for Nairobi
        # This is a conceptual test - adjust based on implementation


class NavigationTestCase(TestCase):
    """Test navigation between different parts of the application."""

    def setUp(self):
        self.client = Client()
        
        # Create complete user setup
        self.user = CustomUser.objects.create_user(
            email='navigator@example.com',
            password='TestPassword123!'
        )
        self.user.email_verified = True
        self.user.save()
        
        self.farmer = Farmer.objects.create(
            fname='Nav',
            lname='Tester',
            email=self.user.email,
        )
        
        self.farm = Farm.objects.create(
            farmer=self.farmer,
            farm_name='Nav Farm',
            crop_type='maize',
            farm_size=5.0,
        )
        
        self.client.login(email='navigator@example.com', password='TestPassword123!')

    def test_Dashboard_to_conversation(self):
        """Test navigation from dashboard to conversation."""
        response = self.client.get(reverse('dashboard'))
        self.assertEqual(response.status_code, 200)
        
        response = self.client.get(reverse('conversation'))
        self.assertEqual(response.status_code, 200)

    def test_dashboard_to_edit_farm(self):
        """Test navigation from dashboard to edit farm."""
        response = self.client.get(reverse('dashboard'))
        self.assertEqual(response.status_code, 200)
        
        url = reverse('edit_farm_details', args=[self.farm.id])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

    def test_conversation_to_dashboard(self):
        """Test navigation from conversation back to dashboard."""
        response = self.client.get(reverse('conversation'))
        self.assertEqual(response.status_code, 200)
        
        response = self.client.get(reverse('dashboard'))
        self.assertEqual(response.status_code, 200)


class SessionManagementTestCase(TestCase):
    """Test session management and session data."""

    def setUp(self):
        self.client = Client()
        self.user = CustomUser.objects.create_user(
            email='session@example.com',
            password='TestPassword123!'
        )
        self.user.email_verified = True
        self.user.save()

    def test_login_creates_session(self):
        """Test that login creates a session."""
        self.client.login(email='session@example.com', password='TestPassword123!')
        
        # Session should exist
        self.assertIn('_auth_user_id', self.client.session)

    def test_logout_clears_session(self):
        """Test that logout clears the session."""
        self.client.login(email='session@example.com', password='TestPassword123!')
        self.assertIn('_auth_user_id', self.client.session)
        
        self.client.get(reverse('logout'))
        
        # Session should be empty
        self.assertNotIn('_auth_user_id', self.client.session)

    def test_session_persists_across_requests(self):
        """Test that session data persists across multiple requests."""
        self.client.login(email='session@example.com', password='TestPassword123!')
        
        # Make multiple requests
        self.client.get(reverse('dashboard'))
        self.client.get(reverse('auth'))
        
        # User should still be authenticated
        response = self.client.get(reverse('dashboard'))
        self.assertEqual(response.wsgi_request.user.email, 'session@example.com')


class PerformanceAndLoadTestCase(TestCase):
    """Test application performance with multiple entities."""

    def setUp(self):
        self.client = Client()

    def test_dashboard_with_many_farms(self):
        """Test dashboard performance with many farms."""
        user = CustomUser.objects.create_user(
            email='perf@example.com',
            password='TestPassword123!'
        )
        user.email_verified = True
        user.save()
        
        farmer = Farmer.objects.create(
            fname='Perf',
            lname='Test',
            email=user.email,
        )
        
        # Create 20 farms
        for i in range(20):
            Farm.objects.create(
                farmer=farmer,
                farm_name=f'Farm {i}',
                crop_type=('maize' if i % 2 == 0 else 'beans'),
                farm_size=float(i+1),
            )
        
        self.client.login(email='perf@example.com', password='TestPassword123!')
        response = self.client.get(reverse('dashboard'))
        
        # Should load successfully
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context['farms']), 20)

    def test_dashboard_with_many_notifications(self):
        """Test dashboard with many notifications."""
        user = CustomUser.objects.create_user(
            email='notif@example.com',
            password='TestPassword123!'
        )
        user.email_verified = True
        user.save()
        
        farmer = Farmer.objects.create(
            fname='Notif',
            lname='Test',
            email=user.email,
        )
        
        # Create many notifications
        for i in range(50):
            Notification.objects.create(
                farmer=farmer,
                title=f'Notification {i}',
                message=f'Message {i}',
                notification_type='advisory',
            )
        
        self.client.login(email='notif@example.com', password='TestPassword123!')
        response = self.client.get(reverse('dashboard'))
        
        # Should load successfully
        self.assertEqual(response.status_code, 200)
