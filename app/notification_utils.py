"""
Notification utilities for sending notifications via SMS, email, and website.
Handles the business logic for creating and sending different types of notifications.
"""

import logging
import requests
import threading
from django.core.mail import send_mail
from django.conf import settings
from django.utils import timezone
from datetime import datetime, timedelta
from .models import Notification, NotificationPreference, NotificationTriggerLog, Farmer

logger = logging.getLogger(__name__)

# SMS Gateway Configuration
SMS_GATEWAY_URL = "http://192.168.13.105:8080"
SMS_TIMEOUT = 10  # seconds


def send_sms(phone_number, message):
    """
    Send SMS via the configured SMS gateway.
    
    Args:
        phone_number (str): Phone number in format like +254790341425
        message (str): SMS message content
        
    Returns:
        bool: True if SMS was sent successfully, False otherwise
    """
    if not phone_number:
        logger.warning("No phone number provided for SMS")
        return False
    
    try:
        payload = {
            "phone": phone_number,
            "message": message
        }
        
        response = requests.post(
            SMS_GATEWAY_URL,
            json=payload,
            timeout=SMS_TIMEOUT,
            headers={"Content-Type": "application/json"}
        )
        
        if response.status_code == 200:
            logger.info(f"SMS sent successfully to {phone_number}")
            return True
        else:
            logger.error(f"SMS gateway returned status {response.status_code}: {response.text}")
            return False
            
    except requests.exceptions.RequestException as e:
        logger.error(f"Failed to send SMS to {phone_number}: {str(e)}")
        return False
    except Exception as e:
        logger.error(f"Unexpected error sending SMS: {str(e)}")
        return False


def send_email(recipient_email, subject, message, html_message=None):
    """
    Send email notification.
    
    Args:
        recipient_email (str): Email address
        subject (str): Email subject
        message (str): Plain text message
        html_message (str): HTML version of message (optional)
        
    Returns:
        bool: True if email was sent successfully, False otherwise
    """
    if not recipient_email:
        logger.warning("No email address provided for sending email")
        return False
    
    try:
        send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[recipient_email],
            html_message=html_message,
            fail_silently=False,
        )
        logger.info(f"Email sent successfully to {recipient_email}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to send email to {recipient_email}: {str(e)}")
        return False


def create_and_send_notification(
    farmer,
    title,
    message,
    notification_type='advisory',
    metadata=None,
    send_async=True
):
    """
    Create a notification and send it via configured channels.
    
    Args:
        farmer (Farmer): The farmer to send notification to
        title (str): Notification title
        message (str): Notification message
        notification_type (str): Type of notification
        metadata (dict): Additional metadata to store with notification
        send_async (bool): Whether to send via background thread
        
    Returns:
        Notification: The created notification object
    """
    try:
        # Get or create notification preferences for farmer
        prefs, _ = NotificationPreference.objects.get_or_create(farmer=farmer)
        
        # Create notification record
        notification = Notification.objects.create(
            farmer=farmer,
            title=title,
            message=message,
            notification_type=notification_type,
            metadata=metadata or {},
            status='unread'
        )
        
        # Determine which channels to use
        channels_to_send = {
            'website': prefs.notify_via_website,
            'email': prefs.notify_via_email,
            'sms': prefs.notify_via_sms,
        }
        
        # Send notifications
        if send_async:
            # Send in background thread to avoid blocking
            thread = threading.Thread(
                target=_send_notification_channels,
                args=(notification, channels_to_send)
            )
            thread.start()
        else:
            _send_notification_channels(notification, channels_to_send)
        
        logger.info(f"Notification created for {farmer}: {title}")
        return notification
        
    except Exception as e:
        logger.error(f"Failed to create notification for {farmer}: {str(e)}")
        return None


def _send_notification_channels(notification, channels_to_send):
    """
    Internal function to send notification via selected channels.
    
    Args:
        notification (Notification): The notification to send
        channels_to_send (dict): Dictionary of channels and whether to send
    """
    farmer = notification.farmer
    
    # Website notification (always stored in database)
    if channels_to_send.get('website'):
        notification.sent_via_website = True
        notification.save()
    
    # Email notification
    if channels_to_send.get('email') and farmer.email:
        email_sent = send_email(
            recipient_email=farmer.email,
            subject=f"CRPAS Alert: {notification.title}",
            message=notification.message,
            html_message=f"<h3>{notification.title}</h3><p>{notification.message}</p>"
        )
        if email_sent:
            notification.sent_via_email = True
    
    # SMS notification
    if channels_to_send.get('sms') and farmer.phone:
        # Limit SMS to 160 characters
        sms_message = notification.message[:160]
        sms_sent = send_sms(
            phone_number=farmer.phone,
            message=sms_message
        )
        if sms_sent:
            notification.sent_via_sms = True
    
    # Update notification with sent status
    notification.save()


def log_trigger_event(farmer, trigger_type, trigger_data, notification=None):
    """
    Log a trigger event that caused a notification.
    
    Args:
        farmer (Farmer): The farmer associated with trigger
        trigger_type (str): Type of trigger
        trigger_data (dict): Raw trigger data
        notification (Notification): Associated notification (optional)
        
    Returns:
        NotificationTriggerLog: The created log entry
    """
    try:
        log_entry = NotificationTriggerLog.objects.create(
            farmer=farmer,
            trigger_type=trigger_type,
            trigger_data=trigger_data,
            notification=notification,
            processed=True
        )
        logger.info(f"Logged {trigger_type} trigger for {farmer}")
        return log_entry
    except Exception as e:
        logger.error(f"Failed to log trigger event: {str(e)}")
        return None


def check_rainfall_alert(farmer, rainfall_data):
    """
    Check if rainfall data should trigger a notification.
    Creates notification if rainfall exceeds threshold or after dry spell.
    
    Args:
        farmer (Farmer): The farmer
        rainfall_data (dict): Contains 'amount' (mm) and 'date' info
        
    Returns:
        Notification: Created notification or None
    """
    try:
        rainfall_amount = rainfall_data.get('amount', 0)
        rainfall_date = rainfall_data.get('date', timezone.now().date())
        
        # Check if rainfall is significant (more than 10mm is good)
        if rainfall_amount > 10:
            notification = create_and_send_notification(
                farmer=farmer,
                title=f"Rainfall Alert: {rainfall_amount}mm recorded",
                message=f"Good news! {rainfall_amount}mm of rainfall was recorded in your area on {rainfall_date}. "
                        f"This is excellent for your crops. Ensure proper drainage to avoid waterlogging.",
                notification_type='rainfall',
                metadata={'rainfall_amount': rainfall_amount, 'date': str(rainfall_date)}
            )
            log_trigger_event(farmer, 'rainfall', rainfall_data, notification)
            return notification
        
        # Check for dry spell (no rain for extended period)
        seven_days_ago = timezone.now().date() - timedelta(days=7)
        recent_rainfall = Notification.objects.filter(
            farmer=farmer,
            notification_type='rainfall',
            created_at__gte=timezone.make_aware(
                datetime.combine(seven_days_ago, datetime.min.time())
            )
        ).exists()
        
        if rainfall_amount < 5 and not recent_rainfall:
            notification = create_and_send_notification(
                farmer=farmer,
                title="Dry Spell Warning",
                message=f"Low rainfall ({rainfall_amount}mm) recorded. A dry spell may be developing in your area. "
                        f"Consider irrigation or field moisture management practices.",
                notification_type='dry_spell',
                metadata={'rainfall_amount': rainfall_amount, 'date': str(rainfall_date)}
            )
            log_trigger_event(farmer, 'dry_spell', rainfall_data, notification)
            return notification
            
    except Exception as e:
        logger.error(f"Error checking rainfall alert for {farmer}: {str(e)}")
    
    return None


def check_soil_moisture_alert(farmer, soil_data):
    """
    Check if soil moisture data should trigger a notification.
    
    Args:
        farmer (Farmer): The farmer
        soil_data (dict): Contains 'moisture_percent' and other soil metrics
        
    Returns:
        Notification: Created notification or None
    """
    try:
        moisture_percent = soil_data.get('moisture_percent', 0)
        soil_type = soil_data.get('soil_type', 'unknown')
        
        # Different thresholds for different crops
        if farmer.crop_type == 'maize':
            optimal_min = 40
            optimal_max = 70
        else:  # beans or intercropped
            optimal_min = 35
            optimal_max = 65
        
        # Check for too dry
        if moisture_percent < optimal_min:
            notification = create_and_send_notification(
                farmer=farmer,
                title=f"⚠️ Soil Moisture Low: {moisture_percent}%",
                message=f"Soil moisture in your field is at {moisture_percent}%. "
                        f"This is below the optimal range for {farmer.get_crop_type_display()}. "
                        f"Consider irrigation or increase watering frequency.",
                notification_type='soil_moisture',
                metadata={'moisture_percent': moisture_percent, 'soil_type': soil_type}
            )
            log_trigger_event(farmer, 'soil_moisture', soil_data, notification)
            return notification
        
        # Check for too wet
        elif moisture_percent > optimal_max:
            notification = create_and_send_notification(
                farmer=farmer,
                title=f"Soil Moisture High: {moisture_percent}%",
                message=f"Soil moisture is at {moisture_percent}%, which is above optimal. "
                        f"Ensure proper drainage to prevent root rot and fungal diseases.",
                notification_type='soil_moisture',
                metadata={'moisture_percent': moisture_percent, 'soil_type': soil_type}
            )
            log_trigger_event(farmer, 'soil_moisture', soil_data, notification)
            return notification
            
    except Exception as e:
        logger.error(f"Error checking soil moisture alert for {farmer}: {str(e)}")
    
    return None


def check_planting_date_alert(farmer):
    """
    Check if it's an optimal time for planting based on rainfall patterns.
    
    Args:
        farmer (Farmer): The farmer
        
    Returns:
        Notification: Created notification or None
    """
    try:
        # This would typically fetch rainfall data for last 2-4 weeks
        # For now, we'll check the farmer's recent notifications
        
        recent_good_rainfall = Notification.objects.filter(
            farmer=farmer,
            notification_type='rainfall',
            created_at__gte=timezone.now() - timedelta(days=14)
        ).filter(metadata__rainfall_amount__gte=10).count()
        
        if recent_good_rainfall >= 2:
            crop_name = farmer.get_crop_type_display()
            notification = create_and_send_notification(
                farmer=farmer,
                title=f"✅ Optimal Planting Time for {crop_name}",
                message=f"Recent rainfall in your area (40mm+ over 2 weeks) indicates good soil moisture. "
                        f"Now is an excellent time to plant {crop_name}. "
                        f"Prepare your field and plant within the next week.",
                notification_type='planting_date',
                metadata={'crop': farmer.crop_type, 'date': str(timezone.now().date())}
            )
            log_trigger_event(farmer, 'planting_date', {'crop': farmer.crop_type}, notification)
            return notification
            
    except Exception as e:
        logger.error(f"Error checking planting date alert for {farmer}: {str(e)}")
    
    return None
