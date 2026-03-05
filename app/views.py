from django.shortcuts import render, redirect, get_object_or_404
from django.views.generic import ListView, DetailView
from django.contrib import messages
from django.http import JsonResponse
from .models import Farmer, ChatThread, Notification
from .utils import get_rainfall_forecast, get_soil_data, generate_advisory, chat_with_advisor
from .forms import CustomUserCreationForm, CustomAuthenticationForm, FarmerRegistrationForm
from django.contrib.auth import authenticate, login, logout, get_user_model
from django.contrib.auth.decorators import login_required
import logging

logger = logging.getLogger(__name__)
CustomUser = get_user_model()

@login_required(login_url='auth')
def dashboard(request):
    return render(request, 'dashboard/dashboard.html')

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
                    
                    # Auto-login the user after signup
                    email = new_user.email
                    password = request.POST.get('password1')
                    logger.info(f"Attempting authentication with email={email}")
                    
                    user = authenticate(request, username=email, password=password)
                    logger.info(f"Authentication result: {user}")
                    
                    if user is not None:
                        logger.info(f"✓ Authentication successful for {user.email}")
                        login(request, user)
                        messages.success(request, "Account created successfully! Now let's set up your farm profile.")
                        logger.info("Redirecting to farmer registration")
                        return redirect('farmer_registration')
                    else:
                        logger.error(f"✗ Authentication failed for {email}")
                        messages.error(request, "Account created but automatic login failed. Please log in with your credentials.")
                except Exception as e:
                    logger.exception(f"Exception during signup: {str(e)}")
                    messages.error(request, f"An error occurred during sign up: {str(e)}")
    
    return render(request, 'auth.html', {
        'login_form': login_form,
        'signup_form': signup_form
    })

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
    Handle farmer registration where users add plot and contact information.
    Prefills email from request.user.
    Auto-fills county, sub_county, and ward from GPS coordinates using reverse geocoding.
    """
    from .utils import reverse_geocode_coordinates
    
    # Check if farmer already has a profile linked to the logged-in user's email
    # Use filter().first() to avoid MultipleObjectsReturned if multiple farmers exist with same email
    farmer = Farmer.objects.filter(email=request.user.email).first() if request.user.is_authenticated else None
    
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
        
        form = FarmerRegistrationForm(post_data, instance=farmer)
        if form.is_valid():
            farmer = form.save()
            messages.success(request, "Your farm details have been saved successfully!")
            return redirect('dashboard')
    else:
        # Prefill the form with logged-in user's email
        initial_data = {
            'email': request.user.email,
        }
        form = FarmerRegistrationForm(initial=initial_data)
    
    return render(request, 'registration.html', {'form': form})


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
    """
    # Get or create farmer profile for the logged-in user
    try:
        farmer = Farmer.objects.filter(phone=request.user.email).first() or Farmer.objects.first()
    except Farmer.DoesNotExist:
        messages.error(request, "Please complete your farmer registration first.")
        return redirect('farmer_registration')
    
    if not farmer:
        messages.error(request, "Please complete your farmer registration first.")
        return redirect('farmer_registration')
    
    # Get the chat thread - either from query param or the most recent one
    thread_id = request.GET.get('thread_id')
    if thread_id:
        # Load specific thread
        chat_thread = farmer.chat_threads.filter(id=thread_id).first()
        if not chat_thread:
            messages.error(request, "Chat thread not found.")
            return redirect('conversation')
    else:
        # Get the most recent thread
        chat_thread = farmer.chat_threads.order_by('-updated_at').first()
        if not chat_thread:
            # If no chat threads exist, create one
            chat_thread = ChatThread.objects.create(
                farmer=farmer,
                title='New chat',
                history=[]
            )
    
    # Handle AJAX requests for new messages
    if request.method == 'POST' and request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        user_message = request.POST.get('message', '').strip()
        
        if not user_message:
            return JsonResponse({'error': 'Message cannot be empty'}, status=400)
        
        # Get the advisor response
        advisor_response = chat_with_advisor(farmer, chat_thread, user_message)
        
        # Return the response as JSON
        return JsonResponse({
            'status': 'success',
            'user_message': user_message,
            'advisor_response': advisor_response
        })
    
    # GET request - display conversation page
    # Fetch all chat threads for this farmer
    chat_threads = farmer.chat_threads.all().order_by('-updated_at')
    
    # Filter out system messages for display (only show user and assistant messages)
    conversation_history = [
        msg for msg in (chat_thread.history or [])
        if msg.get('role') != 'system'
    ]
    
    context = {
        'farmer': farmer,
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