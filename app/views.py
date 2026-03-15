from django.shortcuts import render, redirect, get_object_or_404
from django.views.generic import ListView, DetailView
from django.contrib import messages
from django.http import JsonResponse
from django.contrib.auth import authenticate, login, logout, get_user_model
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from datetime import timedelta
import random
import logging
import uuid

from .models import Farmer, Farm, ChatThread, Notification
from .utils import chat_with_advisor, reverse_geocode_coordinates
from .forms import CustomUserCreationForm, CustomAuthenticationForm, FarmerProfileForm, FarmRegistrationForm, EmailVerificationForm, PhoneAuthenticationForm, PhoneVerificationForm
from .email_service import send_verification_email
from .sms_service import send_verification_sms

logger = logging.getLogger(__name__)
CustomUser = get_user_model()

@login_required(login_url='auth')
def dashboard(request):
    # Get farmer profile and farms
    farmer = Farmer.objects.filter(email=request.user.email).first()
    farms = Farm.objects.filter(farmer=farmer) if farmer else []
    
    return render(request, 'dashboard/dashboard.html', {
        'farmer': farmer,
        'farms': farms,
    })

def index_redirect(request):
    """
    Redirect the root URL (/) to /dashboard/.
    """
    return redirect('dashboard')

def auth_view(request):
    """
    Handles both login and sign-up using email and password.
    Displays appropriate forms and error messages.
    """
    login_form = CustomAuthenticationForm()
    signup_form = CustomUserCreationForm()
    
    if request.method == 'POST':
        action = request.POST.get('action')
        logger.info(f"[{action.upper()}] Form submission received")
        
        if action == 'login':
            login_form = CustomAuthenticationForm(data=request.POST)
            if login_form.is_valid():
                email = login_form.cleaned_data["username"]
                password = login_form.cleaned_data["password"]
                # Authenticate using the custom backend
                user = authenticate(request, username=email, password=password)
                if user is not None:
                    login(request, user)
                    logger.info(f"✓ Login successful for {user.email}")
                    messages.success(request, f"Welcome back, {user.email}!")
                    return redirect('dashboard')
                else:
                    logger.warning(f"✗ Authentication failed for {email}")
                    messages.error(request, "Invalid email or password. Please try again.")
                    login_form.add_error(None, "Invalid email or password.")
            else:
                logger.error(f"Login form errors: {login_form.errors}")
                # Add form errors as messages for display
                if login_form.errors:
                    for field, errors in login_form.errors.items():
                        for error in errors:
                            if field == '__all__':
                                messages.error(request, str(error))
                            else:
                                messages.error(request, f"{field.replace('_', ' ').title()}: {error}")
            
        elif action == 'signup':
            logger.info("=== SIGNUP ATTEMPT ===")
            signup_form = CustomUserCreationForm(request.POST)
            logger.info(f"Form valid: {signup_form.is_valid()}")
            
            if not signup_form.is_valid():
                logger.error(f"Form errors: {signup_form.errors}")
                # Add form errors as messages for display
                if signup_form.errors:
                    for field, errors in signup_form.errors.items():
                        for error in errors:
                            if field == '__all__':
                                messages.error(request, str(error))
                            else:
                                messages.error(request, f"{field.replace('_', ' ').title()}: {error}")
            
            if signup_form.is_valid():
                try:
                    new_user = signup_form.save()
                    logger.info(f"✓ User created: {new_user.email} (ID: {new_user.id})")
                    
                    # Generate 6-digit verification code
                    verification_code = ''.join([str(random.randint(0, 9)) for _ in range(6)])
                    new_user.email_verification_code = verification_code
                    new_user.verification_code_expires_at = timezone.now() + timedelta(minutes=10)
                    new_user.save()
                    
                    logger.info(f"Generated verification code for {new_user.email}: {verification_code}")
                    
                    # Store password in session for later auto-login after verification
                    request.session['signup_password'] = request.POST.get('password1')
                    request.session['signup_email'] = new_user.email
                    
                    # Send verification email
                    email_sent = send_verification_email(new_user.email, verification_code)
                    
                    if email_sent:
                        logger.info(f"✓ Verification email sent to {new_user.email}")
                        messages.success(request, "Account created! Please check your email to verify your account.")
                        # Redirect to email verification page
                        return redirect('verify_email')
                    else:
                        logger.error(f"✗ Failed to send verification email to {new_user.email}")
                        messages.error(request, "Account created but we couldn't send the verification email. Please contact support.")
                        # Still allow access to verification page to retry
                        return redirect('verify_email')
                
                except Exception as e:
                    logger.exception(f"Exception during signup: {str(e)}")
                    messages.error(request, f"An error occurred during sign up: {str(e)}")
    
    return render(request, 'auth.html', {
        'login_form': login_form,
        'signup_form': signup_form
    })

def verify_email(request):
    """
    Handles email verification during signup.
    Users enter the 6-digit code sent to their email to verify their account.
    Automatically sends the verification email on first page load if needed.
    Also handles login flow where user needs to verify email after logging in.
    """
    # Get the user being verified from session or database
    signup_email = request.session.get('signup_email')
    is_signup_flow = False
    
    if signup_email:
        # User is currently in signup flow
        user = CustomUser.objects.filter(email=signup_email, email_verified=False).first()
        is_signup_flow = True
    else:
        # User might be accessing from authenticated session (middleware redirected them)
        if request.user.is_authenticated and not request.user.email_verified:
            user = request.user
            is_signup_flow = False
        else:
            # No pending verification found
            messages.error(request, "No pending verification found. Please sign up first.")
            return redirect('auth')
    
    if not user:
        messages.error(request, "No pending verification found. Please sign up first.")
        return redirect('auth')
    
    # Check if verification code has expired or is missing
    if not user.is_verification_code_valid():
        # If this is a login flow (user logged in but email not verified), regenerate code
        if not is_signup_flow and request.user.is_authenticated:
            logger.info(f"Regenerating verification code for logged-in user {user.email}")
            verification_code = ''.join([str(random.randint(0, 9)) for _ in range(6)])
            user.email_verification_code = verification_code
            user.verification_code_expires_at = timezone.now() + timedelta(minutes=10)
            user.save()
            # Clear the session flag so email gets sent
            request.session.pop('verification_email_sent', None)
        else:
            # This is signup flow with expired code
            messages.error(request, "Your verification code has expired. Please sign up again.")
            user.email_verification_code = None
            user.verification_code_expires_at = None
            user.save()
            return redirect('auth')
    
    # AUTO-SEND VERIFICATION EMAIL on first GET request (if not already sent or as fallback)
    if request.method == 'GET' and not request.session.get('verification_email_sent'):
        email_sent = send_verification_email(user.email, user.email_verification_code)
        if email_sent:
            logger.info(f"✓ Verification email sent on page load to {user.email}")
            request.session['verification_email_sent'] = True
        else:
            logger.error(f"✗ Failed to send verification email on page load to {user.email}")
    
    form = EmailVerificationForm()
    
    if request.method == 'POST':
        form = EmailVerificationForm(request.POST)
        if form.is_valid():
            entered_code = form.cleaned_data.get('verification_code')
            
            if entered_code == user.email_verification_code:
                # Mark email as verified
                user.email_verified = True
                user.email_verification_code = None
                user.verification_code_expires_at = None
                user.save()
                
                logger.info(f"✓ Email verified for {user.email}")
                messages.success(request, "Email verified successfully!")
                
                # Auto-login the user after verification using password from session
                password = request.session.get('signup_password')
                
                if password:
                    authenticated_user = authenticate(request, username=user.email, password=password)
                    if authenticated_user is not None:
                        logger.info(f"✓ Auto-login successful after email verification for {user.email}")
                        login(request, authenticated_user)
                        # Clean up session
                        request.session.pop('signup_password', None)
                        request.session.pop('signup_email', None)
                        request.session.pop('verification_email_sent', None)
                        messages.success(request, "Welcome! Let's set up your farm profile.")
                        return redirect('farmer_registration')
                
                # If auto-login with saved password fails, redirect to login
                messages.info(request, "Please log in with your credentials.")
                return redirect('auth')
            else:
                messages.error(request, "Invalid verification code. Please try again.")
                logger.warning(f"Invalid verification code attempt for {user.email}")
                form.add_error('verification_code', 'Code does not match. Please check and try again.')
    
    context = {
        'form': form,
        'email': user.email,
        'resend_info': f'A verification code has been sent to {user.email}'
    }
    
    return render(request, 'verify_email.html', context)

def resend_verification_email(request):
    """
    Resend the verification email if the user didn't receive the first one.
    """
    if request.method != 'POST':
        return redirect('verify_email')
    
    # Get the user being verified from session or authenticated user
    signup_email = request.session.get('signup_email')
    
    if signup_email:
        user = CustomUser.objects.filter(email=signup_email, email_verified=False).first()
    else:
        if request.user.is_authenticated and not request.user.email_verified:
            user = request.user
        else:
            messages.error(request, "No pending verification found.")
            return redirect('auth')
    
    if not user:
        messages.error(request, "No pending verification found.")
        return redirect('auth')
    
    # Regenerate verification code
    verification_code = ''.join([str(random.randint(0, 9)) for _ in range(6)])
    user.email_verification_code = verification_code
    user.verification_code_expires_at = timezone.now() + timedelta(minutes=10)
    user.save()
    
    logger.info(f"Regenerated verification code for {user.email}: {verification_code}")
    
    # Send verification email
    email_sent = send_verification_email(user.email, verification_code)
    
    if email_sent:
        logger.info(f"✓ Verification email resent to {user.email}")
        messages.success(request, "Verification code resent! Check your email.")
    else:
        logger.error(f"✗ Failed to resend verification email to {user.email}")
        messages.error(request, "Failed to resend verification email. Please try again.")
    
    return redirect('verify_email')

def phone_auth(request):
    """
    Handles phone-based authentication (login/signup).
    Users enter their phone number and receive a 6-digit code via SMS.
    """
    form = PhoneAuthenticationForm()
    
    if request.method == 'POST':
        form = PhoneAuthenticationForm(request.POST)
        if form.is_valid():
            phone = form.cleaned_data.get('phone')
            logger.info(f"[PHONE AUTH] Form submission for phone: {phone}")
            
            # Normalize phone number - store as international format
            phone_normalized = phone.replace(' ', '')
            if phone_normalized.startswith('0'):
                phone_normalized = '+254' + phone_normalized[1:]
            elif not phone_normalized.startswith('+'):
                if phone_normalized.startswith('254'):
                    phone_normalized = '+' + phone_normalized
                else:
                    phone_normalized = '+254' + phone_normalized
            
            logger.info(f"Normalized phone: {phone_normalized}")
            
            # Check if user exists with this phone number
            user = CustomUser.objects.filter(phone=phone_normalized).first()
            
            if user:
                # User exists - this is a login flow
                logger.info(f"✓ User found with phone {phone_normalized}")
                
                # Ensure phone users have email_verified=True (in case of older accounts)
                if not user.email_verified:
                    user.email_verified = True
                    user.save()
                
                # Generate 6-digit verification code
                verification_code = ''.join([str(random.randint(0, 9)) for _ in range(6)])
                user.phone_verification_code = verification_code
                user.phone_verification_code_expires_at = timezone.now() + timedelta(minutes=10)
                user.save()
                
                logger.info(f"Generated phone verification code for {phone_normalized}: {verification_code}")
                
                # Store phone in session for verification page
                request.session['auth_phone'] = phone_normalized
                
                # Send verification SMS
                sms_sent = send_verification_sms(phone_normalized, verification_code)
                
                if sms_sent:
                    logger.info(f"✓ Verification SMS sent to {phone_normalized}")
                    messages.success(request, f"Verification code sent to {phone_normalized}!")
                    return redirect('verify_phone')
                else:
                    logger.error(f"✗ Failed to send verification SMS to {phone_normalized}")
                    messages.error(request, "Failed to send verification code. Please try again.")
            else:
                # User doesn't exist - create new account for signup
                logger.info(f"No user found with phone {phone_normalized}, creating new account")
                try:
                    # For phone-only signup, use UUID as email (it's just a placeholder)
                    # phone users won't use email for login
                    unique_email = f"phone-{uuid.uuid4()}@crpas.local"
                    
                    new_user = CustomUser.objects.create_user(
                        email=unique_email,
                        phone=phone_normalized,
                        password=None  # Phone auth doesn't use password initially
                    )
                    
                    # Mark email as verified since phone users don't use email
                    # This prevents middleware from redirecting them to email verification
                    new_user.email_verified = True
                    new_user.save()  # Save immediately to persist email_verified flag
                    
                    logger.info(f"✓ New user created for phone {phone_normalized}")
                    
                    # Generate 6-digit verification code
                    verification_code = ''.join([str(random.randint(0, 9)) for _ in range(6)])
                    new_user.phone_verification_code = verification_code
                    new_user.phone_verification_code_expires_at = timezone.now() + timedelta(minutes=10)
                    new_user.save()
                    
                    logger.info(f"Generated phone verification code for {phone_normalized}: {verification_code}")
                    
                    # Store phone in session for verification page
                    request.session['auth_phone'] = phone_normalized
                    request.session['is_phone_signup'] = True
                    
                    # Send verification SMS
                    sms_sent = send_verification_sms(phone_normalized, verification_code)
                    
                    if sms_sent:
                        logger.info(f"✓ Verification SMS sent to {phone_normalized}")
                        messages.success(request, f"Verification code sent to {phone_normalized}!")
                        return redirect('verify_phone')
                    else:
                        logger.error(f"✗ Failed to send verification SMS to {phone_normalized}")
                        messages.error(request, "Failed to send verification code. Please try again.")
                        # Clean up the user we just created
                        new_user.delete()
                        return redirect('phone_auth')
                        
                except Exception as e:
                    logger.exception(f"Exception during phone signup: {str(e)}")
                    messages.error(request, f"An error occurred: {str(e)}")
    
    return render(request, 'phone_auth.html', {'form': form})

def verify_phone(request):
    """
    Handles phone verification during phone-based signup/login.
    Users enter the 6-digit code sent to their phone to verify their account.
    Automatically sends the verification SMS on first page load if needed.
    """
    # Get the user being verified from session or database
    auth_phone = request.session.get('auth_phone')
    is_phone_signup = request.session.get('is_phone_signup', False)
    
    if not auth_phone:
        messages.error(request, "No pending phone verification found. Please start over.")
        return redirect('phone_auth')
    
    # Get user by phone number
    user = CustomUser.objects.filter(phone=auth_phone).first()
    
    if not user:
        messages.error(request, "User not found. Please start over.")
        return redirect('phone_auth')
    
    # Check if verification code has expired or is missing
    if not user.is_phone_verification_code_valid():
        messages.error(request, "Your verification code has expired. Please request a new one.")
        # Clear session
        request.session.pop('auth_phone', None)
        request.session.pop('is_phone_signup', None)
        return redirect('phone_auth')
    
    # AUTO-SEND VERIFICATION SMS on first GET request (if not already sent or as fallback)
    if request.method == 'GET' and not request.session.get('verification_sms_sent'):
        sms_sent = send_verification_sms(user.phone, user.phone_verification_code)
        if sms_sent:
            logger.info(f"✓ Verification SMS sent on page load to {user.phone}")
            request.session['verification_sms_sent'] = True
        else:
            logger.error(f"✗ Failed to send verification SMS on page load to {user.phone}")
    
    form = PhoneVerificationForm()
    
    if request.method == 'POST':
        form = PhoneVerificationForm(request.POST)
        if form.is_valid():
            entered_code = form.cleaned_data.get('verification_code')
            
            if entered_code == user.phone_verification_code:
                # Mark phone as verified
                user.phone_verified = True
                user.phone_verification_code = None
                user.phone_verification_code_expires_at = None
                user.save()
                
                logger.info(f"✓ Phone verified for {user.phone}")
                messages.success(request, "Phone verified successfully!")
                
                if is_phone_signup:
                    # This is a signup flow - redirect to set password
                    request.session.pop('is_phone_signup', None)
                    request.session.pop('verification_sms_sent', None)
                    return redirect('phone_signup_password')
                else:
                    # This is a login flow - log the user in
                    user.backend = 'app.backends.EmailBackend'
                    login(request, user)
                    request.session.pop('auth_phone', None)
                    request.session.pop('verification_sms_sent', None)
                    logger.info(f"✓ Login successful for {user.phone}")
                    messages.success(request, "Logged in successfully!")
                    return redirect('dashboard')
            else:
                messages.error(request, "Invalid verification code. Please try again.")
                logger.warning(f"Invalid phone verification code attempt for {user.phone}")
                form.add_error('verification_code', 'Code does not match. Please check and try again.')
    
    context = {
        'form': form,
        'phone': user.phone,
        'resend_info': f'A verification code has been sent to {user.phone}'
    }
    
    return render(request, 'verify_phone.html', context)

def resend_verification_sms(request):
    """
    Resend the verification SMS if the user didn't receive the first one.
    """
    if request.method != 'POST':
        return redirect('verify_phone')
    
    # Get the phone being verified from session
    auth_phone = request.session.get('auth_phone')
    
    if not auth_phone:
        messages.error(request, "No pending phone verification found.")
        return redirect('phone_auth')
    
    # Get user by phone
    user = CustomUser.objects.filter(phone=auth_phone).first()
    
    if not user:
        messages.error(request, "User not found.")
        return redirect('phone_auth')
    
    # Regenerate verification code
    verification_code = ''.join([str(random.randint(0, 9)) for _ in range(6)])
    user.phone_verification_code = verification_code
    user.phone_verification_code_expires_at = timezone.now() + timedelta(minutes=10)
    user.save()
    
    logger.info(f"Regenerated phone verification code for {user.phone}: {verification_code}")
    
    # Send verification SMS
    sms_sent = send_verification_sms(user.phone, verification_code)
    
    if sms_sent:
        logger.info(f"✓ Verification SMS resent to {user.phone}")
        messages.success(request, "Verification code resent! Check your phone.")
    else:
        logger.error(f"✗ Failed to resend verification SMS to {user.phone}")
        messages.error(request, "Failed to resend verification code. Please try again.")
    
    return redirect('verify_phone')

def phone_signup_password(request):
    """
    Allow newly signed-up phone users to set their password.
    Phone users can later optionally add an email if they want email-based login.
    """
    auth_phone = request.session.get('auth_phone')
    
    if not auth_phone:
        messages.error(request, "Session expired. Please sign up again.")
        return redirect('phone_auth')
    
    user = CustomUser.objects.filter(phone=auth_phone).first()
    
    if not user or not user.phone_verified:
        messages.error(request, "Invalid session. Please sign up again.")
        return redirect('phone_auth')
    
    if request.method == 'POST':
        password1 = request.POST.get('password1')
        password2 = request.POST.get('password2')
        
        if not password1 or not password2:
            messages.error(request, "Please enter a password.")
        elif len(password1) < 8:
            messages.error(request, "Password must be at least 8 characters long.")
        elif password1 != password2:
            messages.error(request, "Passwords do not match.")
        else:
            user.set_password(password1)
            user.save()
            
            logger.info(f"✓ Password set for phone signup user {user.phone}")
            messages.success(request, "Password set successfully!")
            
            # Log the user in - specify the backend since multiple are configured
            user.backend = 'app.backends.EmailBackend'
            login(request, user)
            
            # Clean up session
            request.session.pop('auth_phone', None)
            
            return redirect('farmer_registration')
    
    return render(request, 'phone_signup_password.html', {'phone': user.phone})

def logout_view(request):
    """
    Handles user logout.
    """
    logout(request)
    messages.success(request, "You have been logged out successfully.")
    return redirect('auth')

@login_required(login_url='auth')
@login_required(login_url='auth')
def farmer_registration(request):
    """
    Step 1: Handle farmer profile registration/editing.
    Creates or updates the Farmer profile with personal details (fname, lname, phone, email).
    After completion, redirects to farm_registration for farm details.
    """
    # Get or create farmer profile for the logged-in user
    farmer = Farmer.objects.filter(email=request.user.email).first()
    
    if request.method == 'POST':
        form = FarmerProfileForm(request.POST, instance=farmer)
        if form.is_valid():
            farmer = form.save(commit=False)
            # Ensure email matches the logged-in user
            farmer.email = request.user.email
            farmer.save()
            messages.success(request, "Your profile has been saved successfully!")
            return redirect('farm_registration')
    else:
        # Prefill the form with logged-in user's email
        initial_data = {
            'email': request.user.email,
        }
        form = FarmerProfileForm(instance=farmer, initial=initial_data)
    
    return render(request, 'registration.html', {
        'form': form,
        'step': 'farmer',
        'title': 'Farmer Profile Registration'
    })


@login_required(login_url='auth')
def farm_registration(request):
    """
    Step 2: Handle farm registration/editing.
    Creates or updates a Farm profile with farm details (crop_type, farm_size, location, etc.).
    Only accessible after farmer profile is completed.
    """
    # Verify farmer profile exists
    farmer = Farmer.objects.filter(email=request.user.email).first()
    if not farmer:
        messages.error(request, "Please complete your farmer profile first.")
        return redirect('farmer_registration')
    
    # Check if this is an edit (farm_id parameter) or new registration
    farm_id = request.GET.get('farm_id')
    farm = None
    if farm_id:
        farm = farmer.farms.filter(id=farm_id).first()
        if not farm:
            messages.error(request, "Farm not found.")
            return redirect('farm_registration')
    
    if request.method == 'POST':
        # Try to reverse geocode the coordinates if both are provided
        lat = request.POST.get('lat')
        lon = request.POST.get('long')
        
        post_data = request.POST.copy()
        
        if lat and lon:
            try:
                lat = float(lat)
                lon = float(lon)
                geocoded = reverse_geocode_coordinates(lat, lon)
                
                if geocoded:
                    # Auto-fill the administrative divisions from geocoding
                    if geocoded.get('county') and not post_data.get('county'):
                        post_data['county'] = geocoded['county']
                    if geocoded.get('sub_county') and not post_data.get('sub_county'):
                        post_data['sub_county'] = geocoded['sub_county']
                    if geocoded.get('ward') and not post_data.get('ward'):
                        post_data['ward'] = geocoded['ward']
                    
                    logger.info(f"Reverse geocoded ({lat}, {lon}) → {geocoded}")
            except (ValueError, TypeError) as e:
                logger.warning(f"Could not parse GPS coordinates: {str(e)}")
        
        form = FarmRegistrationForm(post_data, instance=farm)
        if form.is_valid():
            new_farm = form.save(commit=False)
            new_farm.farmer = farmer
            new_farm.save()
            messages.success(request, "Your farm details have been saved successfully!")
            return redirect('dashboard')
    else:
        form = FarmRegistrationForm(instance=farm)
    
    return render(request, 'farm_registration.html', {
        'form': form,
        'farmer': farmer,
        'farm': farm,
        'step': 'farm',
        'title': 'Farm Details Registration',
        'is_edit': farm is not None
    })


@login_required(login_url='auth')
def edit_farm_details(request, farm_id):
    """
    Edit an existing farm's details.
    Only accessible to the farmer who owns the farm.
    """
    farmer = Farmer.objects.filter(email=request.user.email).first()
    if not farmer:
        messages.error(request, "Please complete your farmer profile first.")
        return redirect('farmer_registration')
    
    farm = farmer.farms.filter(id=farm_id).first()
    if not farm:
        messages.error(request, "Farm not found.")
        return redirect('dashboard')
    
    if request.method == 'POST':
        # Try to reverse geocode the coordinates if both are provided
        lat = request.POST.get('lat')
        lon = request.POST.get('long')
        
        post_data = request.POST.copy()
        
        if lat and lon:
            try:
                lat = float(lat)
                lon = float(lon)
                geocoded = reverse_geocode_coordinates(lat, lon)
                
                if geocoded:
                    # Auto-fill the administrative divisions from geocoding
                    if geocoded.get('county') and not post_data.get('county'):
                        post_data['county'] = geocoded['county']
                    if geocoded.get('sub_county') and not post_data.get('sub_county'):
                        post_data['sub_county'] = geocoded['sub_county']
                    if geocoded.get('ward') and not post_data.get('ward'):
                        post_data['ward'] = geocoded['ward']
                    
                    logger.info(f"Reverse geocoded ({lat}, {lon}) → {geocoded}")
            except (ValueError, TypeError) as e:
                logger.warning(f"Could not parse GPS coordinates: {str(e)}")
        
        form = FarmRegistrationForm(post_data, instance=farm)
        if form.is_valid():
            form.save()
            messages.success(request, "Farm details updated successfully!")
            return redirect('dashboard')
    else:
        form = FarmRegistrationForm(instance=farm)
    
    return render(request, 'edit_farm_details.html', {
        'form': form,
        'farmer': farmer,
        'farm': farm,
        'title': 'Edit Farm Details'
    })


def reverse_geocode_api(request):
    """
    AJAX endpoint to reverse geocode GPS coordinates.
    Accepts GET parameters: lat and lon
    Returns JSON with county, sub_county, and ward
    """
    from .utils import reverse_geocode_coordinates
    
    if request.method != 'GET':
        return JsonResponse({'error': 'Only GET requests allowed'}, status=400)
    
    try:
        lat = float(request.GET.get('lat', ''))
        lon = float(request.GET.get('lon', ''))
    except (ValueError, TypeError):
        return JsonResponse({'error': 'Invalid latitude or longitude'}, status=400)
    
    # Call the reverse geocoding function
    result = reverse_geocode_coordinates(lat, lon)
    
    if result:
        return JsonResponse({
            'status': 'success',
            'data': result
        })
    else:
        return JsonResponse({
            'status': 'error',
            'message': 'Could not geocode coordinates. Please enter location manually.'
        }, status=400)

# @login_required(login_url='auth')
def conversation_view(request):
    """
    Conversation page where the farmer can chat with an agricultural advisor.
    The advisor can answer questions about farming, crops, and advisory.
    Supports loading a specific chat thread via ?thread_id parameter.
    Allows selecting from farmer's farms via ?farm_id parameter.
    """
    # Get farmer profile for the logged-in user (same as dashboard)
    farmer = Farmer.objects.filter(email=request.user.email).first()
    
    if not farmer:
        messages.error(request, "Please complete your farmer registration first.")
        return redirect('farmer_registration')
    
    # Get farmer's farms
    farms = farmer.farms.all()
    if not farms.exists():
        messages.error(request, "Please register at least one farm first.")
        return redirect('farm_registration')
    
    # Get the selected farm - either from query param or the first farm (default)
    farm_id = request.GET.get('farm_id')
    if farm_id:
        farm = farms.filter(id=farm_id).first()
        if not farm:
            messages.error(request, "Farm not found.")
            return redirect('conversation')
    else:
        # Default to the first farm
        farm = farms.first()
    
    # Get the chat thread - either from query param or the most recent one for this farm
    thread_id = request.GET.get('thread_id')
    if thread_id:
        # Load specific thread (for this farm)
        chat_thread = farm.chat_threads.filter(id=thread_id).first()
        if not chat_thread:
            messages.error(request, "Chat thread not found.")
            return redirect('conversation')
    else:
        # Get the most recent thread for this farm
        chat_thread = farm.chat_threads.order_by('-updated_at').first()
        if not chat_thread:
            # If no chat threads exist for this farm, create one
            chat_thread = ChatThread.objects.create(
                farmer=farmer,
                farm=farm,
                title='New chat',
                history=[]
            )
    
    # Handle AJAX requests for new messages
    if request.method == 'POST' and request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        user_message = request.POST.get('message', '').strip()
        
        if not user_message:
            return JsonResponse({'error': 'Message cannot be empty'}, status=400)
        
        # Get the advisor response
        advisor_response = chat_with_advisor(farm, chat_thread, user_message)
        
        # Return the response as JSON
        return JsonResponse({
            'status': 'success',
            'user_message': user_message,
            'advisor_response': advisor_response
        })
    
    # GET request - display conversation page
    # Fetch all chat threads for this farm
    chat_threads = farm.chat_threads.all().order_by('-updated_at')
    
    # Filter out system messages for display (only show user and assistant messages)
    conversation_history = [
        msg for msg in (chat_thread.history or [])
        if msg.get('role') != 'system'
    ]
    
    context = {
        'farmer': farmer,
        'farm': farm,
        'farms': farms,
        'conversation_history': conversation_history,
        'chat_threads': chat_threads,
        'active_thread_id': chat_thread.id,
    }
    
    return render(request, 'dashboard/conversation.html', context)

@login_required(login_url='auth')
def new_chat_view(request):
    """
    Create a new chat thread for the logged-in farmer.
    """
    try:
        farmer = Farmer.objects.filter(phone=request.user.email).first() or Farmer.objects.first()
    except Farmer.DoesNotExist:
        messages.error(request, "Please complete your farmer registration first.")
        return redirect('farmer_registration')
    
    if not farmer:
        messages.error(request, "Please complete your farmer registration first.")
        return redirect('farmer_registration')
    
    # Create a new chat thread
    chat_thread = ChatThread.objects.create(
        farmer=farmer,
        title='New chat',
        history=[]
    )
    
    return redirect('conversation')

@login_required(login_url='auth')
def delete_chat_view(request, thread_id):
    """
    Delete a chat thread for the logged-in farmer.
    Handles both AJAX and regular POST requests.
    """
    try:
        farmer = Farmer.objects.filter(phone=request.user.email).first() or Farmer.objects.first()
    except Farmer.DoesNotExist:
        messages.error(request, "Please complete your farmer registration first.")
        return redirect('farmer_registration')
    
    if not farmer:
        messages.error(request, "Please complete your farmer registration first.")
        return redirect('farmer_registration')
    
    # Get the chat thread and verify it belongs to the farmer
    chat_thread = farmer.chat_threads.filter(id=thread_id).first()
    if not chat_thread:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'status': 'error', 'message': 'Chat thread not found'}, status=404)
        messages.error(request, "Chat thread not found.")
        return redirect('conversation')
    
    # Delete the chat thread
    chat_thread.delete()
    
    # Handle AJAX requests
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({'status': 'success', 'message': 'Chat deleted successfully'})
    
    # Redirect to conversation page (loads the most recent remaining chat or creates a new one)
    return redirect('conversation')


# ============================================================================
# NOTIFICATION ENDPOINTS
# ============================================================================

@login_required(login_url='auth')
def get_notifications(request):
    """
    Get all notifications for the logged-in farmer.
    Supports filtering by status (read/unread) via query parameter.
    Returns JSON with list of notifications.
    """
    try:
        farmer = Farmer.objects.filter(email=request.user.email).first()
        if not farmer:
            return JsonResponse({'error': 'Farmer profile not found'}, status=404)
    except Farmer.DoesNotExist:
        return JsonResponse({'error': 'Farmer profile not found'}, status=404)
    
    # Get filter parameter (unread, read, all)
    status_filter = request.GET.get('status', 'unread')  # default to unread
    
    # Get notifications
    notifications_query = farmer.notifications.all()
    
    if status_filter == 'unread':
        notifications_query = notifications_query.filter(status='unread')
    elif status_filter == 'read':
        notifications_query = notifications_query.filter(status='read')
    
    notifications = notifications_query.order_by('-created_at')
    
    # Serialize notifications
    notifications_data = []
    for notif in notifications:
        notifications_data.append({
            'id': notif.id,
            'title': notif.title,
            'message': notif.message,
            'type': notif.notification_type,
            'status': notif.status,
            'created_at': notif.created_at.isoformat(),
            'read_at': notif.read_at.isoformat() if notif.read_at else None,
            'sent_via': {
                'website': notif.sent_via_website,
                'email': notif.sent_via_email,
                'sms': notif.sent_via_sms,
            }
        })
    
    return JsonResponse({
        'status': 'success',
        'count': notifications_query.count(),
        'unread_count': farmer.notifications.filter(status='unread').count(),
        'notifications': notifications_data
    })


@login_required(login_url='auth')
def mark_notification_as_read(request, notification_id):
    """
    Mark a notification as read.
    """
    from django.utils import timezone
    
    if request.method != 'POST':
        return JsonResponse({'error': 'Only POST requests allowed'}, status=400)
    
    try:
        farmer = Farmer.objects.filter(email=request.user.email).first()
        if not farmer:
            return JsonResponse({'error': 'Farmer profile not found'}, status=404)
    except Farmer.DoesNotExist:
        return JsonResponse({'error': 'Farmer profile not found'}, status=404)
    
    try:
        notification = farmer.notifications.get(id=notification_id)
        notification.status = 'read'
        notification.read_at = timezone.now()
        notification.save()
        
        return JsonResponse({
            'status': 'success',
            'message': 'Notification marked as read',
            'notification_id': notification_id
        })
    except Notification.DoesNotExist:
        return JsonResponse({'error': 'Notification not found'}, status=404)


@login_required(login_url='auth')
def delete_notification(request, notification_id):
    """
    Delete a notification.
    """
    if request.method != 'POST':
        return JsonResponse({'error': 'Only POST requests allowed'}, status=400)
    
    try:
        farmer = Farmer.objects.filter(email=request.user.email).first()
        if not farmer:
            return JsonResponse({'error': 'Farmer profile not found'}, status=404)
    except Farmer.DoesNotExist:
        return JsonResponse({'error': 'Farmer profile not found'}, status=404)
    
    try:
        notification = farmer.notifications.get(id=notification_id)
        notification.delete()
        
        return JsonResponse({
            'status': 'success',
            'message': 'Notification deleted',
            'notification_id': notification_id
        })
    except Notification.DoesNotExist:
        return JsonResponse({'error': 'Notification not found'}, status=404)


@login_required(login_url='auth')
def get_notification_preferences(request):
    """
    Get the notification preferences for the logged-in farmer.
    """
    from .models import NotificationPreference
    
    try:
        farmer = Farmer.objects.filter(email=request.user.email).first()
        if not farmer:
            return JsonResponse({'error': 'Farmer profile not found'}, status=404)
    except Farmer.DoesNotExist:
        return JsonResponse({'error': 'Farmer profile not found'}, status=404)
    
    try:
        prefs = farmer.notification_preference
    except NotificationPreference.DoesNotExist:
        # Create default preferences if they don't exist
        prefs = NotificationPreference.objects.create(farmer=farmer)
    
    return JsonResponse({
        'status': 'success',
        'preferences': {
            'notify_via_website': prefs.notify_via_website,
            'notify_via_email': prefs.notify_via_email,
            'notify_via_sms': prefs.notify_via_sms,
        }
    })


@login_required(login_url='auth')
def update_notification_preferences(request):
    """
    Update the notification preferences for the logged-in farmer.
    """
    from .models import NotificationPreference
    
    if request.method != 'POST':
        return JsonResponse({'error': 'Only POST requests allowed'}, status=400)
    
    try:
        farmer = Farmer.objects.filter(email=request.user.email).first()
        if not farmer:
            return JsonResponse({'error': 'Farmer profile not found'}, status=404)
    except Farmer.DoesNotExist:
        return JsonResponse({'error': 'Farmer profile not found'}, status=404)
    
    try:
        import json
        data = json.loads(request.body)
        
        prefs, _ = NotificationPreference.objects.get_or_create(farmer=farmer)
        
        if 'notify_via_website' in data:
            prefs.notify_via_website = data['notify_via_website']
        if 'notify_via_email' in data:
            prefs.notify_via_email = data['notify_via_email']
        if 'notify_via_sms' in data:
            prefs.notify_via_sms = data['notify_via_sms']
        
        prefs.save()
        
        return JsonResponse({
            'status': 'success',
            'message': 'Preferences updated',
            'preferences': {
                'notify_via_website': prefs.notify_via_website,
                'notify_via_email': prefs.notify_via_email,
                'notify_via_sms': prefs.notify_via_sms,
            }
        })
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)