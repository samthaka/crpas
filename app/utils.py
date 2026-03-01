import requests
from groq import Groq
from django.conf import settings
from datetime import datetime, timedelta

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
        chat_completion = client.chat.completions.create(
            messages=[
                {"role": "system", "content": "You are a helpful Kenyan farming advisor."},
                {"role": "user", "content": prompt},
            ],
            model="llama-3.3-70b-versatile",
            temperature=0.7,
            max_tokens=400,
        )
        advisory = chat_completion.choices[0].message.content.strip()

        # Optional: Save to history (adapt format)
        new_entry = [
            {"role": "user", "content": prompt},
            {"role": "model", "content": advisory}
        ]
        farmer.gemini_chat_history.extend(new_entry)  # Reuse field name or rename later
        farmer.save()

        return advisory
    except Exception as e:
        return f"Error generating advisory: {str(e)}"