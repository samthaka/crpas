from django.shortcuts import render, redirect, get_object_or_404
from django.views.generic import ListView, DetailView
from django.contrib import messages
from .models import Farmer
from .utils import get_rainfall_forecast, get_soil_data, generate_advisory
from .forms import CustomUserCreationForm, CustomAuthenticationForm, FarmerRegistrationForm
from django.contrib.auth import authenticate, login, logout, get_user_model
from django.contrib.auth.decorators import login_required

CustomUser = get_user_model()

@login_required(login_url='auth')
def institution_dashboard(request):
    return render(request, 'dashboard/dashboard.html')

def auth_view(request):
    """
    Handles both login and sign-up using email and password.
    Displays appropriate forms and error messages.
    """
    login_form = CustomAuthenticationForm()
    signup_form = CustomUserCreationForm()
    
    if request.method == 'POST':
        action = request.POST.get('action')
        
        if action == 'login':
            login_form = CustomAuthenticationForm(data=request.POST)
            if login_form.is_valid():
                email = login_form.cleaned_data["username"]
                password = login_form.cleaned_data["password"]
                # Authenticate using the custom backend
                user = authenticate(request, username=email, password=password)
                if user is not None:
                    login(request, user)
                    messages.success(request, f"Welcome back, {user.email}!")
                    return redirect('farmer_registration')
                else:
                    login_form.add_error(None, "Invalid email or password.")
            
        elif action == 'signup':
            signup_form = CustomUserCreationForm(request.POST)
            if signup_form.is_valid():
                try:
                    new_user = signup_form.save()
                    # Auto-login the user after signup
                    user = authenticate(request, username=new_user.email, password=request.POST.get('password1'))
                    if user is not None:
                        login(request, user)
                        messages.success(request, "Account created successfully! Welcome to CRPAS!")
                        return redirect('farmer_registration')
                except Exception as e:
                    signup_form.add_error(None, f"An error occurred during sign up: {str(e)}")
    
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
def farmer_registration(request):
    """
    Handle farmer registration where users add plot and contact information.
    """
    # Check if farmer already has a profile
    try:
        farmer = Farmer.objects.get(phone=request.POST.get('phone') if request.method == 'POST' else None)
    except Farmer.DoesNotExist:
        farmer = None
    
    if request.method == 'POST':
        form = FarmerRegistrationForm(request.POST, instance=farmer)
        if form.is_valid():
            farmer = form.save()
            messages.success(request, "Your farm details have been saved successfully!")
            return redirect('dashboard')
    else:
        form = FarmerRegistrationForm()
    
    return render(request, 'registration.html', {'form': form})