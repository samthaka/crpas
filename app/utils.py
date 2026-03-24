import logging
import requests
import sqlite3
import os
from difflib import SequenceMatcher
from django.conf import settings
from datetime import datetime, timedelta

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Try to import Groq (may not be installed in all environments)
try:
    from groq import Groq
    GROQ_AVAILABLE = True
except ImportError:
    GROQ_AVAILABLE = False
    logger.warning("Groq module not installed - chat features will not work")

# Path to the Kenya admin database
KENYA_ADMIN_DB = os.path.join(os.path.dirname(__file__), '..', 'county-data', 'kenya_admin.db')


def format_location_name(name):
    """
    Format location names for UI display.
    Converts to title case: 'KISII CENTRAL' → 'Kisii Central'
    """
    if not name:
        return name
    return name.title()


def remove_county_suffix(county_name):
    """
    Remove ' County' suffix from county name.
    'Kisii County' → 'Kisii'
    """
    if not county_name:
        return county_name
    if county_name.endswith(' County'):
        return county_name[:-7].strip()  # Remove ' County' (7 chars)
    return county_name


def fuzzy_match(name, choices, threshold=0.70):
    """
    Fuzzy match a name against a list of choices.
    Returns the best match if similarity >= threshold, else None.
    
    Args:
        name: String to match
        choices: List of strings to match against
        threshold: Minimum similarity score (0-1)
    
    Returns:
        Best matching string or None
    """
    if not name or not choices:
        return None
    
    name_lower = name.lower().strip()
    best_match = None
    best_score = 0
    
    for choice in choices:
        choice_lower = choice.lower().strip()
        # Calculate similarity ratio
        score = SequenceMatcher(None, name_lower, choice_lower).ratio()
        if score > best_score:
            best_score = score
            best_match = choice
    
    if best_score >= threshold:
        logger.debug(f"Fuzzy match: '{name}' → '{best_match}' (score: {best_score:.2f})")
        return best_match
    
    logger.debug(f"No fuzzy match for '{name}' (best score: {best_score:.2f}, threshold: {threshold})")
    return None


def get_wards_in_constituency(constituency_name):
    """
    Query kenya_admin.db to get all wards in a given constituency.
    
    Args:
        constituency_name: Name of the constituency (sub-county)
    
    Returns:
        List of ward names, or empty list if not found
    """
    try:
        if not os.path.exists(KENYA_ADMIN_DB):
            logger.error(f"Kenya admin DB not found at {KENYA_ADMIN_DB}")
            return []
        
        conn = sqlite3.connect(KENYA_ADMIN_DB)
        cursor = conn.cursor()
        
        # First, find the constituency ID
        cursor.execute(
            "SELECT id FROM constituencies WHERE LOWER(name) = LOWER(?)",
            (constituency_name,)
        )
        result = cursor.fetchone()
        
        if not result:
            logger.warning(f"Constituency '{constituency_name}' not found in DB")
            conn.close()
            return []
        
        constituency_id = result[0]
        
        # Now get all wards in this constituency
        cursor.execute(
            "SELECT name FROM wards WHERE constituency_id = ? ORDER BY name",
            (constituency_id,)
        )
        wards = [row[0] for row in cursor.fetchall()]
        conn.close()
        
        logger.info(f"Found {len(wards)} wards in constituency '{constituency_name}': {wards}")
        return wards
    
    except Exception as e:
        logger.error(f"Error querying wards in constituency: {str(e)}")
        return []


def find_constituency_by_ward(ward_name):
    """
    Reverse lookup: Given a ward name, find which constituency it belongs to.
    This handles cases where Nominatim's 'county' field actually contains a ward name.
    
    Args:
        ward_name: Name of the ward to search for
    
    Returns:
        Tuple of (constituency_name, valid_ward_name) if found, else None
    """
    try:
        if not os.path.exists(KENYA_ADMIN_DB):
            logger.error(f"Kenya admin DB not found at {KENYA_ADMIN_DB}")
            return None
        
        conn = sqlite3.connect(KENYA_ADMIN_DB)
        cursor = conn.cursor()
        
        # Try exact match first
        cursor.execute("""
            SELECT c.name, w.name
            FROM wards w
            JOIN constituencies c ON w.constituency_id = c.id
            WHERE LOWER(w.name) = LOWER(?)
            LIMIT 1
        """, (ward_name,))
        
        result = cursor.fetchone()
        if result:
            logger.info(f"Found ward '{ward_name}' in constituency '{result[0]}'")
            conn.close()
            return result  # (constituency_name, ward_name)
        
        # Try fuzzy match if exact doesn't work
        cursor.execute("SELECT name FROM wards")
        all_wards = [row[0] for row in cursor.fetchall()]
        
        matched_ward = fuzzy_match(ward_name, all_wards, threshold=0.70)
        if matched_ward:
            cursor.execute("""
                SELECT c.name, w.name
                FROM wards w
                JOIN constituencies c ON w.constituency_id = c.id
                WHERE LOWER(w.name) = LOWER(?)
                LIMIT 1
            """, (matched_ward,))
            result = cursor.fetchone()
            if result:
                logger.info(f"Fuzzy matched '{ward_name}' to ward '{matched_ward}' in constituency '{result[0]}'")
                conn.close()
                return result
        
        logger.warning(f"Ward '{ward_name}' not found in database")
        conn.close()
        return None
    
    except Exception as e:
        logger.error(f"Error finding constituency by ward: {str(e)}")
        return None


def validate_ward_in_constituency(ward_name, constituency_name):
    """
    Check if a ward belongs to a given constituency in the DB.
    Uses fuzzy matching to handle naming variations.
    
    Args:
        ward_name: Name of the ward
        constituency_name: Name of the constituency
    
    Returns:
        Validated ward name from DB, or None
    """
    try:
        if not os.path.exists(KENYA_ADMIN_DB):
            logger.error(f"Kenya admin DB not found at {KENYA_ADMIN_DB}")
            return None
        
        conn = sqlite3.connect(KENYA_ADMIN_DB)
        cursor = conn.cursor()
        
        # Find constituency ID
        cursor.execute(
            "SELECT id FROM constituencies WHERE LOWER(name) = LOWER(?)",
            (constituency_name,)
        )
        result = cursor.fetchone()
        
        if not result:
            logger.warning(f"Constituency '{constituency_name}' not found in DB")
            conn.close()
            return None
        
        constituency_id = result[0]
        
        # Get all wards in this constituency
        cursor.execute(
            "SELECT name FROM wards WHERE constituency_id = ? ORDER BY name",
            (constituency_id,)
        )
        valid_wards = [row[0] for row in cursor.fetchall()]
        conn.close()
        
        # Try exact match first
        for w in valid_wards:
            if w.lower() == ward_name.lower():
                logger.info(f"Ward '{ward_name}' validated in constituency '{constituency_name}'")
                return w
        
        # Try fuzzy match
        matched_ward = fuzzy_match(ward_name, valid_wards, threshold=0.70)
        if matched_ward:
            logger.info(f"Ward '{ward_name}' fuzzy-matched to '{matched_ward}' in constituency '{constituency_name}'")
            return matched_ward
        
        logger.warning(f"Ward '{ward_name}' not found in constituency '{constituency_name}'")
        return None
    
    except Exception as e:
        logger.error(f"Error validating ward: {str(e)}")
        return None


def geocode_from_location(county, sub_county=None, ward=None):
    """
    Forward geocode Kenya administrative location names to GPS coordinates.
    Uses Nominatim (OpenStreetMap) - free API, no key required.
    Tries multiple search strategies with fallback options.
    
    Args:
        county: County name (required, e.g., "Kisii County" or "Kisii")
        sub_county: Sub-county/Constituency name (optional, e.g., "Kisii Central")
        ward: Ward name (optional, e.g., "Nyaribari Chache")
    
    Returns:
        Dict with 'lat' and 'lon' keys, or None if geocoding fails
        Example: {'lat': 0.6234, 'lon': 35.2891, 'source': 'nominatim'}
    """
    if not county:
        logger.warning("[ADVISOR DEBUG] geocode_from_location: No county provided")
        return None
    
    # Normalize county name (ensure "County" suffix is present)
    county_normalized = remove_county_suffix(county).strip()
    if not county_normalized.endswith(' County'):
        county_normalized = county_normalized + ' County'
    
    # Build multiple search strategies (most specific to least specific)
    search_queries = []
    
    # Strategy 1: Full address with ward, sub_county, and county
    if ward and sub_county:
        search_queries.append(f"{ward}, {sub_county}, {county_normalized}, Kenya")
    
    # Strategy 2: Sub_county and county (for constituency-level geocoding)
    if sub_county:
        search_queries.append(f"{sub_county}, {county_normalized}, Kenya")
    
    # Strategy 3: Ward and county (skip sub_county)
    if ward:
        search_queries.append(f"{ward}, {county_normalized}, Kenya")
    
    # Strategy 4: Just the county
    search_queries.append(f"{county_normalized}, Kenya")
    
    for search_location in search_queries:
        try:
            logger.info(f"[ADVISOR DEBUG] Attempting geocoding: {search_location}")
            
            # Nominatim API endpoint for forward geocoding
            url = "https://nominatim.openstreetmap.org/search"
            params = {
                'q': search_location,
                'format': 'json',
                'limit': 1,
                'accept-language': 'en'
            }
            
            # Add User-Agent as required by Nominatim
            headers = {
                'User-Agent': 'CRPAS-AgriculturalAdvisor/1.0'
            }
            
            response = requests.get(url, params=params, headers=headers, timeout=10)
            response.raise_for_status()
            results = response.json()
            
            if results:
                # Get the first (most relevant) result
                result = results[0]
                lat = float(result['lat'])
                lon = float(result['lon'])
                
                logger.info(f"[ADVISOR DEBUG] Successfully geocoded '{search_location}' → lat={lat:.6f}, lon={lon:.6f}")
                return {'lat': lat, 'lon': lon, 'source': 'nominatim', 'query': search_location}
            else:
                logger.debug(f"[ADVISOR DEBUG] Nominatim returned no results for: {search_location}")
                continue
        
        except requests.exceptions.Timeout as e:
            logger.warning(f"[ADVISOR DEBUG] Nominatim timeout for '{search_location}': {str(e)}")
            continue
        except requests.exceptions.ConnectionError as e:
            logger.warning(f"[ADVISOR DEBUG] Nominatim connection error for '{search_location}': {str(e)}")
            continue
        except Exception as e:
            logger.warning(f"[ADVISOR DEBUG] Nominatim error for '{search_location}': {type(e).__name__}: {str(e)}")
            continue
    
    # If all Nominatim queries failed, try hardcoded fallback coordinates for major Kenya counties
    logger.warning(f"[ADVISOR DEBUG] Nominatim geocoding failed for all search queries. Checking hardcoded fallback coordinates.")
    fallback_coords = get_county_fallback_coordinates(county_normalized)
    if fallback_coords:
        logger.info(f"[ADVISOR DEBUG] Using fallback coordinates for {county_normalized}: lat={fallback_coords['lat']}, lon={fallback_coords['lon']}")
        return fallback_coords
    
    logger.error(f"[ADVISOR DEBUG] Geocoding failed completely for county: {county_normalized}")
    return None


def get_county_fallback_coordinates(county_name):
    """
    Hardcoded fallback coordinates for major Kenyan counties.
    Used when Nominatim API fails or doesn't return results.
    
    Args:
        county_name: County name (e.g., "Kisii County")
    
    Returns:
        Dict with 'lat', 'lon', 'source' keys, or None if not found
    """
    # Approximate center coordinates for major Kenya counties
    county_coords = {
        'Kisii County': {'lat': -0.683, 'lon': 34.758},
        'Kisii': {'lat': -0.683, 'lon': 34.758},
        'Nyanza': {'lat': -0.5, 'lon': 34.3},
        'Western': {'lat': -0.2, 'lon': 34.5},
        'Nairobi': {'lat': -1.286, 'lon': 36.818},
        'Nakuru': {'lat': -0.303, 'lon': 36.070},
        'Rift Valley': {'lat': 0.0, 'lon': 35.5},
        'Coast': {'lat': -4.0, 'lon': 39.3},
        'Eastern': {'lat': -0.5, 'lon': 39.0},
        'Central': {'lat': -0.5, 'lon': 36.5},
        'North Eastern': {'lat': 1.0, 'lon': 39.5},
    }
    
    # Try exact match first
    for key, coords in county_coords.items():
        if key.lower() == county_name.lower():
            return {'lat': coords['lat'], 'lon': coords['lon'], 'source': 'fallback'}
    
    # Try partial match
    county_lower = county_name.lower()
    for key, coords in county_coords.items():
        if key.lower() in county_lower or county_lower in key.lower():
            logger.info(f"[ADVISOR DEBUG] Matched '{county_name}' to fallback '{key}'")
            return {'lat': coords['lat'], 'lon': coords['lon'], 'source': 'fallback'}
    
    return None


def reverse_geocode_coordinates(lat, lon):
    """
    Reverse geocode GPS coordinates to extract Kenya administrative divisions.
    Uses Nominatim (OpenStreetMap) - free API, no key required.
    Falls back to kenya_admin.db when Nominatim doesn't return valid data.
    
    IMPORTANT: Nominatim's field mapping is confusing for Kenya:
    - state → County (correct)
    - county → Can be ward name, not constituency!
    - town/village → May be locality, not necessarily the ward
    
    So we do reverse lookups in the DB to find the correct hierarchy.
    
    Returns a dict with:
    {
        'county': 'County Name',
        'sub_county': 'Sub-County Name',
        'ward': 'Ward Name',
        'confidence': 'HIGH|MEDIUM|LOW|DB_FALLBACK'
    }
    
    Returns None if geocoding fails completely.
    """
    if not lat or not lon:
        return None
    
    try:
        # Nominatim API endpoint for reverse geocoding
        url = "https://nominatim.openstreetmap.org/reverse"
        params = {
            'format': 'json',
            'lat': lat,
            'lon': lon,
            'zoom': 18,  # Detailed address
            'accept-language': 'en'
        }
        
        # Add User-Agent as required by Nominatim
        headers = {
            'User-Agent': 'CRPAS-AgriculturalAdvisor/1.0'
        }
        
        response = requests.get(url, params=params, headers=headers, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        if not data:
            logger.warning(f"Empty response from Nominatim for ({lat}, {lon})")
            return None
        
        address = data.get('address', {})
        logger.debug(f"Full address from Nominatim: {address}")
        
        # Extract County (from state field - this is reliable)
        county = address.get('state')
        if county:
            # Remove ' County' suffix and format
            county = remove_county_suffix(county)
            county = format_location_name(county)
        
        if not county:
            logger.error(f"Could not extract county from Nominatim for ({lat}, {lon})")
            return None
        
        # KEY INSIGHT: Nominatim's 'county' field often contains a WARD name, not the constituency!
        # We need to intelligently parse what we got and reverse-lookup in the DB
        nominatim_county = address.get('county')  # Could be ward, could be constituency
        nominatim_town = address.get('town')
        nominatim_village = address.get('village')
        nominatim_hamlet = address.get('hamlet')
        nominatim_district = address.get('district')
        
        # Collect all potential ward names from Nominatim
        potential_wards = [w for w in [
            nominatim_county,
            nominatim_town,
            nominatim_village,
            nominatim_hamlet,
            nominatim_district,
            address.get('suburb'),
            address.get('neighbourhood'),
            address.get('locality')
        ] if w]
        
        logger.debug(f"Potential wards from Nominatim: {potential_wards}")
        
        result = {'county': county}
        confidence = 'HIGH'
        final_ward = None
        final_constituency = None
        
        # STRATEGY: Try to find the ward by reverse-lookup
        # For each potential ward name, check if it exists in the DB
        for potential_ward in potential_wards:
            lookup_result = find_constituency_by_ward(potential_ward)
            if lookup_result:
                final_constituency, final_ward = lookup_result
                logger.info(f"Reverse lookup found: ward='{final_ward}' in constituency='{final_constituency}'")
                break
        
        # If we found a valid ward & constituency through reverse lookup
        if final_constituency and final_ward:
            result['sub_county'] = format_location_name(final_constituency)
            result['ward'] = format_location_name(final_ward)
            confidence = 'HIGH'
            logger.info(f"Geocoded ({lat}, {lon}) → County: {county}, Sub-county: {result['sub_county']}, Ward: {result['ward']}")
        
        else:
            # Fallback: Try to validate the sub_county field from Nominatim
            # First, try to find a constituency that matches
            if nominatim_county:
                # Check if this is a valid constituency in the DB
                wards_in_constituency = get_wards_in_constituency(nominatim_county)
                if wards_in_constituency:
                    # It's a valid constituency!
                    result['sub_county'] = format_location_name(nominatim_county)
                    result['ward'] = format_location_name(wards_in_constituency[0])  # Use first ward as primary
                    if len(wards_in_constituency) > 1:
                        result['suggested_wards'] = [format_location_name(w) for w in wards_in_constituency[:5]]
                    confidence = 'DB_FALLBACK'
                    logger.info(f"Used first ward '{result['ward']}' from DB for constituency '{result['sub_county']}'")
                else:
                    # Not a valid constituency - try reverse lookup on it
                    lookup_result = find_constituency_by_ward(nominatim_county)
                    if lookup_result:
                        final_constituency, final_ward = lookup_result
                        result['sub_county'] = format_location_name(final_constituency)
                        result['ward'] = format_location_name(final_ward)
                        confidence = 'MEDIUM'
                        logger.info(f"Nominatim's 'county' field was actually a ward: '{result['ward']}' in '{result['sub_county']}'")
                    else:
                        confidence = 'LOW'
                        logger.warning(f"Nominatim's county field '{nominatim_county}' is neither a constituency nor a ward in DB")
        
        # Final fallback: If we still don't have anything, query by GPS proximity
        if not result.get('ward'):
            logger.warning(f"Could not determine ward for ({lat}, {lon}), confidence is LOW")
            result['confidence'] = 'LOW'
            return result if 'sub_county' in result else None
        
        # Add confidence metric to result
        result['confidence'] = confidence
        logger.info(f"Reverse geocoded ({lat}, {lon}) → {result}")
        return result
            
    except requests.exceptions.Timeout:
        logger.error(f"Nominatim API timeout for ({lat}, {lon})")
        return None
    except requests.exceptions.RequestException as e:
        logger.error(f"Nominatim API error for ({lat}, {lon}): {str(e)}")
        return None
    except Exception as e:
        logger.error(f"Reverse geocoding error for ({lat}, {lon}): {str(e)}")
        return None

def generate_chat_title(user_message):
    """
    Generate a concise title/summary of the first user message using Groq.
    Returns a short, meaningful title (3-7 words) for organizing chats.
    Falls back to truncated message if Groq is not available.
    """
    if not GROQ_AVAILABLE:
        # Fallback: use first 40 characters of message
        return user_message[:40].strip() + "..." if len(user_message) > 40 else user_message
    
    client = Groq(api_key=settings.GROQ_API_KEY)
    
    prompt = f"""Given this farming question from a farmer, generate a very short title (3-7 words max) that summarizes what they're asking about. 
Only output the title, nothing else.

Question: {user_message}

Title:"""
    
    try:
        response = client.chat.completions.create(
            messages=[
                {"role": "user", "content": prompt}
            ],
            model="llama-3.3-70b-versatile",
            temperature=0.3,
            max_tokens=20,
        )
        
        title = response.choices[0].message.content.strip()
        # Ensure title is not too long
        if len(title) > 50:
            title = title[:50].strip() + "..."
        return title if title else "New chat"
    except Exception as e:
        logger.warning(f"Failed to generate title: {str(e)}")
        # Fallback to first 40 chars if API fails
        return user_message[:40].strip() + "..." if len(user_message) > 40 else user_message

def get_rainfall_forecast(lat, lon, days=10):
    """Fetch 10-day rainfall forecast from Open-Meteo (free, no key)"""
    url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": lat,
        "longitude": lon,
        "daily": "precipitation_sum,precipitation_probability_max,precipitation_probability_min,temperature_2m_max,temperature_2m_min",
        "timezone": "Africa/Nairobi",
        "forecast_days": days,
    }
    try:
        logger.info(f"[ADVISOR DEBUG] Fetching rainfall forecast from Open-Meteo: lat={lat}, lon={lon}, days={days}")
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        logger.info(f"[ADVISOR DEBUG] Open-Meteo API response status: {response.status_code}, data keys: {list(data.keys())}")
        
        # Simplify: list of dates with rain mm, prob, temps
        forecast = []
        for i in range(len(data['daily']['time'])):
            forecast.append({
                "date": data['daily']['time'][i],
                "rain_mm": data['daily']['precipitation_sum'][i],
                "prob_max": data['daily']['precipitation_probability_max'][i],
                "temp_max": data['daily']['temperature_2m_max'][i],
                "temp_min": data['daily']['temperature_2m_min'][i],
            })
        logger.info(f"[ADVISOR DEBUG] Rainfall forecast successfully retrieved: {len(forecast)} days of forecast data")
        logger.debug(f"[ADVISOR DEBUG] Forecast sample: {forecast[0] if forecast else 'NO DATA'}")
        return forecast
    except requests.exceptions.Timeout as e:
        logger.error(f"[ADVISOR DEBUG] Open-Meteo API TIMEOUT: {str(e)}")
        return {"error": f"Timeout: {str(e)}"}
    except requests.exceptions.ConnectionError as e:
        logger.error(f"[ADVISOR DEBUG] Open-Meteo API CONNECTION ERROR: {str(e)}")
        return {"error": f"Connection error: {str(e)}"}
    except Exception as e:
        logger.error(f"[ADVISOR DEBUG] Open-Meteo API ERROR: {type(e).__name__}: {str(e)}")
        return {"error": str(e)}

def get_soil_data(lat, lon):
    """Fetch current soil moisture/temp from Open-Meteo (hourly, take recent) + iSDA later"""
    # For now, use Open-Meteo soil moisture (0-81cm layers, current + forecast)
    url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": lat,
        "longitude": lon,
        "hourly": "soil_moisture_0_to_1cm,soil_moisture_9_to_27cm,soil_moisture_27_to_81cm,soil_temperature_0cm,soil_temperature_18cm",
        "timezone": "Africa/Nairobi",
        "forecast_days": 1,  # current + short forecast
    }
    try:
        logger.info(f"[ADVISOR DEBUG] Fetching soil data from Open-Meteo: lat={lat}, lon={lon}")
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        logger.info(f"[ADVISOR DEBUG] Open-Meteo soil API response status: {response.status_code}, data keys: {list(data.keys())}")
        
        if 'hourly' not in data:
            logger.error(f"[ADVISOR DEBUG] Open-Meteo soil response missing 'hourly' key. Available keys: {list(data.keys())}")
            return {"error": "Invalid response format", "response_keys": list(data.keys())}
        
        if not data['hourly']['time']:
            logger.error(f"[ADVISOR DEBUG] Open-Meteo soil response has no time data")
            return {"error": "No time data in response"}
        
        latest_hour = data['hourly']['time'][0]  # most recent
        idx = 0  # first (current)
        
        result = {
            "soil_moisture_top": data['hourly']['soil_moisture_0_to_1cm'][idx],
            "soil_moisture_mid": data['hourly']['soil_moisture_9_to_27cm'][idx],
            "soil_moisture_deep": data['hourly']['soil_moisture_27_to_81cm'][idx],
            "soil_temp_surface": data['hourly']['soil_temperature_0cm'][idx],
            "soil_temp_mid": data['hourly']['soil_temperature_18cm'][idx],
            "timestamp": latest_hour,
        }
        logger.info(f"[ADVISOR DEBUG] Soil data successfully retrieved: moisture_top={result['soil_moisture_top']}, timestamp={latest_hour}")
        return result
    except requests.exceptions.Timeout as e:
        logger.error(f"[ADVISOR DEBUG] Open-Meteo soil API TIMEOUT: {str(e)}")
        return {"error": f"Timeout: {str(e)}"}
    except requests.exceptions.ConnectionError as e:
        logger.error(f"[ADVISOR DEBUG] Open-Meteo soil API CONNECTION ERROR: {str(e)}")
        return {"error": f"Connection error: {str(e)}"}
    except requests.exceptions.HTTPError as e:
        logger.error(f"[ADVISOR DEBUG] Open-Meteo soil API HTTP ERROR: {response.status_code} - {str(e)}")
        return {"error": f"HTTP {response.status_code}: {str(e)}"}
    except KeyError as e:
        logger.error(f"[ADVISOR DEBUG] Open-Meteo soil response missing expected key: {str(e)}. Response structure: {list(data.keys()) if 'data' in locals() else 'No data'}")
        return {"error": f"Missing key in response: {str(e)}"}
    except Exception as e:
        logger.error(f"[ADVISOR DEBUG] Open-Meteo soil API ERROR: {type(e).__name__}: {str(e)}")
        return {"error": f"Soil data fetch failed: {str(e)}", "fallback": "Assume moderate moisture (0.25 m³/m³)"}


def generate_advisory(farm, forecast_data, soil_data):
    """Use Groq with a strong free model for reasoning"""
    client = Groq(api_key=settings.GROQ_API_KEY)

    crop = "maize" if farm.crop_type == 'maize' else "beans" if farm.crop_type == 'beans' else "maize and beans intercropped"
    
    # Format forecast nicely for prompt
    forecast_str = "\n".join([f"{day['date']}: {day['rain_mm']}mm rain (prob {day['prob_max']}%), temp {day['temp_min']}-{day['temp_max']}°C" for day in forecast_data[:10]])

    prompt = f"""
You are an expert Kenyan agronomist advising smallholder farmers using local climate logic.
Your goal is to reduce false-start planting risk.

Farmer: {farm.farmer.fname} {farm.farmer.lname}
Location: {farm.lat}, {farm.long}
Crop: {crop}

CURRENT SOIL CONDITIONS:
- Top soil moisture: {soil_data.get('soil_moisture_top', 'N/A')} m³/m³
- Mid soil moisture: {soil_data.get('soil_moisture_mid', 'N/A')} m³/m³
- Deep soil moisture: {soil_data.get('soil_moisture_deep', 'N/A')} m³/m³
- Surface soil temperature: {soil_data.get('soil_temp_surface', 'N/A')} °C

RAINFALL & WEATHER FORECAST (next 10 days):
{forecast_str}

AGRONOMIC RULES (Kenyan conditions):

Maize:
- Needs at least 20-30 mm cumulative rain over 5-7 days to plant safely
- High failure risk if >7 dry days occur after first rain
- Very sensitive in first 30 days after planting
- Early rains increase fall armyworm risk

Beans:
- Can plant with 15-20 mm over ~5 days
- More tolerant to short dry spells
- Wet-dry cycles increase fungal disease risk

ANALYZE STEP-BY-STEP:
1. Identify if upcoming rains are a FALSE START (rain followed by long dry spell).
2. Check if rainfall + soil moisture align to support germination.
3. Determine the BEST planting window in the next 10-14 days.
4. If conditions are risky, clearly advise to WAIT.
5. Add simple risk alerts (pests or disease) only if relevant.

OUTPUT RULES:
- Output ONLY one SMS-style message
- Start exactly with:
  "Habari {farm.farmer.fname}! Ushauri wa Kupanda wa CRPAS:"
- Use simple English with very light simple Kiswahili if helpful
- Mention specific dates or date ranges
- Be clear and decisive (Plant / Wait and When to plant)
- Keep an open tone, avoid technical jargon, and be encouraging
- Keep under 500 characters if possible
- Do NOT explain your reasoning
"""

    try:
        messages_payload = [
            {"role": "system", "content": "You are a helpful Kenyan farming advisor."},
            {"role": "user", "content": prompt},
        ]
        logger.debug(f"Sending advisory prompt to Groq API: {messages_payload}")
        chat_completion = client.chat.completions.create(
            messages=messages_payload,
            model="llama-3.3-70b-versatile",
            temperature=0.7,
            max_tokens=400,
        )
        advisory = chat_completion.choices[0].message.content.strip()

        # Optional: Save to history (adapt format)
        new_entry = [
            {"role": "user", "content": prompt},
            # Groq/chat API uses 'assistant' for model responses
            {"role": "assistant", "content": advisory}
        ]
        farm.farmer.gemini_chat_history.extend(new_entry)  # Reuse field name or rename later
        farm.farmer.save()

        return advisory
    except Exception as e:
        return f"Error generating advisory: {str(e)}"


def chat_with_advisor(farm, chat_thread, user_message):
    """
    Handle conversational chat with the advisor about farming topics.
    Uses Groq to maintain context across multiple messages in the current chat thread.
    Includes REAL-TIME weather and soil data for accurate, data-driven recommendations.
    Only sends the system prompt + messages from the current chat thread to avoid context bloat.
    
    Args:
        farm (Farm): The farm being discussed in the chat
        chat_thread (ChatThread): The conversation thread
        user_message (str): The user's message
    """
    if not GROQ_AVAILABLE:
        return "Sorry, the chat advisor is currently unavailable. Please ensure the Groq API is properly configured."
    
    client = Groq(api_key=settings.GROQ_API_KEY)
    
    farmer = farm.farmer
    crop = "maize" if farm.crop_type == 'maize' else "beans" if farm.crop_type == 'beans' else "maize and beans (intercropped)"
    
    # Build location string with administrative divisions (these ARE known)
    location_parts = []
    if farm.county:
        location_parts.append(farm.county + " County")
    if farm.sub_county:
        location_parts.append(farm.sub_county)
    if farm.ward:
        location_parts.append(farm.ward)
    location_str = ", ".join(location_parts) if location_parts else "Location not specified"
    
    # Fetch real-time weather and soil data for DATA-DRIVEN advice
    # Try to get GPS coordinates: first from farm data, then by geocoding location
    forecast_data = None
    soil_data = None
    gps_note = ""
    actual_lat = farm.lat
    actual_lon = farm.long
    
    # If GPS is missing, try to geocode from administrative location
    if not actual_lat or not actual_lon:
        if farm.county:
            logger.info(f"[ADVISOR DEBUG] Farm {farm.id} missing GPS, attempting geocoding from location: {location_str}")
            geocoded = geocode_from_location(farm.county, farm.sub_county, farm.ward)
            if geocoded:
                actual_lat = geocoded['lat']
                actual_lon = geocoded['lon']
                logger.info(f"[ADVISOR DEBUG] Geocoding successful: {location_str} → lat={actual_lat:.6f}, lon={actual_lon:.6f}")
            else:
                logger.warning(f"[ADVISOR DEBUG] Geocoding failed for {location_str}. Will use regional patterns only.")
        else:
            logger.warning(f"[ADVISOR DEBUG] Farm {farm.id} has neither GPS coordinates nor administrative location. Unable to fetch real-time data.")
    
    # Now fetch weather/soil data if we have coordinates (either from farm or geocoding)
    if actual_lat and actual_lon:
        logger.info(f"[ADVISOR DEBUG] Farm has GPS coordinates (lat={actual_lat}, lon={actual_lon}), fetching real-time data")
        forecast_data = get_rainfall_forecast(actual_lat, actual_lon, days=10)
        soil_data = get_soil_data(actual_lat, actual_lon)
        
        # Log data fetch results
        if isinstance(forecast_data, dict) and 'error' in forecast_data:
            logger.error(f"[ADVISOR DEBUG] Rainfall forecast API failed: {forecast_data['error']}")
        else:
            logger.info(f"[ADVISOR DEBUG] Rainfall forecast retrieved successfully: {len(forecast_data)} days")
        
        if isinstance(soil_data, dict) and 'error' in soil_data:
            logger.error(f"[ADVISOR DEBUG] Soil data API failed: {soil_data['error']}")
        else:
            logger.info(f"[ADVISOR DEBUG] Soil data retrieved successfully")
        
        gps_note = f"(GPS: {actual_lat:.6f}, {actual_lon:.6f})"
    else:
        logger.warning(f"[ADVISOR DEBUG] Farm {farm.id} has no GPS coordinates and geocoding unavailable. Using administrative location only: {location_str}")
        gps_note = "(GPS coordinates not available - using regional seasonal patterns for context)"
    
    # Format forecast for prompt
    forecast_str = "Real-time weather data unavailable - GPS coordinates needed for precise forecasting"
    if forecast_data and isinstance(forecast_data, list) and len(forecast_data) > 0:
        forecast_str = "\n".join([f"  {day['date']}: {day['rain_mm']}mm rain (prob {day['prob_max']}%), temp {day['temp_min']}-{day['temp_max']}°C" for day in forecast_data[:10]])
        logger.info(f"[ADVISOR DEBUG] Using real-time forecast data with {len(forecast_data)} days")
    else:
        logger.warning(f"[ADVISOR DEBUG] Could not use forecast data (type={type(forecast_data)}, content={forecast_data if not isinstance(forecast_data, dict) else 'dict with error'}). Using fallback message.")
    
    # Format soil data for prompt
    soil_str = "Real-time soil data unavailable - GPS coordinates needed for precise readings"
    if isinstance(soil_data, dict) and 'error' not in soil_data and soil_data:
        soil_str = f"""Top layer: {soil_data.get('soil_moisture_top', 'N/A')} m³/m³
  Mid layer: {soil_data.get('soil_moisture_mid', 'N/A')} m³/m³
  Deep layer: {soil_data.get('soil_moisture_deep', 'N/A')} m³/m³
  Surface temp: {soil_data.get('soil_temp_surface', 'N/A')}°C"""
        logger.info(f"[ADVISOR DEBUG] Using real-time soil data: moisture_top={soil_data.get('soil_moisture_top')}")
    else:
        logger.warning(f"[ADVISOR DEBUG] Could not use soil data (type={type(soil_data)}, content={soil_data if not isinstance(soil_data, dict) else 'dict with error'}). Using fallback message.")
    
    # Build system prompt with REAL-TIME farm context and weather/soil data
    system_prompt = f"""You are a friendly and knowledgeable Kenyan agricultural advisor helping farmers improve their farming practices.

FARMER & FARM PROFILE:
- Name: {farmer.fname} {farmer.lname}
- Farm: {farm.farm_name or "Unnamed farm"}
- Farm Size: {farm.farm_size} acres
- Location: {location_str} {gps_note}
- Primary Crops: {crop}
- Today's Date: {datetime.now().strftime('%Y-%m-%d')}

CURRENT REAL-TIME CONDITIONS:
Soil Moisture:
{soil_str}

10-Day Weather Forecast:
{forecast_str}

LOCATION CONTEXT:
This farm is in {location_str}, which is in Kenya. Use this regional knowledge to inform your advice about:
- Typical rainfall patterns for this region/season
- Common pests and diseases in this area
- Appropriate crop varieties for this geography
- Water availability and management practices

CRITICAL RULES FOR PLANTING RECOMMENDATIONS:
When answering YES/NO planting questions:
- If real-time data available: Base decision on ACTUAL weather and soil moisture data
- If real-time data unavailable: Use regional seasonal patterns for {location_str}
  * Generally: Long rains March-May, Short rains Sept-Nov in Kenya
  * For Maize: Plant when soil is moist, needs 20-30mm rain over 5-7 days
  * For Beans: More flexible, needs 15-20mm rain over ~5 days
- Always consider current season and typical weather for the location
- Advise AGAINST planting if risk of false-start (rain followed by long dry spell)

Your role is to provide practical, location-aware farming advice about:
1. Planting decisions (yes/no) based on available data + regional knowledge
2. Crop selection and suitability for {location_str}
3. Best planting windows based on today's season and forecast (if available)
4. Pest and disease management for {location_str}
5. Soil health and water management strategies
6. Yield improvement techniques for this region
7. Post-harvest handling

Guidelines:
- Keep responses friendly and in simple language (English or light Kiswahili)
- Give practical, actionable advice smallholder farmers can implement
- Be encouraging and supportive
- If uncertain, suggest checking with local agricultural extension officers in {location_str}
- Be transparent about data limitations: mention if you're using seasonal patterns vs real-time data
- Keep responses concise and focused on the question asked"""

    # Get only the conversation history from this specific chat thread
    conversation_history = [msg.copy() for msg in (chat_thread.history or [])]

    # sanitize any legacy or invalid roles before sending to API
    allowed_roles = {'system', 'user', 'assistant'}
    for msg in conversation_history:
        role = msg.get('role')
        if role == 'model':
            msg['role'] = 'assistant'
            role = 'assistant'
        if role not in allowed_roles:
            logger.warning(f"Unexpected role '{role}' found in history; converting to 'assistant'.")
            msg['role'] = 'assistant'

    conversation_history.append({
        "role": "user",
        "content": user_message
    })
    
    # Update chat thread title if this is the first message
    if not chat_thread.history or len(chat_thread.history) == 0:
        # Generate a smart title from the first message
        chat_thread.title = generate_chat_title(user_message)
    
    # Prepare messages for API (add system message first, then only current chat history)
    api_messages = [{"role": "system", "content": system_prompt}] + conversation_history
    
    try:
        # Log comprehensive debug info about what data is being sent
        has_forecast = forecast_data and isinstance(forecast_data, list) and len(forecast_data) > 0
        has_soil = soil_data and isinstance(soil_data, dict) and 'error' not in soil_data
        data_sources = []
        if has_forecast:
            data_sources.append(f"forecast({len(forecast_data)} days)")
        if has_soil:
            data_sources.append(f"soil({soil_data.get('soil_moisture_top')}m³/m³)")
        data_status = ", ".join(data_sources) if data_sources else "no real-time data (using regional patterns)"
        
        logger.info(f"[ADVISOR DEBUG] Sending to Groq API: chat_thread={chat_thread.id}, farmer={farmer.fname}, location={location_str}, data_sources=[{data_status}], total_messages={len(api_messages)}")
        logger.debug(f"[ADVISOR DEBUG] System prompt length: {len(system_prompt)} chars")
        
        chat_completion = client.chat.completions.create(
            messages=api_messages,
            model="llama-3.3-70b-versatile",
            temperature=0.7,
            max_tokens=500,
        )
        
        advisor_response = chat_completion.choices[0].message.content.strip()
        logger.info(f"[ADVISOR DEBUG] Groq API responded successfully: {len(advisor_response)} chars")
        
        # Save the exchange to the current chat thread's history (not farmer history)
        conversation_history.append({
            "role": "assistant",
            "content": advisor_response
        })
        chat_thread.history = conversation_history
        chat_thread.save()
        
        return advisor_response
    
    except Exception as e:
        logger.error(f"[ADVISOR DEBUG] Groq API ERROR: {type(e).__name__}: {str(e)}")
        return f"Sorry, I encountered an error processing your message: {str(e)}"