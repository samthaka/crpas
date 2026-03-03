import logging
import requests
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

def reverse_geocode_coordinates(lat, lon):
    """
    Reverse geocode GPS coordinates to extract Kenya administrative divisions.
    Uses Nominatim (OpenStreetMap) - free API, no key required.
    
    Returns a dict with:
    {
        'county': 'County Name',
        'sub_county': 'Sub-County Name',
        'ward': 'Ward Name'
    }
    
    Returns None if geocoding fails.
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
            return None
        
        address = data.get('address', {})
        
        # Extract Kenya administrative divisions from OSM address tags
        # Nominatim uses different field names depending on the area:
        # Rural areas: state (county), county (sub-county), town/village/hamlet (ward)
        # Urban areas: state (region), city_district (sub-county), suburb (ward)
        
        # Extract County
        county = address.get('state')
        if county and not county.endswith(' County'):
            county = f"{county} County"
        
        # Extract Sub-County - try different field names
        sub_county = (address.get('county') or 
                     address.get('city_district') or
                     address.get('municipality'))
        
        # Extract Ward - try multiple field names
        ward = (address.get('town') or 
                address.get('village') or 
                address.get('hamlet') or 
                address.get('suburb') or
                address.get('neighbourhood') or
                address.get('locality') or
                address.get('district'))
        
        # Log what we're getting for debugging
        logger.debug(f"Full address from Nominatim: {address}")
        logger.debug(f"Extracted: county={county}, sub_county={sub_county}, ward={ward}")
        
        # Build result
        result = {}
        if county:
            result['county'] = county
            logger.info(f"Reverse geocoded county: {county}")
        if sub_county:
            result['sub_county'] = sub_county
            logger.info(f"Reverse geocoded sub-county: {sub_county}")
        if ward:
            result['ward'] = ward
            logger.info(f"Reverse geocoded ward: {ward}")
        
        if result:
            logger.info(f"Reverse geocoded ({lat}, {lon}) → {result}")
            return result
        else:
            logger.warning(f"Could not extract admin divisions from geocoding response: {address}")
            return None
            
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
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
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
        return forecast
    except Exception as e:
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
        response = requests.get(url, params=params)
        data = response.json()
        latest_hour = data['hourly']['time'][0]  # most recent
        idx = 0  # first (current)
        return {
            "soil_moisture_top": data['hourly']['soil_moisture_0_to_1cm'][idx],
            "soil_moisture_mid": data['hourly']['soil_moisture_9_to_27cm'][idx],
            "soil_moisture_deep": data['hourly']['soil_moisture_27_to_81cm'][idx],
            "soil_temp_surface": data['hourly']['soil_temperature_0cm'][idx],
            "soil_temp_mid": data['hourly']['soil_temperature_18cm'][idx],
            "timestamp": latest_hour,
        }
    except:
        return {"error": "Soil data fetch failed", "fallback": "Assume moderate moisture (0.25 m³/m³)"}


def generate_advisory(farmer, forecast_data, soil_data):
    """Use Groq with a strong free model for reasoning"""
    client = Groq(api_key=settings.GROQ_API_KEY)

    crop = "maize" if farmer.crop_type == 'maize' else "beans" if farmer.crop_type == 'beans' else "maize and beans intercropped"
    
    # Format forecast nicely for prompt
    forecast_str = "\n".join([f"{day['date']}: {day['rain_mm']}mm rain (prob {day['prob_max']}%), temp {day['temp_min']}-{day['temp_max']}°C" for day in forecast_data[:10]])

    prompt = f"""
You are an expert Kenyan agronomist advising smallholder farmers using local climate logic.
Your goal is to reduce false-start planting risk.

Farmer: {farmer.fname} {farmer.lname}
Location: {farmer.lat}, {farmer.long}
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
  "Habari {farmer.fname}! Ushauri wa Kupanda wa CRPAS:"
- Use simple English with light simple Kiswahili if helpful
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
        farmer.gemini_chat_history.extend(new_entry)  # Reuse field name or rename later
        farmer.save()

        return advisory
    except Exception as e:
        return f"Error generating advisory: {str(e)}"


def chat_with_advisor(farmer, chat_thread, user_message):
    """
    Handle conversational chat with the advisor about farming topics.
    Uses Groq to maintain context across multiple messages in the current chat thread.
    Only sends the system prompt + messages from the current chat thread to avoid context bloat.
    """
    if not GROQ_AVAILABLE:
        return "Sorry, the chat advisor is currently unavailable. Please ensure the Groq API is properly configured."
    
    client = Groq(api_key=settings.GROQ_API_KEY)
    
    crop = "maize" if farmer.crop_type == 'maize' else "beans" if farmer.crop_type == 'beans' else "maize and beans (intercropped)"
    
    # Build system prompt with farmer context
    system_prompt = f"""You are a friendly and knowledgeable Kenyan agricultural advisor helping farmers improve their farming practices.

Farmer Profile:
- Name: {farmer.fname} {farmer.lname}
- Location: {farmer.lat}, {farmer.long}
- Primary Crops: {crop}
- Sub-county: {farmer.sub_county}
- Ward: {farmer.ward}

Your role is to provide practical, localized farming advice about:
1. Crop selection and suitability for their location
2. Planting and harvesting times
3. Pest and disease management (especially for maize and beans)
4. Soil health and water management
5. Yield improvement techniques
6. Post-harvest handling

Guidelines:
- Keep responses friendly and in simple language (English or light Kiswahili mix is fine)
- Give practical, actionable advice that smallholder farmers can implement
- Consider Kenya's climate and local farming practices
- Be encouraging and supportive
- If uncertain, suggest they check with local agricultural extension officers
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
        # debug: log message sequence before request
        logger.debug(f"Sending messages to Groq API for chat thread {chat_thread.id}: {len(api_messages)} messages")
        chat_completion = client.chat.completions.create(
            messages=api_messages,
            model="llama-3.3-70b-versatile",
            temperature=0.7,
            max_tokens=500,
        )
        
        advisor_response = chat_completion.choices[0].message.content.strip()
        
        # Save the exchange to the current chat thread's history (not farmer history)
        conversation_history.append({
            "role": "assistant",
            "content": advisor_response
        })
        chat_thread.history = conversation_history
        chat_thread.save()
        
        return advisor_response
    
    except Exception as e:
        return f"Sorry, I encountered an error processing your message: {str(e)}"