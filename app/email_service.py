"""
Email service for sending verification emails via Django's Email Backend.
Uses Gmail SMTP configured in settings.py
"""

import logging
from django.core.mail import EmailMultiAlternatives
from django.conf import settings

logger = logging.getLogger(__name__)

print("Default from email:", settings.DEFAULT_FROM_EMAIL)

def send_verification_email(recipient_email: str, verification_code: str) -> bool:
    """
    Send a verification code email to the user via Django's Email Backend.
    
    Prerequisites:
    1. Enable 2-Factor Authentication on your Gmail account
    2. Generate an App Password at: https://myaccount.google.com/apppasswords
    3. Add to .env file:
       - GMAIL_ADDRESS=your-email@gmail.com
       - GMAIL_APP_PASSWORD=your-app-password (16 characters without spaces)
    
    Args:
        recipient_email (str): The recipient's email address
        verification_code (str): The 6-digit verification code
        
    Returns:
        bool: True if email sent successfully, False otherwise
    """
    
    try:
        # Create HTML email body
        html_body = f"""
        <html>
            <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
                <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
                    <div style="text-align: center; margin-bottom: 30px;">
                        <h2 style="color: #007726;">Welcome to CRPAS</h2>
                    </div>
                    
                    <div style="background-color: #f5f5f5; padding: 20px; border-radius: 5px; margin-bottom: 20px;">
                        <p>Hello,</p>
                        
                        <p>Thank you for signing up for <strong>CRPAS</strong> (Climate-Responsive Precision Agriculture System). 
                        To verify your email address and complete your account setup, please enter the verification code below:</p>
                        
                        <div style="background-color: #007726; color: white; padding: 15px; text-align: center; border-radius: 5px; margin: 20px 0;">
                            <p style="font-size: 24px; font-weight: bold; letter-spacing: 2px; margin: 0;">
                                {verification_code}
                            </p>
                        </div>
                        
                        <p style="color: #666; font-size: 14px; margin-top: 15px;">
                            <strong>Note:</strong> This code will expire in 10 minutes. If you did not sign up for this account, please ignore this email.
                        </p>
                        
                        <p>Best regards,<br/>
                        <strong>CRPAS Team</strong><br/>
                        Your trusted agricultural advisory partner
                        </p>
                    </div>
                    
                    <div style="border-top: 1px solid #ddd; padding-top: 20px; text-align: center; color: #999; font-size: 12px;">
                        <p>This is an automated message. Please do not reply to this email.</p>
                        <p>&copy; 2026 CRPAS. All rights reserved.</p>
                    </div>
                </div>
            </body>
        </html>
        """
        
        # Plain text fallback
        text_body = f"""
Hello,

Thank you for signing up for CRPAS (Climate-Responsive Precision Agriculture System).

To verify your email address, please enter the verification code below:

{verification_code}

This code will expire in 10 minutes. If you did not sign up for this account, please ignore this email.

Best regards,
CRPAS Team
Your trusted agricultural advisory partner
        """
        
        # Create email message with both plain text and HTML
        email = EmailMultiAlternatives(
            subject='CRPAS Email Verification - Verify Your Account',
            body=text_body,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[recipient_email],
        )
        email.attach_alternative(html_body, 'text/html')
        
        # Send the email
        email.send(fail_silently=False)
        
        logger.info(f"Verification email sent successfully to {recipient_email}")
        return True
    
    except Exception as e:
        logger.error(f"Failed to send verification email: {str(e)}")
        return False


def send_test_email(recipient_email: str) -> bool:
    """
    Send a test email to verify Django's email configuration is working.
    
    Args:
        recipient_email (str): The recipient's email address
        
    Returns:
        bool: True if email sent successfully, False otherwise
    """
    
    try:
        html_body = """
        <html>
            <body style="font-family: Arial, sans-serif;">
                <h2 style="color: #007726;">CRPAS Email Configuration Test</h2>
                <p>If you received this email, the Django email backend is configured correctly!</p>
                <p>You can now use email notifications in CRPAS.</p>
            </body>
        </html>
        """
        
        text_body = """
CRPAS Email Configuration Test

If you received this email, the Django email backend is configured correctly!
You can now use email notifications in CRPAS.
        """
        
        email = EmailMultiAlternatives(
            subject='CRPAS Test Email - Configuration Successful',
            body=text_body,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[recipient_email],
        )
        email.attach_alternative(html_body, 'text/html')
        
        email.send(fail_silently=False)
        
        logger.info(f"Test email sent successfully to {recipient_email}")
        return True
    
    except Exception as e:
        logger.error(f"Test email failed: {str(e)}")
        return False
