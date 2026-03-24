"""
SMS service for sending verification codes.
Uses the existing SMS gateway system from notification_utils.py
"""

import logging
from .notification_utils import send_sms

logger = logging.getLogger(__name__)

def send_verification_sms(phone_number: str, verification_code: str) -> bool:
    """
    Send a verification code SMS to the user.
    Uses the existing SMS gateway configured in notification_utils.py
    
    Args:
        phone_number (str): The recipient's phone number (e.g., +254712345678)
        verification_code (str): The 6-digit verification code
        
    Returns:
        bool: True if SMS sent successfully, False otherwise
    """
    
    try:
        # Create message body
        message_body = f"Your CRPAS verification code is: {verification_code}\n\nThis code will expire in 10 minutes. If you did not request this code, please ignore this message."
        
        # Send SMS via the existing gateway
        result = send_sms(phone_number, message_body)
        
        if result:
            logger.info(f"✓ Verification SMS sent to {phone_number}")
        else:
            logger.error(f"✗ Failed to send verification SMS to {phone_number}")
        
        return result
        
    except Exception as e:
        logger.error(f"✗ Exception sending verification SMS to {phone_number}: {str(e)}")
        return False
