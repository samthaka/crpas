"""
Custom adapter for django-allauth to handle social account authentication.
This adapter automatically creates a Farmer profile when users sign up via Google.
"""
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from allauth.socialaccount.models import SocialAccount
from django.contrib.auth import get_user_model
from .models import Farmer
import logging

logger = logging.getLogger(__name__)
CustomUser = get_user_model()


class SocialAccountAdapter(DefaultSocialAccountAdapter):
    """
    Custom adapter that extends allauth's default behavior for social account authentication.
    Specifically ensures Farmer profiles are created for new users signing up via Google.
    """
    
    def pre_social_login(self, request, sociallogin):
        """
        Called when a user logs in via a social provider (Google in this case).
        This runs before the user is actually logged in.
        """
        # If the user is already logged in, do nothing
        if sociallogin.is_existing:
            return
        
        # Check if email exists in the system
        try:
            email = sociallogin.account.extra_data.get('email')
            existing_user = CustomUser.objects.get(email=email)
            # Connect the social account to the existing user
            sociallogin.connect(request, existing_user)
        except CustomUser.DoesNotExist:
            # User doesn't exist, will be created in post_social_login
            pass
    
    def post_social_login(self, request, sociallogin):
        """
        Called after the user is successfully authenticated.
        This is where we can create a Farmer profile if needed.
        """
        user = sociallogin.user
        
        # Check if a Farmer profile already exists for this user
        farmer_exists = Farmer.objects.filter(email=user.email).exists()
        
        if not farmer_exists:
            try:
                # Extract name from social account data
                # Google provides 'name' or we can construct it from 'given_name' and 'family_name'
                extra_data = sociallogin.account.extra_data
                
                name = extra_data.get('name', '')
                given_name = extra_data.get('given_name', '')
                family_name = extra_data.get('family_name', '')
                
                # Extract first and last names
                if given_name and family_name:
                    fname = given_name
                    lname = family_name
                elif name:
                    # Parse the full name if given_name/family_name not available
                    name_parts = name.split(' ', 1)
                    fname = name_parts[0] if len(name_parts) > 0 else 'User'
                    lname = name_parts[1] if len(name_parts) > 1 else ''
                else:
                    fname = 'User'
                    lname = ''
                
                # Create Farmer profile
                farmer = Farmer.objects.create(
                    fname=fname,
                    lname=lname,
                    email=user.email
                )
                logger.info(f"✓ Farmer profile created for {user.email}: {farmer.fname} {farmer.lname}")
                
            except Exception as e:
                logger.error(f"✗ Error creating Farmer profile for {user.email}: {str(e)}")
                # Don't block login if Farmer creation fails
                pass
    
    def save_user(self, request, sociallogin, form=None):
        """
        Save user data from social provider.
        Override to customize user creation.
        """
        user = super().save_user(request, sociallogin, form)
        
        # Extract additional data from Google if available
        extra_data = sociallogin.account.extra_data
        
        # Mark email as verified since it comes from Google
        user.email_verified = True
        user.save()
        
        logger.info(f"✓ User created/updated from Google: {user.email}")
        return user
