"""Tests for notification utilities.
Covers notification_utils.py and Notification models low-coverage areas.
"""
from django.test import TestCase
from django.contrib.auth import get_user_model
from unittest.mock import patch, MagicMock, call
from app.models import Farmer, Farm, Notification, NotificationPreference, NotificationTriggerLog
from app.notification_utils import (
    send_sms, send_email, create_and_send_notification,
    log_trigger_event, check_rainfall_alert
)
import requests

CustomUser = get_user_model()


class SMSGatewayTestCase(TestCase):
    """Test SMS gateway communication."""

    @patch('app.notification_utils.requests.post')
    def test_send_sms_success(self, mock_post):
        """Test successful SMS sending via gateway."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_post.return_value = mock_response
        
        result = send_sms('+254712345678', 'Test message')
        
        self.assertTrue(result)
        mock_post.assert_called_once()

    @patch('app.notification_utils.requests.post')
    def test_send_sms_gateway_failure(self, mock_post):
        """Test SMS failure from gateway."""
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.text = 'Internal server error'
        mock_post.return_value = mock_response
        
        result = send_sms('+254712345678', 'Test message')
        
        self.assertFalse(result)

    @patch('app.notification_utils.requests.post')
    def test_send_sms_network_error(self, mock_post):
        """Test SMS with network error."""
        mock_post.side_effect = requests.exceptions.Timeout('Connection timeout')
        
        result = send_sms('+254712345678', 'Test message')
        
        self.assertFalse(result)

    @patch('app.notification_utils.requests.post')
    def test_send_sms_invalid_phone(self, mock_post):
        """Test SMS with invalid phone number."""
        result = send_sms('', 'Test message')
        
        self.assertFalse(result)
        mock_post.assert_not_called()

    @patch('app.notification_utils.requests.post')
    def test_send_sms_no_message(self, mock_post):
        """Test SMS with empty message."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_post.return_value = mock_response
        
        result = send_sms('+254712345678', '')
        
        # Should still attempt to send
        self.assertTrue(result)

    @patch('app.notification_utils.requests.post')
    def test_send_sms_various_formats(self, mock_post):
        """Test SMS with various phone number formats."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_post.return_value = mock_response
        
        phones = ['+254712345678', '+1234567890', '+447911123456']
        for phone in phones:
            result = send_sms(phone, 'Test')
            self.assertTrue(result)


class EmailNotificationTestCase(TestCase):
    """Test email notification system."""

    @patch('app.notification_utils.send_mail')
    def test_send_email_success(self, mock_send_mail):
        """Test successful email sending."""
        mock_send_mail.return_value = 1
        
        result = send_email('user@example.com', 'Subject', 'Message')
        
        self.assertTrue(result)
        mock_send_mail.assert_called_once()

    @patch('app.notification_utils.send_mail')
    def test_send_email_with_html(self, mock_send_mail):
        """Test email with HTML content."""
        mock_send_mail.return_value = 1
        
        result = send_email('user@example.com', 'Subject', 'Text', '<p>HTML</p>')
        
        self.assertTrue(result)

    @patch('app.notification_utils.send_mail')
    def test_send_email_failure(self, mock_send_mail):
        """Test email sending failure."""
        mock_send_mail.side_effect = Exception('SMTP error')
        
        result = send_email('user@example.com', 'Subject', 'Message')
        
        self.assertFalse(result)

    @patch('app.notification_utils.send_mail')
    def test_send_email_no_recipient(self, mock_send_mail):
        """Test email with no recipient."""
        result = send_email('', 'Subject', 'Message')
        
        self.assertFalse(result)
        mock_send_mail.assert_not_called()

    @patch('app.notification_utils.send_mail')
    def test_send_email_various_recipients(self, mock_send_mail):
        """Test email to various recipients."""
        mock_send_mail.return_value = 1
        
        recipients = ['user@example.com', 'farmer@test.org', 'admin@crpas.io']
        for email in recipients:
            result = send_email(email, 'Subject', 'Message')
            self.assertTrue(result)


class NotificationCreationTestCase(TestCase):
    """Test notification creation and sending."""

    def setUp(self):
        """Create test user and farmer."""
        self.user = CustomUser.objects.create_user(
            email='farmer@example.com',
            password='Password123!'
        )
        self.user.email_verified = True
        self.user.save()
        
        self.farmer = Farmer.objects.create(
            fname='John',
            lname='Doe',
            email=self.user.email,
            phone='+254712345678'
        )
        
        self.farm = Farm.objects.create(
            farmer=self.farmer,
            farm_name='Test Farm',
            crop_type='maize',
            farm_size=2.0,
            county='Nairobi',
            sub_county='Westlands',
            ward='Chiromo Ward',
            lat=-1.2833,
            long=36.8167,
        )

    @patch('app.notification_utils.send_sms')
    @patch('app.notification_utils.send_email')
    def test_create_notification_basic(self, mock_email, mock_sms):
        """Test basic notification creation."""
        mock_sms.return_value = True
        mock_email.return_value = True
        
        notification = Notification.objects.create(
            farmer=self.farmer,
            title='Weather Alert',
            message='Heavy rain expected',
            notification_type='rainfall',
            county='Nairobi',
            sent_via_sms=True,
            sent_via_email=False,
            sent_via_website=True,
        )
        
        self.assertIsNotNone(notification)
        self.assertEqual(notification.farmer, self.farmer)
        self.assertTrue(notification.sent_via_sms)
        self.assertFalse(notification.sent_via_email)

    @patch('app.notification_utils.send_sms')
    @patch('app.notification_utils.send_email')
    def test_create_notification_with_email(self, mock_email, mock_sms):
        """Test notification creation with email delivery."""
        mock_sms.return_value = True
        mock_email.return_value = True
        
        notification = Notification.objects.create(
            farmer=self.farmer,
            title='Advisory Update',
            message='New farming advisory available',
            notification_type='advisory',
            county='Nairobi',
            sent_via_sms=False,
            sent_via_email=True,
            sent_via_website=True,
        )
        
        self.assertTrue(notification.sent_via_email)
        self.assertFalse(notification.sent_via_sms)

    def test_notification_trigger_log(self):
        """Test notification trigger logging."""
        notification = Notification.objects.create(
            farmer=self.farmer,
            title='Test Alert',
            message='Test message',
            notification_type='risk_alert',
            county='Nairobi',
        )
        
        trigger_log = NotificationTriggerLog.objects.create(
            farmer=self.farmer,
            notification=notification,
            trigger_type='rainfall',
            trigger_data={'condition': 'heavy_rain', 'rainfall_mm': 45}
        )
        
        self.assertEqual(trigger_log.notification, notification)
        self.assertIsNotNone(trigger_log.created_at)
        self.assertTrue(trigger_log.processed)

    def test_notification_preferences(self):
        """Test notification preferences."""
        prefs = NotificationPreference.objects.create(
            farmer=self.farmer,
            notify_via_sms=True,
            notify_via_email=False,
            notify_via_website=True,
        )
        
        self.assertTrue(prefs.notify_via_sms)
        self.assertFalse(prefs.notify_via_email)
        self.assertTrue(prefs.notify_via_website)
        self.assertEqual(prefs.farmer, self.farmer)

    def test_create_multiple_notifications_for_farmer(self):
        """Test creating multiple notifications for same farmer."""
        ntf1 = Notification.objects.create(
            farmer=self.farmer,
            title='Alert 1',
            message='Message 1',
            notification_type='rainfall',
            county='Nairobi',
        )
        
        ntf2 = Notification.objects.create(
            farmer=self.farmer,
            title='Alert 2',
            message='Message 2',
            notification_type='advisory',
            county='Nairobi',
        )
        
        farmer_notifs = Notification.objects.filter(farmer=self.farmer)
        self.assertEqual(farmer_notifs.count(), 2)

    def test_regional_notifications(self):
        """Test regional notification targeting."""
        # Create notifications for specific county
        notif = Notification.objects.create(
            farmer=self.farmer,
            title='Regional Alert',
            message='Message for Nairobi region',
            notification_type='rainfall',
            county='Nairobi',
            sub_county='Westlands',
            ward='Chiromo Ward',
        )
        
        self.assertEqual(notif.county, 'Nairobi')
        self.assertEqual(notif.sub_county, 'Westlands')
        self.assertEqual(notif.ward, 'Chiromo Ward')

    def test_notification_types(self):
        """Test different notification types."""
        types = ['planting_date', 'rainfall', 'dry_spell', 'soil_moisture', 'risk_alert', 'advisory']
        
        for notif_type in types:
            notif = Notification.objects.create(
                farmer=self.farmer,
                title=f'{notif_type} notification',
                message='Test message',
                notification_type=notif_type,
                county='Nairobi',
            )
            
            self.assertEqual(notif.notification_type, notif_type)


class NotificationIntegrationTestCase(TestCase):
    """Integration tests for full notification workflow."""

    def setUp(self):
        """Create test setup."""
        self.user = CustomUser.objects.create_user(
            email='integration_farmer@example.com',
            password='Password123!'
        )
        self.user.email_verified = True
        self.user.save()
        
        self.farmer = Farmer.objects.create(
            fname='Integration',
            lname='Farmer',
            email=self.user.email,
            phone='+254712345678'
        )
        
        self.farm = Farm.objects.create(
            farmer=self.farmer,
            farm_name='Integration Farm',
            crop_type='maize',
            farm_size=3.0,
            county='Kisii',
            sub_county='Kisii Central',
            ward='Keumbu Ward',
            lat=-0.6833,
            long=34.7833,
        )
        
        # Create notification preferences
        self.prefs = NotificationPreference.objects.create(
            farmer=self.farmer,
            notify_via_sms=True,
            notify_via_email=True,
            notify_via_website=True,
        )

    @patch('app.notification_utils.send_sms')
    @patch('app.notification_utils.send_email')
    def test_full_notification_workflow(self, mock_email, mock_sms):
        """Test complete notification workflow."""
        mock_sms.return_value = True
        mock_email.return_value = True
        
        # Create notification
        notification = Notification.objects.create(
            farmer=self.farmer,
            title='Heavy Rain Expected',
            message='Prepare for heavy rainfall in your region',
            notification_type='rainfall',
            county='Kisii',
            sub_county='Kisii Central',
            sent_via_sms=True,
            sent_via_email=True,
            sent_via_website=True,
        )
        
        # Create trigger log
        trigger = NotificationTriggerLog.objects.create(
            farmer=self.farmer,
            notification=notification,
            trigger_type='rainfall',
            trigger_data={'rainfall_mm': 45, 'probability': 95}
        )
        
        # Verify notification created
        self.assertIsNotNone(notification.id)
        self.assertEqual(notification.farmer, self.farmer)
        self.assertIsNotNone(trigger.created_at)
        self.assertTrue(trigger.processed)

    def test_farmer_notification_history(self):
        """Test farmer notification history."""
        # Create multiple notifications
        notifications = []
        for i in range(5):
            notif = Notification.objects.create(
                farmer=self.farmer,
                title=f'Notification {i}',
                message=f'Message {i}',
                notification_type='advisory',
                county='Kisii',
            )
            notifications.append(notif)
        
        # Check history
        farmer_notifs = Notification.objects.filter(farmer=self.farmer)
        self.assertEqual(farmer_notifs.count(), 5)
        
        # Should be able to query by date
        self.assertTrue(farmer_notifs.first().created_at is not None)
        
    def test_notification_read_status(self):
        """Test notification read/unread status."""
        notification = Notification.objects.create(
            farmer=self.farmer,
            title='Status Test',
            message='Test message',
            notification_type='advisory',
            status='unread',
            county='Kisii',
        )
        
        self.assertEqual(notification.status, 'unread')
        # Simulate reading
        notification.status = 'read'
        notification.save()
        
        # Verify status updated
        refreshed = Notification.objects.get(id=notification.id)
        self.assertEqual(refreshed.status, 'read')
    
    def test_trigger_log_farmer_link(self):
        """Test trigger log farmer foreign key."""
        trigger = NotificationTriggerLog.objects.create(
            farmer=self.farmer,
            trigger_type='soil_moisture',
            trigger_data={'soil_moisture_m3m3': 0.15}
        )
        
        self.assertEqual(trigger.farmer, self.farmer)
        farmer_triggers = NotificationTriggerLog.objects.filter(farmer=self.farmer)
        self.assertEqual(farmer_triggers.count(), 1)
