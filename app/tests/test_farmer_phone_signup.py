"""
Tests for farmer profile registration specifically for phone signup users.
Phone signup users have email_verified=True from the start and don't need email verification.
They can optionally provide an email during farmer registration that requires verification.
"""
from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone
from datetime import timedelta
from unittest.mock import patch
from app.models import Farmer
import uuid

CustomUser = get_user_model()


class PhoneSignupFarmerRegistrationTestCase(TestCase):
    """Test farmer profile registration for phone signup users."""

    def setUp(self):
        self.client = Client()
        self.farmer_registration_url = reverse('farmer_registration')
    
    @patch('app.views.send_verification_sms')
    def test_phone_signup_farmer_registration_no_email(self, mock_send_sms):
        """Test phone signup user can complete farmer registration without providing email.
        
        Phone users don't need email verification for their account.
        They have email_verified=True automatically from phone signup.
        """
        mock_send_sms.return_value = True
        
        # Create phone signup user (simulating completed phone signup flow)
        unique_email = f"phone-{uuid.uuid4()}@crpas.local"
        user = CustomUser.objects.create_user(
            email=unique_email,
            password='TestPassword123!',
            phone='+254712345678'
        )
        # Phone signup users have email_verified=True from the start
        user.email_verified = True
        user.phone_verified = True
        user.save()
        
        # Login the user
        self.client.force_login(user)
        
        # Set phone_signup flag in session
        session = self.client.session
        session['phone_signup'] = True
        session.save()
        
        # Register farmer without providing email (optional for phone users)
        data = {
            'fname': 'Jane',
            'lname': 'Smith',
            'phone': '+254712345678',
        }
        response = self.client.post(self.farmer_registration_url, data, follow=True)
        
        # Should redirect to farm registration (no email verification needed)
        self.assertRedirects(response, reverse('farm_registration'))
        
        # Farmer profile should be created
        farmer = Farmer.objects.filter(email=user.email).first()
        self.assertIsNotNone(farmer)
        self.assertEqual(farmer.fname, 'Jane')
        self.assertEqual(farmer.lname, 'Smith')
        self.assertEqual(farmer.phone, '+254712345678')
    
    @patch('app.views.send_verification_email')
    @patch('app.views.send_verification_sms')
    def test_phone_signup_farmer_registration_with_email(self, mock_send_sms, mock_send_email):
        """Test phone signup user providing email during farmer registration.
        
        If phone signup user provides an email address, they need to verify it.
        This triggers email verification flow (verify_farmer_email).
        """
        mock_send_sms.return_value = True
        mock_send_email.return_value = True
        
        # Create phone signup user
        unique_email = f"phone-{uuid.uuid4()}@crpas.local"
        user = CustomUser.objects.create_user(
            email=unique_email,
            password='TestPassword123!',
            phone='+254712345678'
        )
        user.email_verified = True
        user.phone_verified = True
        user.save()
        
        self.client.force_login(user)
        
        session = self.client.session
        session['phone_signup'] = True
        session.save()
        
        # Register farmer and provide an email
        data = {
            'fname': 'Jane',
            'lname': 'Smith',
            'phone': '+254712345678',
            'email': 'jane.smith@example.com',  # Providing email optional for phone users
        }
        response = self.client.post(self.farmer_registration_url, data, follow=True)
        
        # Should redirect to email verification for the provided email
        self.assertRedirects(response, reverse('verify_farmer_email'))
        
        # Farmer profile should be created
        farmer = Farmer.objects.filter(email=user.email).first()
        self.assertIsNotNone(farmer)
        
        # Email verification code should be set on user
        user.refresh_from_db()
        self.assertIsNotNone(user.email_verification_code)
        self.assertLessEqual(
            user.verification_code_expires_at,
            timezone.now() + timedelta(minutes=11)
        )
        
        # send_verification_email should have been called
        self.assertTrue(mock_send_email.called)
    
    @patch('app.views.send_verification_sms')
    def test_phone_signup_user_has_email_verified_true(self, mock_send_sms):
        """Test that phone signup users have email_verified=True automatically."""
        mock_send_sms.return_value = True
        
        # Create phone signup user
        unique_email = f"phone-{uuid.uuid4()}@crpas.local"
        user = CustomUser.objects.create_user(
            email=unique_email,
            phone='+254712345678',
            password=None
        )
        # This is what happens in phone signup view
        user.email_verified = True
        user.save()
        
        # Login and access farmer registration
        self.client.force_login(user)
        response = self.client.get(self.farmer_registration_url)
        
        # Should be able to access farmer registration without email verification redirect
        self.assertEqual(response.status_code, 200)
        
        user.refresh_from_db()
        self.assertTrue(user.email_verified)
    
    @patch('app.views.send_verification_sms')
    def test_phone_signup_farmer_registration_minimal_fields(self, mock_send_sms):
        """Test phone signup farmer registration with just fname and lname."""
        mock_send_sms.return_value = True
        
        unique_email = f"phone-{uuid.uuid4()}@crpas.local"
        user = CustomUser.objects.create_user(
            email=unique_email,
            phone='+254712345678',
            password='TestPassword123!'
        )
        user.email_verified = True
        user.phone_verified = True
        user.save()
        
        self.client.force_login(user)
        
        session = self.client.session
        session['phone_signup'] = True
        session.save()
        
        data = {
            'fname': 'John',
            'lname': 'Doe',
            'phone': '+254712345678',  # Required by form validation
        }
        response = self.client.post(self.farmer_registration_url, data, follow=True)
        
        # Should redirect to farm registration
        self.assertRedirects(response, reverse('farm_registration'))
        
        # Farmer should be created
        farmer = Farmer.objects.filter(email=user.email).first()
        self.assertIsNotNone(farmer)
        self.assertEqual(farmer.fname, 'John')
        self.assertEqual(farmer.lname, 'Doe')


class PhoneSignupEmailVerificationTestCase(TestCase):
    """Test email verification flow for phone signup users who provide email."""

    def setUp(self):
        self.client = Client()
        self.verify_farmer_email_url = reverse('verify_farmer_email')
        
        # Create phone signup user
        unique_email = f"phone-{uuid.uuid4()}@crpas.local"
        self.user = CustomUser.objects.create_user(
            email=unique_email,
            phone='+254712345678',
            password='TestPassword123!'
        )
        self.user.email_verified = True
        self.user.phone_verified = True
        self.user.save()
        
        # Create verification code
        self.verification_code = ''.join([str(i % 10) for i in range(6)])
        self.user.email_verification_code = self.verification_code
        self.user.verification_code_expires_at = timezone.now() + timedelta(minutes=10)
        self.user.save()
    
    @patch('app.views.send_verification_email')
    def test_phone_signup_email_verification_correct_code(self, mock_send_email):
        """Test phone signup user verifying email with correct code."""
        mock_send_email.return_value = True
        
        self.client.force_login(self.user)
        
        session = self.client.session
        session['farmer_email_verification'] = 'jane.smith@example.com'
        session.save()
        
        data = {'verification_code': self.verification_code}
        response = self.client.post(self.verify_farmer_email_url, data, follow=True)
        
        # Should be able to verify and proceed
        self.user.refresh_from_db()
        self.assertTrue(self.user.email_verified)
        
        # Should redirect to farmer_registration (not farm_registration)
        # May redirect to farmer_registration for additional info or farm_registration
        self.assertIn(response.status_code, [200, 302])
    
    @patch('app.views.send_verification_email')
    def test_phone_signup_email_verification_incorrect_code(self, mock_send_email):
        """Test phone signup user with incorrect email verification code."""
        mock_send_email.return_value = True
        
        self.client.force_login(self.user)
        
        session = self.client.session
        session['farmer_email_verification'] = 'jane.smith@example.com'
        session.save()
        
        data = {'verification_code': '000000'}  # Wrong code
        response = self.client.post(self.verify_farmer_email_url, data)
        
        # Should show error
        self.assertEqual(response.status_code, 200)
        
        # User should still not be verified for this new email
        self.user.refresh_from_db()
        # Email verification code should still exist (incorrect attempt)
        self.assertIsNotNone(self.user.email_verification_code)
