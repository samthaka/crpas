"""
Comprehensive tests for authentication flows in CRPAS.
Tests email/password signup, phone authentication, email verification, phone verification, and login.
"""
from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone
from datetime import timedelta
from unittest.mock import patch, MagicMock
import random

CustomUser = get_user_model()


class EmailSignupTestCase(TestCase):
    """Test email and password based signup flow."""

    def setUp(self):
        self.client = Client()
        self.auth_url = reverse('auth')

    def test_signup_page_loads(self):
        """Test that the auth page loads and contains signup form."""
        response = self.client.get(self.auth_url)
        self.assertEqual(response.status_code, 200)
        self.assertIn('signup_form', response.context)
        self.assertIn('login_form', response.context)

    def test_email_signup_success(self):
        """Test successful user signup with email and password."""
        data = {
            'action': 'signup',
            'email': 'testfarmier@example.com',
            'password1': 'SecurePassword123!',
            'password2': 'SecurePassword123!',
        }
        response = self.client.post(self.auth_url, data, follow=True)
        
        # Should redirect to email verification
        self.assertRedirects(response, reverse('verify_email'))
        
        # User should be created but not verified
        user = CustomUser.objects.get(email='testfarmier@example.com')
        self.assertFalse(user.email_verified)
        self.assertIsNotNone(user.email_verification_code)
        self.assertIsNotNone(user.verification_code_expires_at)

    def test_email_signup_duplicate_email(self):
        """Test signup with an email that already exists."""
        # Create a user first
        CustomUser.objects.create_user(email='existing@example.com', password='Password123!')
        
        # Try to signup with same email
        data = {
            'action': 'signup',
            'email': 'existing@example.com',
            'password1': 'NewPassword123!',
            'password2': 'NewPassword123!',
        }
        response = self.client.post(self.auth_url, data)
        
        # Should not redirect and should show error
        self.assertEqual(response.status_code, 200)
        self.assertIn('signup_form', response.context)
        form_errors = response.context['signup_form'].errors
        self.assertTrue(any('already exists' in str(error) for error in form_errors.values()))

    def test_email_signup_password_mismatch(self):
        """Test signup with mismatched passwords."""
        data = {
            'action': 'signup',
            'email': 'mismatch@example.com',
            'password1': 'Password123!',
            'password2': 'DifferentPassword123!',
        }
        response = self.client.post(self.auth_url, data)
        
        # Should not create user
        self.assertFalse(CustomUser.objects.filter(email='mismatch@example.com').exists())

    def test_email_signup_weak_password(self):
        """Test signup with a weak/short password."""
        data = {
            'action': 'signup',
            'email': 'weak@example.com',
            'password1': 'weak',
            'password2': 'weak',
        }
        response = self.client.post(self.auth_url, data)
        
        # Should not create user
        self.assertFalse(CustomUser.objects.filter(email='weak@example.com').exists())

    def test_email_signup_empty_email(self):
        """Test signup with empty email."""
        data = {
            'action': 'signup',
            'email': '',
            'password1': 'Password123!',
            'password2': 'Password123!',
        }
        response = self.client.post(self.auth_url, data)
        
        # Should not create user
        self.assertEqual(CustomUser.objects.count(), 0)


class EmailVerificationTestCase(TestCase):
    """Test email verification flow."""

    def setUp(self):
        self.client = Client()
        self.verify_email_url = reverse('verify_email')
        
        # Create an unverified user
        self.user = CustomUser.objects.create_user(
            email='testuser@example.com',
            password='TestPassword123!'
        )
        self.verification_code = ''.join([str(random.randint(0, 9)) for _ in range(6)])
        self.user.email_verification_code = self.verification_code
        self.user.verification_code_expires_at = timezone.now() + timedelta(minutes=10)
        self.user.save()

    @patch('app.views.send_verification_email')
    def test_email_verification_page_loads(self, mock_send_email):
        """Test that email verification page loads."""
        mock_send_email.return_value = True
        
        # Set session data
        session = self.client.session
        session['signup_email'] = self.user.email
        session.save()
        
        response = self.client.get(self.verify_email_url)
        self.assertEqual(response.status_code, 200)
        self.assertIn('form', response.context)

    @patch('app.views.send_verification_email')
    def test_email_verification_correct_code(self, mock_send_email):
        """Test email verification with correct code."""
        mock_send_email.return_value = True
        
        session = self.client.session
        session['signup_email'] = self.user.email
        session['signup_password'] = 'TestPassword123!'
        session.save()
        
        data = {'verification_code': self.verification_code}
        response = self.client.post(self.verify_email_url, data, follow=True)
        
        # User should be verified
        self.user.refresh_from_db()
        self.assertTrue(self.user.email_verified)
        self.assertIsNone(self.user.email_verification_code)
        
        # Should redirect to farmer registration
        self.assertRedirects(response, reverse('farmer_registration'))

    @patch('app.views.send_verification_email')
    def test_email_verification_incorrect_code(self, mock_send_email):
        """Test email verification with incorrect code."""
        mock_send_email.return_value = True
        
        session = self.client.session
        session['signup_email'] = self.user.email
        session.save()
        
        data = {'verification_code': '000000'}  # Wrong code
        response = self.client.post(self.verify_email_url, data)
        
        # User should still be unverified
        self.user.refresh_from_db()
        self.assertFalse(self.user.email_verified)

    def test_email_verification_expired_code(self):
        """Test email verification with expired code."""
        # Set code to expired
        self.user.verification_code_expires_at = timezone.now() - timedelta(minutes=1)
        self.user.save()
        
        session = self.client.session
        session['signup_email'] = self.user.email
        session.save()
        
        response = self.client.get(self.verify_email_url, follow=True)
        
        # Should show error and redirect to auth
        self.assertRedirects(response, reverse('auth'))

    @patch('app.views.send_verification_email')
    def test_resend_verification_email(self, mock_send_email):
        """Test resending verification email."""
        mock_send_email.return_value = True
        
        session = self.client.session
        session['signup_email'] = self.user.email
        session.save()
        
        response = self.client.post(reverse('resend_verification'), follow=True)
        
        # Should redirect back to verify_email
        self.assertRedirects(response, reverse('verify_email'))
        
        # Should have called send_verification_email
        self.assertTrue(mock_send_email.called)


class PhoneSignupTestCase(TestCase):
    """Test phone-based signup flow."""

    def setUp(self):
        self.client = Client()
        self.phone_auth_url = reverse('phone_auth')

    @patch('app.views.send_verification_sms')
    def test_phone_signup_page_loads(self, mock_send_sms):
        """Test that phone auth page loads."""
        response = self.client.get(self.phone_auth_url)
        self.assertEqual(response.status_code, 200)
        self.assertIn('form', response.context)

    @patch('app.views.send_verification_sms')
    def test_phone_signup_success(self, mock_send_sms):
        """Test successful phone signup."""
        mock_send_sms.return_value = True
        
        data = {
            'phone': '+254712345678',
            'action': 'signup'
        }
        response = self.client.post(self.phone_auth_url, data, follow=True)
        
        # Should redirect to phone verification
        self.assertRedirects(response, reverse('verify_phone'))
        
        # User should be created but phone not verified
        # However, email should be auto-verified since phone users don't need email
        user = CustomUser.objects.get(phone='+254712345678')
        self.assertFalse(user.phone_verified)
        self.assertTrue(user.email_verified)  # Auto-verified for phone users
        self.assertIsNotNone(user.phone_verification_code)

    @patch('app.views.send_verification_sms')
    def test_phone_signup_duplicate_phone(self, mock_send_sms):
        """Test signup with phone that already exists."""
        mock_send_sms.return_value = True
        
        # Create user with phone
        CustomUser.objects.create_user(
            email='user1@example.com',
            password='TestPassword123!',
            phone='+254712345678'
        )
        
        # Try to signup with same phone
        data = {
            'phone': '+254712345678',
            'action': 'signup'
        }
        response = self.client.post(self.phone_auth_url, data)
        
        # Should redirect to verify_phone (as normal flow) since user already exists
        # The duplicate message will be shown on the verify page
        self.assertEqual(response.status_code, 302)

    @patch('app.views.send_verification_sms')
    def test_phone_signup_invalid_format(self, mock_send_sms):
        """Test signup with invalid phone format."""
        mock_send_sms.return_value = True
        
        data = {
            'phone': 'invalid_phone',
            'action': 'signup'
        }
        response = self.client.post(self.phone_auth_url, data)
        
        # Should not create user
        self.assertFalse(CustomUser.objects.filter(phone='invalid_phone').exists())


class PhoneVerificationTestCase(TestCase):
    """Test phone verification flow."""

    def setUp(self):
        self.client = Client()
        self.verify_phone_url = reverse('verify_phone')
        
        # Create unverified user with phone
        self.user = CustomUser.objects.create_user(
            email='phoneuser@example.com',
            password='TestPassword123!',
            phone='+254712345678'
        )
        self.verification_code = ''.join([str(random.randint(0, 9)) for _ in range(6)])
        self.user.phone_verification_code = self.verification_code
        self.user.phone_verification_code_expires_at = timezone.now() + timedelta(minutes=10)
        self.user.save()

    @patch('app.views.send_verification_sms')
    def test_phone_verification_page_loads(self, mock_send_sms):
        """Test phone verification page loads."""
        mock_send_sms.return_value = True
        
        session = self.client.session
        session['auth_phone'] = self.user.phone
        session.save()
        
        response = self.client.get(self.verify_phone_url)
        self.assertEqual(response.status_code, 200)

    @patch('app.views.send_verification_sms')
    def test_phone_verification_correct_code_signup(self, mock_send_sms):
        """Test phone verification with correct code during signup."""
        mock_send_sms.return_value = True
        
        # Mark email as verified since phone users don't use email verification
        self.user.email_verified = True
        self.user.save()
        
        session = self.client.session
        session['auth_phone'] = self.user.phone
        session['is_phone_signup'] = True
        session.save()
        
        data = {'verification_code': self.verification_code}
        response = self.client.post(self.verify_phone_url, data, follow=True)
        
        # Phone should be verified
        self.user.refresh_from_db()
        self.assertTrue(self.user.phone_verified)
        
        # Should redirect to phone signup password setup, not farmer registration
        self.assertRedirects(response, reverse('phone_signup_password'))

    @patch('app.views.send_verification_sms')
    def test_phone_verification_correct_code_login(self, mock_send_sms):
        """Test phone verification with correct code during login."""
        mock_send_sms.return_value = True
        
        # Mark email as verified since phone users don't use email verification
        self.user.email_verified = True
        self.user.save()
        
        session = self.client.session
        session['auth_phone'] = self.user.phone
        session['is_phone_signup'] = False
        session.save()
        
        data = {'verification_code': self.verification_code}
        response = self.client.post(self.verify_phone_url, data, follow=True)
        
        # Should redirect to dashboard (login flow, not signup)
        self.assertRedirects(response, reverse('dashboard'))

    @patch('app.views.send_verification_sms')
    def test_phone_verification_incorrect_code(self, mock_send_sms):
        """Test phone verification with incorrect code."""
        mock_send_sms.return_value = True
        
        # Mark email as verified since phone users don't use email verification
        self.user.email_verified = True
        self.user.save()
        
        session = self.client.session
        session['auth_phone'] = self.user.phone
        session.save()
        
        data = {'verification_code': '000000'}
        response = self.client.post(self.verify_phone_url, data)
        
        # Phone should still not be verified
        self.user.refresh_from_db()
        self.assertFalse(self.user.phone_verified)

    @patch('app.views.send_verification_sms')
    def test_resend_verification_sms(self, mock_send_sms):
        """Test resending verification SMS."""
        mock_send_sms.return_value = True
        
        session = self.client.session
        session['auth_phone'] = self.user.phone
        session.save()
        
        response = self.client.post(reverse('resend_sms'), follow=True)
        
        # Should redirect back to verify_phone
        self.assertRedirects(response, reverse('verify_phone'))


class PhoneSignupPasswordTestCase(TestCase):
    """Test setting password for phone signup users."""

    def setUp(self):
        self.client = Client()
        self.phone_password_url = reverse('phone_signup_password')
        
        # Create verified phone user without password
        self.user = CustomUser.objects.create_user(
            email='phoneuser@example.com',
            password='TempPassword123!',
            phone='+254712345678'
        )
        self.user.phone_verified = True
        # Phone signup users have email_verified=True automatically
        self.user.email_verified = True
        self.user.save()

    def test_password_setup_page_loads(self):
        """Test password setup page loads for phone users."""
        session = self.client.session
        session['auth_phone'] = self.user.phone
        session.save()
        
        response = self.client.get(self.phone_password_url)
        self.assertEqual(response.status_code, 200)

    def test_password_setup_success(self):
        """Test successful password setup."""
        session = self.client.session
        session['auth_phone'] = self.user.phone
        session.save()
        
        data = {
            'password1': 'NewSecurePassword123!',
            'password2': 'NewSecurePassword123!',
        }
        response = self.client.post(self.phone_password_url, data, follow=True)
        
        # Should redirect to farmer registration
        self.assertRedirects(response, reverse('farmer_registration'))
        
        # Password should be updated
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password('NewSecurePassword123!'))

    def test_password_setup_mismatch(self):
        """Test password setup with mismatched passwords."""
        session = self.client.session
        session['auth_phone'] = self.user.phone
        session.save()
        
        data = {
            'password1': 'Password123!',
            'password2': 'DifferentPassword123!',
        }
        response = self.client.post(self.phone_password_url, data)
        
        # Should show error
        self.assertEqual(response.status_code, 200)


class EmailLoginTestCase(TestCase):
    """Test email/password login flow."""

    def setUp(self):
        self.client = Client()
        self.auth_url = reverse('auth')
        self.user = CustomUser.objects.create_user(
            email='loginuser@example.com',
            password='TestPassword123!'
        )
        self.user.email_verified = True
        self.user.save()

    def test_login_success(self):
        """Test successful login with email and password."""
        data = {
            'action': 'login',
            'username': 'loginuser@example.com',
            'password': 'TestPassword123!'
        }
        response = self.client.post(self.auth_url, data, follow=True)
        
        # Should redirect to dashboard
        self.assertRedirects(response, reverse('dashboard'))
        
        # User should be authenticated
        self.assertTrue(response.wsgi_request.user.is_authenticated)

    def test_login_wrong_password(self):
        """Test login with wrong password."""
        data = {
            'action': 'login',
            'username': 'loginuser@example.com',
            'password': 'WrongPassword123!'
        }
        response = self.client.post(self.auth_url, data)
        
        # Should not login
        self.assertFalse(response.wsgi_request.user.is_authenticated)

    def test_login_nonexistent_email(self):
        """Test login with non-existent email."""
        data = {
            'action': 'login',
            'username': 'nonexistent@example.com',
            'password': 'TestPassword123!'
        }
        response = self.client.post(self.auth_url, data)
        
        # Should not login
        self.assertFalse(response.wsgi_request.user.is_authenticated)

    def test_login_empty_credentials(self):
        """Test login with empty credentials."""
        data = {
            'action': 'login',
            'username': '',
            'password': ''
        }
        response = self.client.post(self.auth_url, data)
        
        # Should not login
        self.assertFalse(response.wsgi_request.user.is_authenticated)


class LogoutTestCase(TestCase):
    """Test logout functionality."""

    def setUp(self):
        self.client = Client()
        self.user = CustomUser.objects.create_user(
            email='logoutuser@example.com',
            password='TestPassword123!'
        )
        self.user.email_verified = True
        self.user.save()

    def test_logout_authenticated_user(self):
        """Test logout of authenticated user."""
        # Login first
        self.client.login(email='logoutuser@example.com', password='TestPassword123!')
        
        # Logout
        response = self.client.post(reverse('logout'), follow=True)
        
        # Should redirect to auth
        self.assertRedirects(response, reverse('auth'))
        
        # User should be logged out
        self.assertFalse(response.wsgi_request.user.is_authenticated)


class VerificationCodeExpiryTestCase(TestCase):
    """Test verification code expiry."""

    def setUp(self):
        self.client = Client()
        self.user = CustomUser.objects.create_user(
            email='expiryuser@example.com',
            password='TestPassword123!'
        )

    def test_email_code_expiry(self):
        """Test that expired email verification codes are invalid."""
        # Set code to expired
        self.user.email_verification_code = '123456'
        self.user.verification_code_expires_at = timezone.now() - timedelta(minutes=1)
        self.user.save()
        
        # Should not be valid
        self.assertFalse(self.user.is_verification_code_valid())

    def test_email_code_not_expired(self):
        """Test that non-expired email verification codes are valid."""
        # Set code to valid
        self.user.email_verification_code = '123456'
        self.user.verification_code_expires_at = timezone.now() + timedelta(minutes=10)
        self.user.save()
        
        # Should be valid
        self.assertTrue(self.user.is_verification_code_valid())

    def test_phone_code_expiry(self):
        """Test that expired phone verification codes are invalid."""
        self.user.phone = '+254712345678'
        self.user.phone_verification_code = '123456'
        self.user.phone_verification_code_expires_at = timezone.now() - timedelta(minutes=1)
        self.user.save()
        
        # Should not be valid
        self.assertFalse(self.user.is_phone_verification_code_valid())

    def test_phone_code_not_expired(self):
        """Test that non-expired phone verification codes are valid."""
        self.user.phone = '+254712345678'
        self.user.phone_verification_code = '123456'
        self.user.phone_verification_code_expires_at = timezone.now() + timedelta(minutes=10)
        self.user.save()
        
        # Should be valid
        self.assertTrue(self.user.is_phone_verification_code_valid())
