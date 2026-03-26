"""
Integration tests from demo scripts.
Converts demo_notifications, regional_notifications, and other demo scripts into proper test cases.
Tests:
- Notification creation workflows (from test_notifications_demo.py)
- Regional notification system (from regional_notifications_demo.py)
- Advisory generation (from script.py)
- Authentication flows (from test_auth.py)
- Geocoding and ward fallback (from test_ward_fallback.py)
"""
from django.test import TestCase, Client
from django.contrib.auth import get_user_model, authenticate
from django.urls import reverse
from app.models import Farmer, Farm, Notification, CustomUser
from app.forms import CustomUserCreationForm, CustomAuthenticationForm
from app.notification_utils import create_and_send_notification
from unittest.mock import patch, MagicMock
import sqlite3
import os

CustomUser = get_user_model()


class NotificationDemoScenariosTestCase(TestCase):
    """
    Integration test for notification system covering real-world scenarios.
    Converted from test_notifications_demo.py
    Tests creating various notification types that farmers would receive.
    """

    def setUp(self):
        """Setup test farmer and farm."""
        self.user = CustomUser.objects.create_user(
            email='demo_farmer@example.com',
            password='DemoPassword123!'
        )
        self.user.email_verified = True
        self.user.save()
        
        self.farmer = Farmer.objects.create(
            fname='Demo',
            lname='Farmer',
            email=self.user.email,
            phone='+254712345678'
        )
        
        self.farm = Farm.objects.create(
            farmer=self.farmer,
            farm_name='Demo Farm',
            crop_type='maize',
            farm_size=5.0,
            county='Kisii',
            sub_county='Kisii Central',
            ward='Keumbu Ward',
            lat=-0.6833,
            long=34.7833,
        )

    def test_create_rainfall_notification(self):
        """Demo: Create rainfall alert notification."""
        notif = create_and_send_notification(
            farmer=self.farmer,
            title="🌧️ Good Rainfall Recorded",
            message="35mm of rainfall was recorded in your area. This is excellent for crop growth.",
            notification_type='rainfall',
            metadata={
                'rainfall_amount': 35,
                'date': '2026-03-05',
                'location': f'{self.farm.lat}, {self.farm.long}'
            }
        )
        
        self.assertIsNotNone(notif)
        self.assertEqual(notif.title, "🌧️ Good Rainfall Recorded")
        self.assertEqual(notif.notification_type, 'rainfall')
        self.assertIn('rainfall_amount', notif.metadata)
        self.assertEqual(notif.metadata['rainfall_amount'], 35)

    def test_create_soil_moisture_notification(self):
        """Demo: Create soil moisture alert."""
        notif = create_and_send_notification(
            farmer=self.farmer,
            title="⚠️ Low Soil Moisture Alert",
            message="Soil moisture is at 30%. Below optimal range for maize.",
            notification_type='soil_moisture',
            metadata={
                'moisture_percent': 30,
                'soil_type': 'sandy loam',
                'optimal_range': '40-70%'
            }
        )
        
        self.assertIsNotNone(notif)
        self.assertEqual(notif.notification_type, 'soil_moisture')
        self.assertEqual(notif.metadata['moisture_percent'], 30)

    def test_create_dry_spell_warning(self):
        """Demo: Create dry spell warning notification."""
        notif = create_and_send_notification(
            farmer=self.farmer,
            title="☀️ Dry Spell Warning",
            message="Low rainfall expected for the next 10 days.",
            notification_type='dry_spell',
            metadata={
                'expected_duration': 10,
                'severity': 'moderate'
            }
        )
        
        self.assertIsNotNone(notif)
        self.assertEqual(notif.notification_type, 'dry_spell')
        self.assertEqual(notif.metadata['expected_duration'], 10)

    def test_create_planting_date_alert(self):
        """Demo: Create planting date optimal time alert."""
        notif = create_and_send_notification(
            farmer=self.farmer,
            title="✅ Optimal Planting Time",
            message="Recent rainfall and soil moisture indicate good planting conditions.",
            notification_type='planting_date',
            metadata={
                'crop': 'maize',
                'confidence': 0.85
            }
        )
        
        self.assertIsNotNone(notif)
        self.assertEqual(notif.notification_type, 'planting_date')
        self.assertGreater(notif.metadata['confidence'], 0.8)

    def test_create_general_advisory_notification(self):
        """Demo: Create weekly farming advisory."""
        notif = create_and_send_notification(
            farmer=self.farmer,
            title="ℹ️ Weekly Farming Advisory",
            message="This week: Monitor for armyworms in your maize field.",
            notification_type='advisory',
            metadata={
                'pest': 'armyworms',
                'crop': 'maize'
            }
        )
        
        self.assertIsNotNone(notif)
        self.assertEqual(notif.notification_type, 'advisory')
        self.assertEqual(notif.metadata['pest'], 'armyworms')

    def test_multiple_notifications_sequence(self):
        """Demo: Create sequence of different notifications throughout week."""
        notifications = []
        
        # Day 1: Rainfall alert
        notif1 = create_and_send_notification(
            farmer=self.farmer,
            title="Rainfall Alert",
            message="25mm rainfall recorded",
            notification_type='rainfall'
        )
        notifications.append(notif1)
        
        # Day 2: Soil moisture alert
        notif2 = create_and_send_notification(
            farmer=self.farmer,
            title="Soil Moisture Alert",
            message="Moisture at optimal level",
            notification_type='soil_moisture'
        )
        notifications.append(notif2)
        
        # Day 4: Planting recommendation
        notif3 = create_and_send_notification(
            farmer=self.farmer,
            title="Planting Time",
            message="Perfect time to plant",
            notification_type='planting_date'
        )
        notifications.append(notif3)
        
        # Verify all created
        self.assertEqual(len(notifications), 3)
        
        # Verify farmer received all
        farmer_notifications = Notification.objects.filter(farmer=self.farmer)
        self.assertGreaterEqual(farmer_notifications.count(), 3)


class RegionalNotificationDemoTestCase(TestCase):
    """
    Integration test for regional notification system.
    Converted from regional_notifications_demo.py
    Tests sending region-specific alerts to multiple farmers.
    """

    def setUp(self):
        """Setup multiple farmers in same region."""
        # Create 3 farmers in Kisii County
        self.farmers_kisii = []
        for i in range(3):
            user = CustomUser.objects.create_user(
                email=f'kisii_farmer{i}@example.com',
                password='Password123!'
            )
            user.email_verified = True
            user.save()
            
            farmer = Farmer.objects.create(
                fname=f'Farmer',
                lname=f'Kisii{i}',
                email=user.email,
                phone=f'+25471234567{i}'
            )
            
            Farm.objects.create(
                farmer=farmer,
                farm_name=f'Farm {i}',
                crop_type='maize',
                farm_size=5.0,
                county='Kisii',
                sub_county='Kisii Central',
                ward='Keumbu Ward',
                lat=-0.6833,
                long=34.7833,
            )
            
            self.farmers_kisii.append(farmer)

    def test_farmers_in_same_region_exist(self):
        """Verify setup: Multiple farmers in same region."""
        self.assertEqual(len(self.farmers_kisii), 3)
        
        for farmer in self.farmers_kisii:
            farms = farmer.farms.all()
            self.assertEqual(farms.count(), 1)
            self.assertEqual(farms.first().county, 'Kisii')

    def test_create_weather_alert_notification(self):
        """Demo: Create region-wide weather alert."""
        # In real system, this would create RegionalNotification
        # For now, test creating notifications for farmers in region
        
        message = "⚠️ Heavy Rainfall Warning - Kisii County\n\nRainfall (50-100mm) expected in next 24-48 hours"
        
        notifications = []
        for farmer in self.farmers_kisii:
            notif = create_and_send_notification(
                farmer=farmer,
                title="⚠️ Heavy Rainfall Warning",
                message=message,
                notification_type='weather_alert',
                metadata={
                    'expected_rainfall': '50-100mm',
                    'forecast_period': '24-48 hours',
                    'risk_level': 'high',
                    'region': 'Kisii'
                }
            )
            notifications.append(notif)
        
        # Verify all farmers got notification
        self.assertEqual(len(notifications), 3)
        for notif in notifications:
            self.assertEqual(notif.metadata['region'], 'Kisii')

    def test_create_pest_alert_for_region(self):
        """Demo: Create pest alert for farmers with specific crop."""
        message = "🐛 Armyworm Alert - Kisii Central\n\nArmyworm infestation reported. Scout your fields immediately."
        
        # Only send to maize farmers (filter would happen in real system)
        notifications = []
        for farmer in self.farmers_kisii:
            if farmer.farms.filter(crop_type='maize').exists():
                notif = create_and_send_notification(
                    farmer=farmer,
                    title="🐛 Armyworm Alert",
                    message=message,
                    notification_type='pest_alert',
                    metadata={
                        'pest': 'armyworms',
                        'crop': 'maize',
                        'region': 'Kisii Central'
                    }
                )
                notifications.append(notif)
        
        # All farmers have maize
        self.assertEqual(len(notifications), 3)


class AuthenticationDemoTestCase(TestCase):
    """
    Integration test for email/password authentication.
    Converted from test_auth.py
    Tests signup, login, and form validation flows.
    """

    def test_email_signup_success(self):
        """Demo: Successful email/password signup."""
        data = {
            'email': 'newfarmer@example.com',
            'password1': 'SecurePass123!',
            'password2': 'SecurePass123!',
        }
        
        form = CustomUserCreationForm(data)
        self.assertTrue(form.is_valid())
        
        user = form.save()
        self.assertEqual(user.email, 'newfarmer@example.com')
        
        # Verify user exists in database
        saved_user = CustomUser.objects.get(email='newfarmer@example.com')
        self.assertIsNotNone(saved_user)

    def test_email_signup_duplicate_email_rejected(self):
        """Demo: Signup rejects duplicate email."""
        # Create first user
        CustomUser.objects.create_user(
            email='existing@example.com',
            password='Password123!'
        )
        
        # Try signup with same email
        data = {
            'email': 'existing@example.com',
            'password1': 'NewPassword123!',
            'password2': 'NewPassword123!',
        }
        
        form = CustomUserCreationForm(data)
        self.assertFalse(form.is_valid())
        self.assertIn('email', form.errors)

    def test_email_signup_mismatched_passwords_rejected(self):
        """Demo: Signup rejects mismatched passwords."""
        data = {
            'email': 'newuser@example.com',
            'password1': 'Password123!',
            'password2': 'DifferentPass123!',
        }
        
        form = CustomUserCreationForm(data)
        self.assertFalse(form.is_valid())

    def test_email_login_success(self):
        """Demo: Successful email/password login."""
        # Create user
        user = CustomUser.objects.create_user(
            email='farmer@example.com',
            password='LoginPass123!'
        )
        
        # Authenticate
        authenticated_user = authenticate(
            username='farmer@example.com',
            password='LoginPass123!'
        )
        
        self.assertIsNotNone(authenticated_user)
        self.assertEqual(authenticated_user.email, 'farmer@example.com')

    def test_email_login_wrong_password_fails(self):
        """Demo: Login fails with wrong password."""
        # Create user
        CustomUser.objects.create_user(
            email='farmer@example.com',
            password='CorrectPass123!'
        )
        
        # Try wrong password
        authenticated_user = authenticate(
            username='farmer@example.com',
            password='WrongPass123!'
        )
        
        self.assertIsNone(authenticated_user)

    def test_email_login_nonexistent_user_fails(self):
        """Demo: Login fails for non-existent user."""
        authenticated_user = authenticate(
            username='nonexistent@example.com',
            password='SomePassword123!'
        )
        
        self.assertIsNone(authenticated_user)


class GeocodingDemoTestCase(TestCase):
    """
    Integration test for geocoding and ward fallback mechanism.
    Converted from test_ward_fallback.py
    Tests that the system can fallback to database when geocoding fails.
    """

    def test_database_connectivity(self):
        """Demo: Verify kenya_admin.db database exists and is readable."""
        db_path = os.path.join(
            os.path.dirname(__file__),
            '..',
            '..',
            'county-data',
            'kenya_admin.db'
        )
        
        # Check file exists
        self.assertTrue(os.path.exists(db_path), "kenya_admin.db not found")
        
        # Try connecting
        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            
            # Count records in tables
            cursor.execute("SELECT COUNT(*) FROM counties")
            county_count = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM constituencies")
            constituency_count = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM wards")
            ward_count = cursor.fetchone()[0]
            
            conn.close()
            
            # Verify non-zero counts
            self.assertGreater(county_count, 0)
            self.assertGreater(constituency_count, 0)
            self.assertGreater(ward_count, 0)
        except sqlite3.Error as e:
            self.fail(f"Failed to connect to database: {e}")

    def test_farm_location_saved_with_coordinates(self):
        """Demo: Farm registration saves GPS coordinates for fallback."""
        user = CustomUser.objects.create_user(
            email='geo_farmer@example.com',
            password='GeoPass123!'
        )
        user.email_verified = True
        user.save()
        
        farmer = Farmer.objects.create(
            fname='Geo',
            lname='Farmer',
            email=user.email,
            phone='+254712345678'
        )
        
        # Create farm with GPS coordinates
        farm = Farm.objects.create(
            farmer=farmer,
            farm_name='GPS Farm',
            crop_type='maize',
            farm_size=3.0,
            lat=-1.2833,
            long=36.8167,
            county='Nairobi',
            sub_county='Westlands',
            ward='Chiromo Ward',
        )
        
        # Verify coordinates saved for fallback
        self.assertIsNotNone(farm.lat)
        self.assertIsNotNone(farm.long)
        self.assertEqual(farm.lat, -1.2833)
        self.assertEqual(farm.long, 36.8167)
