#!/usr/bin/env python
"""
Test script to validate the DB fallback mechanism for ward resolution.
This demonstrates how the system ensures we never lose ward information
even when Nominatim fails.
"""

import os
import sys
import sqlite3
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'crpas.settings')
django.setup()

from app.utils import (
    reverse_geocode_coordinates,
    get_wards_in_constituency,
    validate_ward_in_constituency,
    fuzzy_match
)

def test_db_connectivity():
    """Test that we can connect to kenya_admin.db"""
    db_path = os.path.join(os.path.dirname(__file__), 'county-data', 'kenya_admin.db')
    print(f"\n✓ Testing DB connectivity...")
    print(f"  DB Path: {db_path}")
    print(f"  DB Exists: {os.path.exists(db_path)}")
    
    if os.path.exists(db_path):
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Count records
        cursor.execute("SELECT COUNT(*) FROM counties")
        county_count = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM constituencies")
        constituency_count = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM wards")
        ward_count = cursor.fetchone()[0]
        
        conn.close()
        
        print(f"  Counties: {county_count}")
        print(f"  Constituencies: {constituency_count}")
        print(f"  Wards: {ward_count}")
        return True
    return False


def test_fuzzy_matching():
    """Test fuzzy matching functionality"""
    print(f"\n✓ Testing fuzzy matching...")
    
    wards = ["Dagoretti North", "Dagoretti South", "Westlands", "Langata"]
    
    test_cases = [
        ("Dagoretti North", 0.75),  # Exact
        ("Dagoretti Norht", 0.75),  # Typo
        ("Westland", 0.75),         # Missing 's'
        ("Lang Ata", 0.75),         # Space instead of no space
    ]
    
    for test_name, threshold in test_cases:
        result = fuzzy_match(test_name, wards, threshold=threshold)
        print(f"  '{test_name}' → {result}")


def test_get_wards_in_constituency():
    """Test querying wards by constituency"""
    print(f"\n✓ Testing ward query by constituency...")
    
    test_constituencies = [
        "Kasipul",
        "Muhoroni",
        "Nairobi South",
    ]
    
    for constituency in test_constituencies:
        wards = get_wards_in_constituency(constituency)
        print(f"  {constituency}: {len(wards)} wards")
        if wards:
            print(f"    Examples: {', '.join(wards[:3])}")


def test_validate_ward():
    """Test ward validation against constituency"""
    print(f"\n✓ Testing ward validation...")
    
    # First, get some real data
    db_path = os.path.join(os.path.dirname(__file__), 'county-data', 'kenya_admin.db')
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    cursor.execute("SELECT c.name, w.name FROM constituencies c JOIN wards w ON c.id = w.constituency_id LIMIT 5")
    samples = cursor.fetchall()
    conn.close()
    
    for constituency, ward in samples:
        result = validate_ward_in_constituency(ward, constituency)
        status = "✓" if result else "✗"
        print(f"  {status} Ward '{ward}' in '{constituency}': {result}")


def test_reverse_geocoding_with_fallback():
    """Test reverse geocoding with DB fallback"""
    print(f"\n✓ Testing reverse geocoding with DB fallback...")
    
    # Test coordinates (these should resolve in Kenya)
    test_coords = [
        (-1.3552, 36.7792, "Dagoretti area (Nairobi)"),
        (-0.4162, 34.7617, "Kisii area"),
        (-1.0083, 34.7617, "Muhoroni area (Kisii)"),
    ]
    
    for lat, lon, description in test_coords:
        print(f"\n  Testing: {description} ({lat}, {lon})")
        result = reverse_geocode_coordinates(lat, lon)
        
        if result:
            print(f"    County: {result.get('county', 'N/A')}")
            print(f"    Sub-County: {result.get('sub_county', 'N/A')}")
            print(f"    Ward: {result.get('ward', 'N/A')}")
            print(f"    Confidence: {result.get('confidence', 'N/A')}")
            
            if 'suggested_wards' in result:
                print(f"    Fallback options: {', '.join(result['suggested_wards'])}")
        else:
            print(f"    ERROR: Could not geocode")


def main():
    print("="*70)
    print("Ward Fallback Mechanism Test Suite")
    print("="*70)
    
    if not test_db_connectivity():
        print("\n✗ ERROR: Could not connect to kenya_admin.db")
        print("  Make sure county_data_gen.py has been run to generate the DB")
        return
    
    test_fuzzy_matching()
    test_get_wards_in_constituency()
    test_validate_ward()
    test_reverse_geocoding_with_fallback()
    
    print("\n" + "="*70)
    print("Test Complete!")
    print("="*70)


if __name__ == '__main__':
    main()
