"""
Risk Analysis Module - Uses Groq LLM to analyze weather data for environmental risks.
Detects risks of floods, pest infestation, and dry spells for both maize and beans.

METEOROLOGICAL THRESHOLDS:
- Flood Risk: Heavy rainfall events, high soil saturation
- Pest Risk: Warm + humid conditions (armyworm thrives at >20°C + 80% RH)
- Dry Spell Risk: Consecutive dry days (>7 days) during critical growth phases
"""

import json
import logging
from django.conf import settings
from groq import Groq

logger = logging.getLogger(__name__)

# ============================================================================
# METEOROLOGICAL THRESHOLDS & BASELINES
# ============================================================================

METEOROLOGICAL_THRESHOLDS = {
    'flood': {
        'daily_rainfall_mm': 20,  # Heavy rain threshold
        'consecutive_wet_days': 5,  # At least 5 days of rainfall
        'soil_saturation_threshold': 0.35,  # Soil moisture above 35% m³/m³
    },
    'pest': {
        'min_temperature_c': 20,  # Armyworm thrives above 20°C
        'min_humidity_percent': 80,  # Needs 80%+ humidity
        'rainfall_trigger_mm': 5,  # Recent rainfall triggering pest activity
        'warm_wet_days': 3,  # 3+ days of warm + wet = high pest risk
    },
    'dry_spell': {
        'consecutive_dry_days': 7,  # More than 7 dry days = dry spell
        'min_rainfall_daily': 2,  # Days with <2mm = considered dry
        'soil_moisture_critical_maize': 0.15,  # Critical for maize
        'soil_moisture_critical_beans': 0.20,  # Less critical for beans
    }
}

# CROP-SPECIFIC SENSITIVITIES
CROP_SENSITIVITIES = {
    'maize': {
        'flood': {
            'critical_stage': 'first 30 days after planting',
            'damage_severity': 'very high - causes root rot',
        },
        'pest': {
            'critical_pest': 'Fall armyworm (FAW)',
            'risk_period': 'vegetative stage', 
        },
        'dry_spell': {
            'critical_stage': 'first 30 days and flowering',
            'damage_severity': 'very high - false-start planting',
        }
    },
    'beans': {
        'flood': {
            'critical_stage': 'pod-filling stage',
            'damage_severity': 'medium - more tolerant than maize',
        },
        'pest': {
            'critical_pest': 'Bean bruchids',
            'risk_period': 'flowering and pod-filling',
        },
        'dry_spell': {
            'critical_stage': 'pod-filling',
            'damage_severity': 'medium - tolerates short dry spells',
        }
    }
}


def analyze_weather_for_risks(farm, forecast_data, soil_data):
    """
    Analyze weather data using Groq LLM to detect environmental risks.
    Uses meteorological thresholds to validate and adjust LLM probabilities.
    
    Args:
        farm (Farm): The farm being analyzed
        forecast_data (list): 10-day weather forecast from Open-Meteo
        soil_data (dict): Soil moisture and temperature data
        
    Returns:
        dict: {
            'success': bool,
            'risks': [
                {
                    'risk_type': 'flood|pest|dry_spell',
                    'affected_crop': 'maize|beans|both',
                    'risk_level': 'low|medium|high|critical',
                    'probability_score': 0-100,
                    'description': 'Why this risk was detected',
                    'recommendation': 'Action to take',
                    'meteorological_basis': 'Threshold trigger details'
                },
                ...
            ],
            'raw_response': 'Full LLM response'
        }
    """
    try:
        client = Groq(api_key=settings.GROQ_API_KEY)
        
        # Determine crop type
        if farm.crop_type == 'maize':
            crops = "maize"
        elif farm.crop_type == 'beans':
            crops = "beans"
        else:
            crops = "maize and beans (intercropped)"
        
        # Calculate meteorological indicators BEFORE sending to LLM
        met_indicators = _calculate_meteorological_indicators(forecast_data, soil_data)
        
        # Format forecast for analysis
        forecast_str = _format_forecast_for_analysis(forecast_data)
        
        # Format soil data for analysis
        soil_str = _format_soil_for_analysis(soil_data)
        
        # Build the risk analysis prompt with meteorological context
        prompt = _build_risk_analysis_prompt(farm, crops, forecast_str, soil_str, met_indicators)
        
        logger.info(f"[RISK ANALYSIS] Analyzing risks for farm {farm.id} ({crops})")
        logger.debug(f"[RISK ANALYSIS] Meteorological indicators: {met_indicators}")
        
        # Call Groq API
        response = client.chat.completions.create(
            messages=[
                {
                    "role": "system",
                    "content": "You are an expert agricultural climatologist analyzing weather conditions for crop risks. Use the provided meteorological thresholds and always respond with valid JSON."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            model="llama-3.3-70b-versatile",
            temperature=0.5,  # Lower temperature for more consistent analysis
            max_tokens=2000,
        )
        
        raw_response = response.choices[0].message.content.strip()
        logger.debug(f"[RISK ANALYSIS] Raw LLM response: {raw_response[:500]}...")
        
        # Parse the JSON response
        risks = _parse_risk_analysis_response(raw_response)
        
        # VALIDATE & ADJUST risks based on meteorological thresholds
        validated_risks = _validate_against_thresholds(risks, met_indicators, farm.crop_type)
        
        return {
            'success': True,
            'risks': validated_risks,
            'raw_response': raw_response,
            'meteorological_indicators': met_indicators
        }
        
    except json.JSONDecodeError as e:
        logger.error(f"[RISK ANALYSIS] Failed to parse LLM response as JSON: {str(e)}")
        return {
            'success': False,
            'risks': [],
            'error': f"Failed to parse LLM response: {str(e)}",
            'raw_response': raw_response if 'raw_response' in locals() else None
        }
    except Exception as e:
        logger.error(f"[RISK ANALYSIS] Error during risk analysis: {str(e)}")
        return {
            'success': False,
            'risks': [],
            'error': str(e)
        }


def _calculate_meteorological_indicators(forecast_data, soil_data):
    """
    Calculate meteorological indicators from raw data for threshold comparison.
    
    Returns:
        dict with indicators for flood, pest, and dry spell risks
    """
    indicators = {
        'flood': {},
        'pest': {},
        'dry_spell': {},
    }
    
    if not forecast_data or not isinstance(forecast_data, list):
        return indicators
    
    # Analyze next 14 days
    days_14 = forecast_data[:14] if len(forecast_data) >= 14 else forecast_data
    
    # FLOOD RISK INDICATORS
    total_rainfall_14d = sum(day.get('rain_mm', 0) for day in days_14)
    consecutive_wet_days = _count_consecutive_wet_days(days_14)
    heavy_rain_days = sum(1 for day in days_14 if day.get('rain_mm', 0) >= 20)
    
    indicators['flood'] = {
        'total_rainfall_14d_mm': round(total_rainfall_14d, 1),
        'consecutive_wet_days': consecutive_wet_days,
        'heavy_rain_days': heavy_rain_days,
        'avg_daily_rainfall_mm': round(total_rainfall_14d / len(days_14), 1) if days_14 else 0,
    }
    
    # Get soil moisture if available
    if soil_data and isinstance(soil_data, dict):
        soil_moisture_top = soil_data.get('soil_moisture_top')
        if soil_moisture_top:
            indicators['flood']['soil_moisture_top_m3m3'] = soil_moisture_top
    
    # PEST RISK INDICATORS
    warm_humid_days = 0
    avg_temp_c = 0
    temp_count = 0
    
    for day in days_14:
        temp_min = day.get('temp_min', 0)
        temp_max = day.get('temp_max', 0)
        rain_mm = day.get('rain_mm', 0)
        
        avg_temp = (temp_min + temp_max) / 2 if (temp_min and temp_max) else 0
        avg_temp_c += avg_temp
        temp_count += 1
        
        # Armyworm thrives: >20°C + humid (assume recent rain = humidity)
        if avg_temp > 20 and rain_mm >= 5:
            warm_humid_days += 1
    
    indicators['pest'] = {
        'avg_temp_c': round(avg_temp_c / temp_count, 1) if temp_count > 0 else 0,
        'warm_humid_days': warm_humid_days,
        'recent_rainfall': sum(day.get('rain_mm', 0) for day in days_14[:3]),  # Last 3 days
    }
    
    # DRY SPELL RISK INDICATORS
    consecutive_dry_days = _count_consecutive_dry_days(days_14)
    dry_day_threshold = 2  # mm
    dry_days_count = sum(1 for day in days_14 if day.get('rain_mm', 0) < dry_day_threshold)
    
    indicators['dry_spell'] = {
        'max_consecutive_dry_days': consecutive_dry_days,
        'total_dry_days_14d': dry_days_count,
        'total_rainfall_14d_mm': round(total_rainfall_14d, 1),
    }
    
    # Soil moisture for dry spell
    if soil_data and isinstance(soil_data, dict):
        soil_moisture_top = soil_data.get('soil_moisture_top')
        if soil_moisture_top:
            indicators['dry_spell']['soil_moisture_top_m3m3'] = soil_moisture_top
    
    return indicators


def _count_consecutive_wet_days(forecast_data, threshold_mm=2):
    """Count longest consecutive wet day sequence."""
    max_wet_days = 0
    current_wet_days = 0
    
    for day in forecast_data:
        rain_mm = day.get('rain_mm', 0)
        if rain_mm >= threshold_mm:
            current_wet_days += 1
            max_wet_days = max(max_wet_days, current_wet_days)
        else:
            current_wet_days = 0
    
    return max_wet_days


def _count_consecutive_dry_days(forecast_data, threshold_mm=2):
    """Count longest consecutive dry day sequence."""
    max_dry_days = 0
    current_dry_days = 0
    
    for day in forecast_data:
        rain_mm = day.get('rain_mm', 0)
        if rain_mm < threshold_mm:
            current_dry_days += 1
            max_dry_days = max(max_dry_days, current_dry_days)
        else:
            current_dry_days = 0
    
    return max_dry_days


def _validate_against_thresholds(risks, met_indicators, crop_type):
    """
    Validate LLM's risk assessments against meteorological thresholds.
    Adjusts probability scores if needed based on actual weather data.
    
    Args:
        risks (list): Risks from LLM
        met_indicators (dict): Calculated meteorological indicators
        crop_type (str): 'maize', 'beans', or 'maize_beans'
        
    Returns:
        list: Validated/adjusted risks
    """
    validated = []
    thresholds = METEOROLOGICAL_THRESHOLDS
    
    for risk in risks:
        risk_type = risk.get('risk_type')
        orig_score = risk.get('probability_score', 0)
        
        # Check thresholds for this risk type
        threshold_triggered = False
        threshold_info = ""
        
        if risk_type == 'flood':
            indicators = met_indicators.get('flood', {})
            # Multiple heavy rain days + wet period = flood risk
            if (indicators.get('heavy_rain_days', 0) >= 2 or 
                indicators.get('consecutive_wet_days', 0) >= thresholds['flood']['consecutive_wet_days']):
                threshold_triggered = True
                threshold_info = f"Heavy rainfall detected: {indicators.get('heavy_rain_days', 0)} days >20mm, {indicators.get('consecutive_wet_days', 0)} consecutive wet days"
                # Boost score if threshold triggered
                if orig_score < 60:
                    risk['probability_score'] = min(orig_score + 15, 85)
        
        elif risk_type == 'pest':
            indicators = met_indicators.get('pest', {})
            # Warm + wet conditions trigger pest risk
            if (indicators.get('avg_temp_c', 0) > thresholds['pest']['min_temperature_c'] and
                indicators.get('warm_humid_days', 0) >= thresholds['pest']['warm_wet_days']):
                threshold_triggered = True
                threshold_info = f"Armyworm conditions: {indicators.get('warm_humid_days', 0)} days >20°C + rain"
                if orig_score < 50:
                    risk['probability_score'] = min(orig_score + 20, 80)
        
        elif risk_type == 'dry_spell':
            indicators = met_indicators.get('dry_spell', {})
            # Long dry period = dry spell risk
            if indicators.get('max_consecutive_dry_days', 0) >= thresholds['dry_spell']['consecutive_dry_days']:
                threshold_triggered = True
                threshold_info = f"Dry spell risk: {indicators.get('max_consecutive_dry_days', 0)} consecutive dry days forecasted"
                if orig_score < 65:
                    risk['probability_score'] = min(orig_score + 20, 90)
        
        # Add threshold info to description
        if threshold_triggered:
            risk['meteorological_basis'] = threshold_info
            old_desc = risk.get('description', '')
            risk['description'] = f"{old_desc}\n\n[Meteorological validation: {threshold_info}]"
        
        validated.append(risk)
    
    return validated
    """
    Analyze weather data using Groq LLM to detect environmental risks.
    
    Args:
        farm (Farm): The farm being analyzed
        forecast_data (list): 10-day weather forecast from Open-Meteo
        soil_data (dict): Soil moisture and temperature data
        
    Returns:
        dict: {
            'success': bool,
            'risks': [
                {
                    'risk_type': 'flood|pest|dry_spell',
                    'affected_crop': 'maize|beans|both',
                    'risk_level': 'low|medium|high|critical',
                    'probability_score': 0-100,
                    'description': 'Why this risk was detected',
                    'recommendation': 'Action to take'
                },
                ...
            ],
            'raw_response': 'Full LLM response'
        }
    """
    try:
        client = Groq(api_key=settings.GROQ_API_KEY)
        
        # Determine crop type
        if farm.crop_type == 'maize':
            crops = "maize"
        elif farm.crop_type == 'beans':
            crops = "beans"
        else:
            crops = "maize and beans (intercropped)"
        
        # Format forecast for analysis
        forecast_str = _format_forecast_for_analysis(forecast_data)
        
        # Format soil data for analysis
        soil_str = _format_soil_for_analysis(soil_data)
        
        # Build the risk analysis prompt
        prompt = _build_risk_analysis_prompt(farm, crops, forecast_str, soil_str)
        
        logger.info(f"[RISK ANALYSIS] Analyzing risks for farm {farm.id} ({crops})")
        
        # Call Groq API
        response = client.chat.completions.create(
            messages=[
                {
                    "role": "system",
                    "content": "You are an expert agricultural climatologist analyzing weather conditions for crop risks. Always respond with valid JSON."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            model="llama-3.3-70b-versatile",
            temperature=0.5,  # Lower temperature for more consistent analysis
            max_tokens=2000,
        )
        
        raw_response = response.choices[0].message.content.strip()
        logger.debug(f"[RISK ANALYSIS] Raw LLM response: {raw_response[:500]}...")
        
        # Parse the JSON response
        risks = _parse_risk_analysis_response(raw_response)
        
        return {
            'success': True,
            'risks': risks,
            'raw_response': raw_response
        }
        
    except json.JSONDecodeError as e:
        logger.error(f"[RISK ANALYSIS] Failed to parse LLM response as JSON: {str(e)}")
        return {
            'success': False,
            'risks': [],
            'error': f"Failed to parse LLM response: {str(e)}",
            'raw_response': raw_response if 'raw_response' in locals() else None
        }
    except Exception as e:
        logger.error(f"[RISK ANALYSIS] Error during risk analysis: {str(e)}")
        return {
            'success': False,
            'risks': [],
            'error': str(e)
        }


def _format_forecast_for_analysis(forecast_data):
    """Format forecast data for the prompt."""
    if not forecast_data or not isinstance(forecast_data, list):
        return "No forecast data available"
    
    lines = []
    for day in forecast_data[:14]:  # Analyze 14 days
        try:
            date = day.get('date', 'N/A')
            rain = day.get('rain_mm', 0)
            prob = day.get('prob_max', 0)
            temp_min = day.get('temp_min', 'N/A')
            temp_max = day.get('temp_max', 'N/A')
            wind = day.get('wind_speed_max', 'N/A')
            
            line = f"- {date}: {rain}mm rain (prob {prob}%), temp {temp_min}°C-{temp_max}°C, wind {wind}km/h"
            lines.append(line)
        except (KeyError, TypeError):
            continue
    
    return "\n".join(lines) if lines else "No forecast data available"


def _format_soil_for_analysis(soil_data):
    """Format soil data for the prompt."""
    if not soil_data or not isinstance(soil_data, dict) or 'error' in soil_data:
        return "No real-time soil data available"
    
    try:
        lines = [
            f"- Top layer moisture: {soil_data.get('soil_moisture_top', 'N/A')} m³/m³",
            f"- Mid layer moisture: {soil_data.get('soil_moisture_mid', 'N/A')} m³/m³",
            f"- Deep layer moisture: {soil_data.get('soil_moisture_deep', 'N/A')} m³/m³",
            f"- Surface temperature: {soil_data.get('soil_temp_surface', 'N/A')}°C",
        ]
        return "\n".join(lines)
    except Exception as e:
        logger.warning(f"Error formatting soil data: {str(e)}")
        return "No real-time soil data available"


def _build_risk_analysis_prompt(farm, crops, forecast_str, soil_str, met_indicators):
    """
    Build the comprehensive risk analysis prompt with meteorological thresholds.
    
    Args:
        farm: Farm object
        crops: Crop type string
        forecast_str: Formatted forecast data
        soil_str: Formatted soil data
        met_indicators: Pre-calculated meteorological indicators
    """
    location = f"{farm.ward or 'N/A'}, {farm.sub_county or 'N/A'}, {farm.county or 'N/A'}"
    
    # Format meteorological indicators for the prompt
    flood_ind = met_indicators.get('flood', {})
    pest_ind = met_indicators.get('pest', {})
    dry_ind = met_indicators.get('dry_spell', {})
    
    met_summary = f"""
METEOROLOGICAL INDICATORS (Pre-calculated):
- Flood: Total rainfall (14d)={flood_ind.get('total_rainfall_14d_mm', 'N/A')}mm, Heavy rain days={flood_ind.get('heavy_rain_days', 'N/A')}, Consecutive wet days={flood_ind.get('consecutive_wet_days', 'N/A')}
- Pest: Avg temp={pest_ind.get('avg_temp_c', 'N/A')}°C, Warm+humid days={pest_ind.get('warm_humid_days', 'N/A')}
- Dry Spell: Max consecutive dry days={dry_ind.get('max_consecutive_dry_days', 'N/A')}, Total dry days={dry_ind.get('total_dry_days_14d', 'N/A')}
"""
    
    prompt = f"""Analyze the following weather conditions for a farm in Kenya to identify environmental risks.

FARM INFORMATION:
- Location: {location}
- GPS: {farm.lat}°N, {farm.long}°E
- Crops: {crops}
- Farm Size: {farm.farm_size} acres

CURRENT SOIL CONDITIONS:
{soil_str}

14-DAY WEATHER FORECAST:
{forecast_str}

{met_summary}

METEOROLOGICAL THRESHOLDS TO APPLY:
1. FLOOD RISK activated when: ≥2 days with >20mm rainfall OR ≥5 consecutive wet days
2. PEST RISK activated when: Avg temp >20°C AND ≥3 days with both warmth + recent rain
3. DRY SPELL RISK activated when: ≥7 consecutive dry days (<2mm rainfall)

ANALYSIS TASK:
Based on the weather forecast, soil conditions, and meteorological indicators, identify and assess these three risks:

1. **FLOOD RISK** - Probability of excessive rainfall causing waterlogging or flooding
   - THRESHOLD CHECK: {flood_ind.get('heavy_rain_days', 0)} heavy rain days, {flood_ind.get('consecutive_wet_days', 0)} consecutive wet days
   - For Maize: Flooding 5-30 days after planting causes root rot - VERY DAMAGING
   - For Beans: More tolerant but wet-dry cycles increase fungal diseases
   - Soil saturation indicates inability to drain: {flood_ind.get('soil_moisture_top_m3m3', 'unavailable')}

2. **PEST INFESTATION RISK** - Probability of pest outbreak (Fall armyworm mainly)
   - THRESHOLD CHECK: {pest_ind.get('avg_temp_c', '?')}°C avg temp, {pest_ind.get('warm_humid_days', 0)} warm+wet days
   - Armyworm thrives when >20°C + humid (activated at threshold: {pest_ind.get('warm_humid_days', 0)} ≥ 3 days)
   - For Maize: Fall armyworm causes major damage in warm, wet periods
   - For Beans: Less vulnerable; focus on bean bruchids

3. **DRY SPELL RISK** - Probability of prolonged dry period causing water stress
   - THRESHOLD CHECK: {dry_ind.get('max_consecutive_dry_days', 0)} consecutive dry days (threshold = 7 days)
   - For Maize: CRITICAL in first 30 days; false-start planting with dry spell after = crop failure
   - For Beans: More tolerant but vulnerable during pod-filling stage
   - Soil moisture: {dry_ind.get('soil_moisture_top_m3m3', 'unavailable')} m³/m³

OUTPUT REQUIREMENTS:
Return VALID JSON with exactly this structure (no markdown, just valid JSON):

{{
  "risks": [
    {{
      "risk_type": "flood|pest|dry_spell",
      "affected_crop": "maize|beans|both",
      "risk_level": "low|medium|high|critical",
      "probability_score": NUMBER_0_TO_100,
      "description": "Detailed explanation of why this risk exists based on the data and thresholds",
      "recommendation": "Specific action to mitigate this risk"
    }}
  ],
  "summary": "Brief overall risk assessment for this farm"
}}

SCORING RULES:
- 0-30: LOW (thresholds not met or minimal weather risk)
- 31-60: MEDIUM (some threshold indicators triggered)
- 61-85: HIGH (multiple thresholds met or strong indicators)
- 86-100: CRITICAL (all thresholds exceeded or imminent threat)

CRITICAL REQUIREMENTS:
- Analyze ONLY for the specific crops grown on this farm ({crops})
- Use BOTH forecast data AND meteorological thresholds in your assessment
- If threshold IS triggered: assign at least HIGH (65+) probability
- If threshold NOT triggered: assign LOW to MEDIUM probability
- Be specific: cite exact rainfall amounts, dates, temperatures
- Always include ALL three risks in output (low score if not applicable)
- Return ONLY valid JSON, no explanations or markdown
"""
    
    return prompt


def _parse_risk_analysis_response(response_text):
    """
    Parse the LLM's JSON response and extract risk data.
    
    Args:
        response_text (str): The raw LLM response
        
    Returns:
        list: List of risk dictionaries
    """
    try:
        # Try to extract JSON from the response
        # Sometimes LLM might wrap it in markdown code blocks
        if "```json" in response_text:
            json_str = response_text.split("```json")[1].split("```")[0].strip()
        elif "```" in response_text:
            json_str = response_text.split("```")[1].split("```")[0].strip()
        else:
            json_str = response_text.strip()
        
        data = json.loads(json_str)
        
        # Validate and normalize the response
        risks = data.get('risks', [])
        
        # Validate each risk object
        validated_risks = []
        for risk in risks:
            if _validate_risk_object(risk):
                validated_risks.append(risk)
            else:
                logger.warning(f"Invalid risk object skipped: {risk}")
        
        logger.info(f"[RISK ANALYSIS] Successfully parsed {len(validated_risks)} risks from LLM response")
        return validated_risks
        
    except json.JSONDecodeError as e:
        logger.error(f"[RISK ANALYSIS] JSON parsing error: {str(e)}")
        logger.debug(f"[RISK ANALYSIS] Response text: {response_text[:500]}")
        raise


def _validate_risk_object(risk):
    """Validate that a risk object has all required fields."""
    required_fields = ['risk_type', 'affected_crop', 'risk_level', 'probability_score', 'description', 'recommendation']
    
    for field in required_fields:
        if field not in risk:
            logger.warning(f"Risk object missing required field: {field}")
            return False
    
    # Validate field values
    valid_risk_types = ['flood', 'pest', 'dry_spell']
    valid_crops = ['maize', 'beans', 'both']
    valid_levels = ['low', 'medium', 'high', 'critical']
    
    if risk.get('risk_type') not in valid_risk_types:
        logger.warning(f"Invalid risk_type: {risk.get('risk_type')}")
        return False
    
    if risk.get('affected_crop') not in valid_crops:
        logger.warning(f"Invalid affected_crop: {risk.get('affected_crop')}")
        return False
    
    if risk.get('risk_level') not in valid_levels:
        logger.warning(f"Invalid risk_level: {risk.get('risk_level')}")
        return False
    
    # Validate probability score
    try:
        score = int(risk.get('probability_score', 0))
        if not (0 <= score <= 100):
            logger.warning(f"Probability score out of range: {score}")
            return False
    except (ValueError, TypeError):
        logger.warning(f"Invalid probability_score: {risk.get('probability_score')}")
        return False
    
    return True


def generate_personalized_risk_notification(farmer, farm, risk_alert):
    """
    Generate a personalized notification message for a detected risk.
    Formats for SMS/Email (no markdown - direct text formatting).
    
    Args:
        farmer (Farmer): The farmer receiving the notification
        farm (Farm): The affected farm
        risk_alert (RiskAlert): The risk alert object
        
    Returns:
        dict: {'title': 'string', 'message': 'string'}
    """
    risk_type = risk_alert.get_risk_type_display()
    risk_level = risk_alert.get_risk_level_display()
    crop = "Maize" if farm.crop_type == 'maize' else "Beans" if farm.crop_type == 'beans' else "Your crops"
    
    # Build title
    if risk_alert.risk_level == 'critical':
        emoji = "🚨"
        urgent = "URGENT"
    elif risk_alert.risk_level == 'high':
        emoji = "⚠️"
        urgent = "Warning"
    elif risk_alert.risk_level == 'medium':
        emoji = "ℹ️"
        urgent = "Alert"
    else:
        emoji = "📋"
        urgent = "Notice"
    
    title = f"{emoji} {urgent}: {risk_type} Risk for {crop}"
    
    # Build message with personalization - SMS/Email friendly (no markdown)
    message = f"""Habari {farmer.fname}!

Our CRPAS system has detected a potential {risk_level.lower()} risk level for your {crop} farm in {farm.ward or farm.sub_county or farm.county}.

RISK DETAILS:
Type: {risk_type}
Crops Affected: {farm.get_crop_type_display()}

SITUATION:
{risk_alert.description}

RECOMMENDED ACTION:
{risk_alert.recommendation}

Risk Probability: {risk_alert.probability_score}% (based on weather analysis)

For more details, visit your CRPAS dashboard or contact your local agricultural extension office.

Stay safe! 🌾"""
    
    return {
        'title': title,
        'message': message
    }
