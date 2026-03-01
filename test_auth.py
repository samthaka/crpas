#!/usr/bin/env python
"""
Test script for email/password login and signup functionality
Run with: python manage.py shell < test_auth.py
"""

import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'crpas.settings')
django.setup()

from django.contrib.auth import get_user_model, authenticate
from app.forms import CustomUserCreationForm, CustomAuthenticationForm

CustomUser = get_user_model()

print("=" * 70)
print("TESTING EMAIL/PASSWORD AUTHENTICATION SYSTEM")
print("=" * 70)

# Test 1: Create a new user via signup form
print("\n[TEST 1] Creating a new user via signup form...")
signup_data = {
    'email': 'testuser@example.com',
    'password1': 'TestPassword123!',
    'password2': 'TestPassword123!',
}

signup_form = CustomUserCreationForm(signup_data)
if signup_form.is_valid():
    user = signup_form.save()
    print(f"✓ User created successfully: {user.email}")
else:
    print(f"✗ Form errors: {signup_form.errors}")

# Test 2: Try signup with existing email
print("\n[TEST 2] Attempting signup with existing email...")
duplicate_data = {
    'email': 'testuser@example.com',
    'password1': 'AnotherPassword123!',
    'password2': 'AnotherPassword123!',
}

signup_form2 = CustomUserCreationForm(duplicate_data)
if signup_form2.is_valid():
    print("✗ Form should have rejected duplicate email!")
else:
    print(f"✓ Form correctly rejected duplicate: {signup_form2.errors['email']}")

# Test 3: Try signup with mismatched passwords
print("\n[TEST 3] Attempting signup with mismatched passwords...")
mismatch_data = {
    'email': 'anotheruser@example.com',
    'password1': 'Password123!',
    'password2': 'DifferentPassword123!',
}

signup_form3 = CustomUserCreationForm(mismatch_data)
if signup_form3.is_valid():
    print("✗ Form should have rejected mismatched passwords!")
else:
    print(f"✓ Form correctly rejected mismatch: {signup_form3.errors}")

# Test 4: Authenticate with correct credentials
print("\n[TEST 4] Testing login with correct email and password...")
auth_data = {
    'username': 'testuser@example.com',
    'password': 'TestPassword123!',
}

auth_form = CustomAuthenticationForm(data=auth_data)
if auth_form.is_valid():
    print("✓ Login form validated successfully")
    user = authenticate(username='testuser@example.com', password='TestPassword123!')
    if user is not None:
        print(f"✓ User authenticated: {user.email}")
    else:
        print("✗ Authentication failed!")
else:
    print(f"✗ Login form errors: {auth_form.errors}")

# Test 5: Try login with wrong password
print("\n[TEST 5] Testing login with wrong password...")
wrong_pass_data = {
    'username': 'testuser@example.com',
    'password': 'WrongPassword123!',
}

auth_form2 = CustomAuthenticationForm(data=wrong_pass_data)
if auth_form2.is_valid():
    print("✗ Form should have rejected wrong password!")
else:
    print(f"✓ Form correctly rejected wrong credentials")

# Test 6: Try login with non-existent email
print("\n[TEST 6] Testing login with non-existent email...")
nonexistent_data = {
    'username': 'nonexistent@example.com',
    'password': 'SomePassword123!',
}

auth_form3 = CustomAuthenticationForm(data=nonexistent_data)
if auth_form3.is_valid():
    print("✗ Form should have rejected non-existent email!")
else:
    print(f"✓ Form correctly rejected non-existent user")

# Test 7: Verify CustomUser is properly configured
print("\n[TEST 7] Verifying CustomUser model configuration...")
all_users = CustomUser.objects.all()
print(f"✓ Total users in database: {all_users.count()}")
for user in all_users:
    print(f"  - {user.email} (is_active: {user.is_active})")

print("\n" + "=" * 70)
print("AUTHENTICATION TESTS COMPLETED")
print("=" * 70)
