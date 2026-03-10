"""
Email service for sending verification emails via Gmail SMTP.
Uses Gmail App Password for authentication (simpler than OAuth2 Service Accounts).
"""

import smtplib
import os
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import logging
from django.conf import settings
from dotenv import load_dotenv
load_dotenv()

logger = logging.getLogger(__name__)

# Gmail SMTP credentials - get from environment variables
GMAIL_ADDRESS = os.getenv('GMAIL_ADDRESS', '')
GMAIL_APP_PASSWORD = os.getenv('GMAIL_APP_PASSWORD', '')


def send_verification_email(recipient_email: str, verification_code: str) -> bool:
    """
    Send a verification code email to the user via Gmail SMTP.
    
    Prerequisites:
    1. Enable 2-Factor Authentication on your Gmail account
    2. Generate an App Password at: https://myaccount.google.com/apppasswords
    3. Set environment variables:
       - GMAIL_ADDRESS=your-email@gmail.com
       - GMAIL_APP_PASSWORD=your-app-password (16 characters without spaces)
    
    Args:
        recipient_email (str): The recipient's email address
        verification_code (str): The 6-digit verification code
        
    Returns:
        bool: True if email sent successfully, False otherwise
    """
    if not GMAIL_ADDRESS or not GMAIL_APP_PASSWORD:
        logger.error(
            "Gmail credentials not configured. "
            "Please set GMAIL_ADDRESS and GMAIL_APP_PASSWORD environment variables."
        )
        return False
    
    try:
        # Create the email message
        message = MIMEMultipart('alternative')
        message['to'] = recipient_email
        message['from'] = GMAIL_ADDRESS
        message['subject'] = 'CRPAS Email Verification - Verify Your Account'
        
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
        
        # Attach both plain text and HTML versions
        message.attach(MIMEText(text_body, 'plain'))
        message.attach(MIMEText(html_body, 'html'))
        
        # Send via Gmail SMTP
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
            server.login(GMAIL_ADDRESS, GMAIL_APP_PASSWORD)
            server.send_message(message)
        
        logger.info(f"Verification email sent successfully to {recipient_email}")
        return True
    
    except smtplib.SMTPAuthenticationError:
        logger.error(
            f"Gmail authentication failed. Check GMAIL_ADDRESS and GMAIL_APP_PASSWORD. "
            f"Make sure you're using an App Password, not your regular Gmail password."
        )
        return False
    except smtplib.SMTPException as e:
        logger.error(f"SMTP error sending verification email: {str(e)}")
        return False
    except Exception as e:
        logger.error(f"Unexpected error sending email: {str(e)}")
        return False


def send_test_email(recipient_email: str) -> bool:
    """
    Send a test email to verify Gmail SMTP configuration is working.
    
    Args:
        recipient_email (str): The recipient's email address
        
    Returns:
        bool: True if email sent successfully, False otherwise
    """
    if not GMAIL_ADDRESS or not GMAIL_APP_PASSWORD:
        logger.error(
            "Gmail credentials not configured. "
            "Please set GMAIL_ADDRESS and GMAIL_APP_PASSWORD environment variables."
        )
        return False
    
    try:
        # Create the email message
        message = MIMEMultipart('alternative')
        message['to'] = recipient_email
        message['from'] = GMAIL_ADDRESS
        message['subject'] = 'CRPAS Test Email - Configuration Successful'
        
        html_body = """
        <html>
            <body style="font-family: Arial, sans-serif;">
                <h2 style="color: #007726;">CRPAS Gmail SMTP Test</h2>
                <p>If you received this email, the Gmail SMTP configuration is working correctly!</p>
                <p>You can now use email notifications in CRPAS.</p>
            </body>
        </html>
        """
        
        message.attach(MIMEText(html_body, 'html'))
        
        # Send via Gmail SMTP
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
            server.login(GMAIL_ADDRESS, GMAIL_APP_PASSWORD)
            server.send_message(message)
        
        logger.info(f"Test email sent successfully to {recipient_email}")
        return True
    
    except Exception as e:
        logger.error(f"Test email failed: {str(e)}")
        return False
