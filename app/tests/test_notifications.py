"""
Tests for notification system in CRPAS.
Tests notification creation, delivery, preferences, and various alert types.
"""
from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone
from datetime import timedelta
from app.models import Farmer, Farm, Notification, NotificationPreference, RegionalNotification
from unittest.mock import patch, MagicMock
import json

CustomUser = get_user_model()


class NotificationSetup(TestCase):
    """Common setup for notification tests."""

    def setUp(self):
        self.client = Client()
        
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
        )
        
        # Create notification preferences
        self.notification_prefs = NotificationPreference.objects.create(
            farmer=self.farmer,
            notify_via_website=True,
            notify_via_email=True,
            notify_via_sms=True,
        )
        
        # Login
        self.client.login(email='farmer@example.com', password='TestPassword123!')


class NotificationCreationTestCase(NotificationSetup):
    """Test creating notifications."""

    def test_create_basic_notification(self):
        """Test creating a basic notification."""
        notification = Notification.objects.create(
            farmer=self.farmer,
            title='Test Alert',
            message='This is a test notification.',
            notification_type='advisory',
            sent_via_website=True,
        )
        
        self.assertEqual(notification.farmer, self.farmer)
        self.assertEqual(notification.title, 'Test Alert')
        self.assertFalse(notification.status == 'read')

    def test_create_rainfall_notification(self):
        """Test creating a rainfall alert notification."""
        notification = Notification.objects.create(
            farmer=self.farmer,
            title='Heavy Rainfall Expected',
            message='Expect heavy rainfall in the next 24 hours.',
            notification_type='rainfall',
            metadata={'rainfall_mm': 45.5, 'time_window': '24h'},
        )
        
        self.assertEqual(notification.notification_type, 'rainfall')
        self.assertEqual(notification.metadata['rainfall_mm'], 45.5)

    def test_create_dry_spell_notification(self):
        """Test creating a dry spell warning."""
        notification = Notification.objects.create(
            farmer=self.farmer,
            title='Dry Spell Warning',
            message='A prolonged dry spell is expected.',
            notification_type='dry_spell',
            metadata={'days_without_rain': 14},
        )
        
        self.assertEqual(notification.notification_type, 'dry_spell')

    def test_create_pest_disease_notification(self):
        """Test creating a pest and disease alert."""
        notification = Notification.objects.create(
            farmer=self.farmer,
            title='Armyworm Detected',
            message='Armyworm infestation detected in your area.',
            notification_type='risk_alert',
            metadata={
                'pest_type': 'armyworm',
                'severity': 'high',
                'recommended_action': 'Use approved pesticides',
            },
        )
        
        self.assertEqual(notification.notification_type, 'risk_alert')
        self.assertIn('pest_type', notification.metadata)

    def test_create_planting_date_notification(self):
        """Test creating a planting date alert."""
        notification = Notification.objects.create(
            farmer=self.farmer,
            title='Optimal Planting Window',
            message='Soil conditions are optimal for planting.',
            notification_type='planting_date',
        )
        
        self.assertEqual(notification.notification_type, 'planting_date')

    def test_notification_status_defaults_to_unread(self):
        """Test that notifications default to unread status."""
        notification = Notification.objects.create(
            farmer=self.farmer,
            title='Alert',
            message='Test message',
        )
        
        self.assertEqual(notification.status, 'unread')

    def test_notification_has_timestamp(self):
        """Test that notifications have creation timestamp."""
        notification = Notification.objects.create(
            farmer=self.farmer,
            title='Alert',
            message='Test message',
        )
        
        self.assertIsNotNone(notification.created_at)


class NotificationChannelsTestCase(NotificationSetup):
    """Test notification delivery via different channels."""

    def test_notification_via_website(self):
        """Test creating notification for website display."""
        notification = Notification.objects.create(
            farmer=self.farmer,
            title='Website Notification',
            message='This appears on the website.',
            sent_via_website=True,
            sent_via_email=False,
            sent_via_sms=False,
        )
        
        self.assertTrue(notification.sent_via_website)
        self.assertFalse(notification.sent_via_email)
        self.assertFalse(notification.sent_via_sms)

    def test_notification_via_sms(self):
        """Test creating notification for SMS delivery."""
        notification = Notification.objects.create(
            farmer=self.farmer,
            title='SMS Alert',
            message='Short message for SMS',
            sent_via_website=False,
            sent_via_email=False,
            sent_via_sms=True,
        )
        
        self.assertTrue(notification.sent_via_sms)

    @patch('app.views.send_verification_email')
    def test_notification_via_email(self, mock_send_email):
        """Test creating notification for email delivery."""
        mock_send_email.return_value = True
        
        notification = Notification.objects.create(
            farmer=self.farmer,
            title='Email Alert',
            message='Detailed message for email.',
            sent_via_website=False,
            sent_via_email=True,
            sent_via_sms=False,
        )
        
        self.assertTrue(notification.sent_via_email)

    def test_notification_multi_channel(self):
        """Test notification sent via multiple channels."""
        notification = Notification.objects.create(
            farmer=self.farmer,
            title='Multi-Channel Alert',
            message='Important alert for all channels.',
            sent_via_website=True,
            sent_via_email=True,
            sent_via_sms=True,
        )
        
        self.assertTrue(all([
            notification.sent_via_website,
            notification.sent_via_email,
            notification.sent_via_sms,
        ]))


class NotificationPreferencesTestCase(NotificationSetup):
    """Test notification preference management."""

    def test_get_notification_preferences(self):
        """Test retrieving notification preferences."""
        url = reverse('get_notification_preferences')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn('status', data)
        self.assertEqual(data['status'], 'success')
        self.assertIn('preferences', data)
        prefs = data['preferences']
        self.assertIn('notify_via_website', prefs)
        self.assertIn('notify_via_email', prefs)
        self.assertIn('notify_via_sms', prefs)

    def test_update_notification_preferences(self):
        """Test updating notification preferences."""
        url = reverse('update_notification_preferences')
        data = {
            'notify_via_website': True,
            'notify_via_email': False,
            'notify_via_sms': True,
        }
        response = self.client.post(url, data, content_type='application/json')
        
        self.assertEqual(response.status_code, 200)
        
        # Verify preferences were updated
        self.notification_prefs.refresh_from_db()
        self.assertTrue(self.notification_prefs.notify_via_website)
        self.assertFalse(self.notification_prefs.notify_via_email)
        self.assertTrue(self.notification_prefs.notify_via_sms)

    def test_disable_all_notification_channels(self):
        """Test disabling all notification channels."""
        url = reverse('update_notification_preferences')
        data = {
            'notify_via_website': False,
            'notify_via_email': False,
            'notify_via_sms': False,
        }
        response = self.client.post(url, data, content_type='application/json')
        
        self.notification_prefs.refresh_from_db()
        self.assertFalse(self.notification_prefs.notify_via_website)
        self.assertFalse(self.notification_prefs.notify_via_email)
        self.assertFalse(self.notification_prefs.notify_via_sms)

    def test_enable_all_notification_channels(self):
        """Test enabling all notification channels."""
        # First disable all
        self.notification_prefs.notify_via_website = False
        self.notification_prefs.notify_via_email = False
        self.notification_prefs.notify_via_sms = False
        self.notification_prefs.save()
        
        # Now enable all
        url = reverse('update_notification_preferences')
        data = {
            'notify_via_website': True,
            'notify_via_email': True,
            'notify_via_sms': True,
        }
        response = self.client.post(url, data, content_type='application/json')
        
        self.notification_prefs.refresh_from_db()
        self.assertTrue(self.notification_prefs.notify_via_website)
        self.assertTrue(self.notification_prefs.notify_via_email)
        self.assertTrue(self.notification_prefs.notify_via_sms)

    def test_preferences_require_authentication(self):
        """Test that preference endpoints require authentication."""
        self.client.logout()
        
        url = reverse('get_notification_preferences')
        response = self.client.get(url, follow=True)
        
        # Should redirect to login
        self.assertRedirects(response, f"{reverse('auth')}?next={url}")


class NotificationRetrievalTestCase(NotificationSetup):
    """Test retrieving and managing notifications."""

    def test_get_farmer_notifications(self):
        """Test retrieving farmer's notifications."""
        # Create some notifications
        notifications_created = []
        for i in range(5):
            notif = Notification.objects.create(
                farmer=self.farmer,
                title=f'Notification {i+1}',
                message=f'Message {i+1}',
            )
            notifications_created.append(notif)
        
        url = reverse('get_notifications')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn('notifications', data)

    def test_unread_notifications_count(self):
        """Test counting unread notifications."""
        # Create mix of read and unread
        Notification.objects.create(
            farmer=self.farmer,
            title='Unread 1',
            message='Unread notification',
            status='unread',
        )
        
        notif_read = Notification.objects.create(
            farmer=self.farmer,
            title='Read 1',
            message='Read notification',
            status='read',
        )
        
        unread_count = Notification.objects.filter(
            farmer=self.farmer,
            status='unread'
        ).count()
        
        self.assertEqual(unread_count, 1)

    def test_mark_notification_as_read(self):
        """Test marking a notification as read."""
        notification = Notification.objects.create(
            farmer=self.farmer,
            title='Alert',
            message='Test alert',
            status='unread',
        )
        
        url = reverse('mark_notification_as_read', args=[notification.id])
        response = self.client.post(url)
        
        # Notification should be marked as read
        notification.refresh_from_db()
        self.assertEqual(notification.status, 'read')
        self.assertIsNotNone(notification.read_at)

    def test_delete_notification(self):
        """Test deleting a notification."""
        notification = Notification.objects.create(
            farmer=self.farmer,
            title='To Delete',
            message='This will be deleted',
        )
        
        url = reverse('delete_notification', args=[notification.id])
        response = self.client.post(url)
        
        # Notification should be deleted
        self.assertFalse(Notification.objects.filter(id=notification.id).exists())

    def test_notifications_sorted_by_date(self):
        """Test that notifications are sorted by creation date (newest first)."""
        # Create notifications with different times
        notif1 = Notification.objects.create(
            farmer=self.farmer,
            title='Old Notification',
            message='Created first',
        )
        # Manually adjust timestamps
        notif1.created_at = timezone.now() - timedelta(hours=2)
        notif1.save()
        
        notif2 = Notification.objects.create(
            farmer=self.farmer,
            title='New Notification',
            message='Created last',
        )
        
        notifications = Notification.objects.filter(farmer=self.farmer).order_by('-created_at')
        
        self.assertEqual(notifications.first().id, notif2.id)

    def test_cannot_access_others_notifications(self):
        """Test that users cannot access other farmers' notifications."""
        # Create second farmer
        user2 = CustomUser.objects.create_user(
            email='farmer2@example.com',
            password='TestPassword123!'
        )
        farmer2 = Farmer.objects.create(
            fname='Jane',
            lname='Smith',
            email=user2.email,
        )
        
        # Create notification for second farmer
        notif = Notification.objects.create(
            farmer=farmer2,
            title='Secret Notification',
            message='Only for farmer2',
        )
        
        # First farmer should not see it
        notifications = Notification.objects.filter(farmer=self.farmer)
        self.assertFalse(notifications.filter(id=notif.id).exists())


class RegionalNotificationTestCase(TestCase):
    """Test regional notifications sent to multiple farmers."""

    def setUp(self):
        # Create multiple farmers in the same region
        self.farmers = []
        for i in range(3):
            user = CustomUser.objects.create_user(
                email=f'farmer{i}@example.com',
                password='TestPassword123!'
            )
            farmer = Farmer.objects.create(
                fname=f'Farmer{i}',
                lname='Test',
                email=user.email,
            )
            
            farm = Farm.objects.create(
                farmer=farmer,
                farm_name=f'Farm {i}',
                crop_type='maize',
                farm_size=5.0,
                county='Nairobi',
                sub_county='Westlands',
                ward='Chiromo Ward',
            )
            
            self.farmers.append(farmer)

    def test_create_regional_notification(self):
        """Test creating a regional notification."""
        regional_notif = RegionalNotification.objects.create(
            title='County-wide Advisory',
            message='Important advisory for all farmers in Nairobi',
            notification_type='advisory',
            region_level='county',
            region_name='Nairobi',
            status='draft',
        )
        
        self.assertEqual(regional_notif.region_level, 'county')
        self.assertEqual(regional_notif.region_name, 'Nairobi')

    def test_regional_notification_targeting_sub_county(self):
        """Test regional notification targeting specific sub-county."""
        regional_notif = RegionalNotification.objects.create(
            title='Sub-county Alert',
            message='Alert for Westlands sub-county',
            notification_type='weather_alert',
            region_level='sub_county',
            region_name='Westlands',
            status='draft',
        )
        
        self.assertEqual(regional_notif.region_level, 'sub_county')

    def test_regional_notification_with_crop_targeting(self):
        """Test regional notification targeting specific crop types."""
        regional_notif = RegionalNotification.objects.create(
            title='Maize-specific Alert',
            message='Alert for maize farmers',
            notification_type='pest_alert',
            region_level='county',
            region_name='Nairobi',
            crop_types=['maize'],
            status='draft',
        )
        
        self.assertEqual(regional_notif.crop_types, ['maize'])

    def test_regional_notification_scheduling(self):
        """Test scheduling regional notification for future delivery."""
        future_time = timezone.now() + timedelta(hours=2)
        
        regional_notif = RegionalNotification.objects.create(
            title='Scheduled Alert',
            message='This will be sent later',
            notification_type='advisory',
            region_level='county',
            region_name='Nairobi',
            scheduled_for=future_time,
            status='scheduled',
        )
        
        self.assertEqual(regional_notif.status, 'scheduled')
        self.assertEqual(regional_notif.scheduled_for, future_time)

    def test_regional_notification_sent_status(self):
        """Test marking regional notification as sent."""
        regional_notif = RegionalNotification.objects.create(
            title='Sent Alert',
            message='This has been sent',
            notification_type='advisory',
            region_level='county',
            region_name='Nairobi',
            status='sent',
            target_farmer_count=3,
            sent_count=3,
        )
        
        self.assertEqual(regional_notif.status, 'sent')
        self.assertEqual(regional_notif.target_farmer_count, 3)
        self.assertEqual(regional_notif.sent_count, 3)


class NotificationAlertTypesTestCase(NotificationSetup):
    """Test various notification alert types."""

    def test_all_notification_types(self):
        """Test creating notifications of all available types."""
        notification_types = [
            'planting_date',
            'rainfall',
            'dry_spell',
            'soil_moisture',
            'risk_alert',
            'advisory',
        ]
        
        for notif_type in notification_types:
            notification = Notification.objects.create(
                farmer=self.farmer,
                title=f'{notif_type} Alert',
                message=f'Test {notif_type} notification',
                notification_type=notif_type,
            )
            
            self.assertEqual(notification.notification_type, notif_type)

    def test_notification_with_metadata(self):
        """Test notifications storing complex metadata."""
        notification = Notification.objects.create(
            farmer=self.farmer,
            title='Complex Alert',
            message='Alert with rich data',
            metadata={
                'rainfall': {'expected_mm': 50, 'probability': 0.85},
                'crops_affected': ['maize', 'beans'],
                'action_required': True,
            },
        )
        
        self.assertIn('rainfall', notification.metadata)
        self.assertEqual(notification.metadata['rainfall']['expected_mm'], 50)

    def test_notification_with_regional_info(self):
        """Test notification with regional location information."""
        notification = Notification.objects.create(
            farmer=self.farmer,
            title='Regional Rain Alert',
            message='Alert for your region',
            county='Nairobi',
            sub_county='Westlands',
            ward='Chiromo Ward',
        )
        
        self.assertEqual(notification.county, 'Nairobi')
        self.assertEqual(notification.sub_county, 'Westlands')
        self.assertEqual(notification.ward, 'Chiromo Ward')


class NotificationTimestampTestCase(NotificationSetup):
    """Test notification timestamp and timing functionality."""

    def test_notification_read_timestamp(self):
        """Test that reading a notification records the time."""
        notification = Notification.objects.create(
            farmer=self.farmer,
            title='Alert',
            message='Test alert',
        )
        
        self.assertIsNone(notification.read_at)
        
        # Mark as read
        notification.status = 'read'
        notification.read_at = timezone.now()
        notification.save()
        
        self.assertIsNotNone(notification.read_at)

    def test_notifications_created_in_correct_order(self):
        """Test that notifications maintain creation order."""
        notif_ids = []
        for i in range(5):
            notif = Notification.objects.create(
                farmer=self.farmer,
                title=f'Alert {i}',
                message=f'Message {i}',
            )
            notif_ids.append(notif.id)
        
        ordered = Notification.objects.filter(
            farmer=self.farmer
        ).order_by('created_at').values_list('id', flat=True)
        
        self.assertEqual(list(ordered), notif_ids)
