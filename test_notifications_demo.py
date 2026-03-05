"""
Test script to demonstrate how to trigger notifications manually.

Usage:
    python manage.py shell < test_notifications.py
    
Or copy the contents into Django shell:
    python manage.py shell
"""
import os 
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'crpas.settings')
django.setup()

from app.models import Farmer
from app.notification_utils import create_and_send_notification


# Get the first farmer (or create one for testing)
try:
    farmer = Farmer.objects.first()
    if not farmer:
        print("No farmers found. Please create a farmer first.")
        exit()
    
    print(f"\n=== Testing Notifications for {farmer} ===\n")
    
    # Test 1: Rainfall notification
    print("1. Testing Rainfall Notification...")
    notif1 = create_and_send_notification(
        farmer=farmer,
        title="🌧️ Good Rainfall Recorded",
        message="35mm of rainfall was recorded in your area. This is excellent for crop growth. Ensure proper drainage.",
        notification_type='rainfall',
        metadata={
            'rainfall_amount': 35,
            'date': '2026-03-05',
            'location': f'{farmer.lat}, {farmer.long}'
        }
    )
    print(f"   ✓ Created: {notif1}")
    
    # Test 2: Soil moisture notification
    print("\n2. Testing Soil Moisture Notification...")
    notif2 = create_and_send_notification(
        farmer=farmer,
        title="⚠️ Low Soil Moisture Alert",
        message="Soil moisture is at 30%. Below optimal range for maize. Consider irrigation.",
        notification_type='soil_moisture',
        metadata={
            'moisture_percent': 30,
            'soil_type': 'sandy loam',
            'optimal_range': '40-70%'
        }
    )
    print(f"   ✓ Created: {notif2}")
    
    # Test 3: Dry spell warning
    print("\n3. Testing Dry Spell Warning...")
    notif3 = create_and_send_notification(
        farmer=farmer,
        title="☀️ Dry Spell Warning",
        message="Low rainfall expected for the next 10 days. Prepare irrigation plans.",
        notification_type='dry_spell',
        metadata={
            'expected_duration': 10,
            'severity': 'moderate'
        }
    )
    print(f"   ✓ Created: {notif3}")
    
    # Test 4: Planting date alert
    print("\n4. Testing Planting Date Alert...")
    notif4 = create_and_send_notification(
        farmer=farmer,
        title="✅ Optimal Planting Time",
        message="Recent rainfall and soil moisture indicate it's a good time to plant maize. Plant within the next week.",
        notification_type='planting_date',
        metadata={
            'crop': 'maize',
            'confidence': 0.85
        }
    )
    print(f"   ✓ Created: {notif4}")
    
    # Test 5: General advisory
    print("\n5. Testing General Advisory...")
    notif5 = create_and_send_notification(
        farmer=farmer,
        title="ℹ️ Weekly Farming Advisory",
        message="This week: Monitor for armyworms in your maize field. Scout 10 plants per field daily.",
        notification_type='advisory',
        metadata={
            'pest': 'armyworms',
            'crop': 'maize'
        }
    )
    print(f"   ✓ Created: {notif5}")
    
    print(f"\n=== Summary ===")
    print(f"Total notifications: {farmer.notifications.count()}")
    print(f"Unread: {farmer.notifications.filter(status='unread').count()}")
    print(f"\n✅ All test notifications created successfully!")
    
except Exception as e:
    print(f"Error: {str(e)}")
    import traceback
    traceback.print_exc()
