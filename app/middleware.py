"""
Middleware to enforce email verification before allowing access to protected views.
Redirects unverified users to the verification page.
"""

from django.shortcuts import redirect
from django.urls import reverse
from django.utils.deprecation import MiddlewareMixin
import logging

logger = logging.getLogger(__name__)

# URLs that should be accessible without email verification
UNVERIFIED_ALLOWED_URLS = [
    '/auth/',
    '/verify-email/',
    '/resend-verification/',
    '/phone-auth/',
    '/verify-phone/',
    '/resend-sms/',
    '/phone-signup-password/',
    '/api/',  # Allow API endpoints
    '/static/',  # Allow static files
    '/logout/',
]


class EmailVerificationMiddleware(MiddlewareMixin):
    """
    Middleware to check if authenticated users have verified their email.
    Redirects unverified users to the email verification page.
    
    This applies to all views except those in UNVERIFIED_ALLOWED_URLS.
    """
    
    def process_request(self, request):
        """
        Check if user is authenticated and email is verified.
        If not verified, redirect to verification page.
        """
        # Allow requests to unverified-allowed URLs
        if self._is_allowed_url(request.path):
            return None
        
        # Check if user is authenticated
        if not request.user.is_authenticated:
            return None
        
        # Check if user's email is verified
        if not request.user.email_verified:
            logger.info(f"Redirecting unverified user {request.user.email} to verification page")
            return redirect('verify_email')
        
        return None
    
    def _is_allowed_url(self, path):
        """
        Check if the given path is in the allowed URLs list.
        These URLs can be accessed without email verification.
        """
        for allowed_url in UNVERIFIED_ALLOWED_URLS:
            if path.startswith(allowed_url):
                return True
        return False
