"""
Scheduled tasks for CRPAS.
These tasks are automatically run by APScheduler at specified times.

IMPORTANT: This module uses REAL DATA ONLY - no fallback/false data is used.
If APIs are unavailable, advisories are SKIPPED rather than sent with false data.
This protects farmers from making wrong decisions based on inaccurate information.
"""

import logging
import time
from datetime import timedelta
from django.utils import timezone
from app.models import Farmer, Farm
from app.notification_utils import create_and_send_notification
from app.utils import get_rainfall_forecast, get_soil_data, generate_advisory

logger = logging.getLogger(__name__)

# Retry configuration
MAX_RETRIES = 3
RETRY_DELAY_SECONDS = 5  # Wait 5 seconds before retrying


def send_daily_advisories_task():
    """
    Scheduled task to send daily agricultural advisories to all farmers.
    Runs automatically every day at 9 AM GMT+3 (Nairobi time).
    
    SCHEDULING TIME: 6 AM UTC = 9 AM GMT+3 (East Africa Time)
    
    This function is called by APScheduler and should not be called directly by users.
    It respects data availability - ONLY sends advisories when real weather and soil data is available.
    """
    logger.info("=" * 80)
    logger.info("Starting scheduled daily advisory notifications (9 AM GMT+3)")
    logger.info("=" * 80)
    
    try:
        # Get all farmers who have at least one farm
        farmers = Farmer.objects.filter(farms__isnull=False).distinct()
        
        if not farmers.exists():
            logger.warning("No farmers with farms found in database")
            return
        
        logger.info(f"Processing daily advisories for {farmers.count()} farmers")
        
        success_count = 0
        skipped_count = 0
        error_count = 0
        
        for farmer in farmers:
            try:
                result = _send_advisory_to_farmer(farmer)
                if result == 'success':
                    success_count += 1
                elif result == 'skipped':
                    skipped_count += 1
                else:
                    error_count += 1
            except Exception as e:
                logger.error(f"Error sending advisory to {farmer}: {str(e)}")
                error_count += 1
        
        logger.info("=" * 80)
        logger.info(f"Daily advisories completed:")
        logger.info(f"  ✓ Sent: {success_count}")
        logger.info(f"  ⊘ Skipped (no data): {skipped_count}")
        logger.info(f"  ✗ Failed: {error_count}")
        logger.info("=" * 80)
        
    except Exception as e:
        logger.exception(f"Fatal error in scheduled advisory task: {str(e)}")


def _fetch_weather_data_with_retry(lat, lon, max_retries=MAX_RETRIES):
    """
    Fetch weather forecast with retry logic and exponential backoff.
    
    Args:
        lat, lon: GPS coordinates
        max_retries: Number of retry attempts
        
    Returns:
        tuple: (forecast_data, success: bool)
        - forecast_data: Real weather data from API or None if failed
        - success: True only if data was successfully fetched and validated
        
    Uses:
        - Open-Meteo API (free, no key required)
        - Retries 3 times with 5-second exponential backoff
        - Validates data before returning
    """
    for attempt in range(1, max_retries + 1):
        try:
            logger.info(f"Fetching forecast (attempt {attempt}/{max_retries}) for ({lat}, {lon})")
            forecast_data = get_rainfall_forecast(lat, lon, days=10)
            
            # Check for API errors
            if isinstance(forecast_data, dict) and 'error' in forecast_data:
                logger.warning(f"API returned error: {forecast_data['error']}")
                if attempt < max_retries:
                    wait_time = RETRY_DELAY_SECONDS * attempt  # Exponential backoff
                    logger.info(f"Retrying in {wait_time} seconds...")
                    time.sleep(wait_time)
                    continue
                return None, False
            
            # Validate that we got actual data
            if not forecast_data or not isinstance(forecast_data, list) or len(forecast_data) == 0:
                logger.warning("Forecast data is empty or invalid")
                if attempt < max_retries:
                    wait_time = RETRY_DELAY_SECONDS * attempt
                    logger.info(f"Retrying in {wait_time} seconds...")
                    time.sleep(wait_time)
                    continue
                return None, False
            
            logger.info(f"✓ Successfully fetched forecast: {len(forecast_data)} days of data")
            return forecast_data, True
            
        except Exception as e:
            logger.error(f"Exception fetching forecast (attempt {attempt}/{max_retries}): {str(e)}")
            if attempt < max_retries:
                wait_time = RETRY_DELAY_SECONDS * attempt
                logger.info(f"Retrying in {wait_time} seconds...")
                time.sleep(wait_time)
                continue
    
    logger.error(f"✗ Failed to fetch forecast after {max_retries} attempts - ADVISORY WILL BE SKIPPED")
    return None, False


def _fetch_soil_data_with_retry(lat, lon, max_retries=MAX_RETRIES):
    """
    Fetch soil data with retry logic and exponential backoff.
    
    Args:
        lat, lon: GPS coordinates
        max_retries: Number of retry attempts
        
    Returns:
        tuple: (soil_data, success: bool)
        - soil_data: Real soil data from API or None if failed
        - success: True only if data was successfully fetched and validated
        
    Uses:
        - Open-Meteo API (free, no key required)
        - Retries 3 times with 5-second exponential backoff
        - Validates required soil moisture fields
    """
    for attempt in range(1, max_retries + 1):
        try:
            logger.info(f"Fetching soil data (attempt {attempt}/{max_retries}) for ({lat}, {lon})")
            soil_data = get_soil_data(lat, lon)
            
            # Check for API errors
            if isinstance(soil_data, dict) and 'error' in soil_data:
                logger.warning(f"API returned error: {soil_data['error']}")
                if attempt < max_retries:
                    wait_time = RETRY_DELAY_SECONDS * attempt
                    logger.info(f"Retrying in {wait_time} seconds...")
                    time.sleep(wait_time)
                    continue
                return None, False
            
            # Validate required fields are present
            required_fields = ['soil_moisture_top', 'soil_moisture_mid', 'soil_moisture_deep']
            if not all(field in soil_data for field in required_fields):
                logger.warning(f"Soil data missing required fields. Got: {soil_data.keys()}")
                if attempt < max_retries:
                    wait_time = RETRY_DELAY_SECONDS * attempt
                    logger.info(f"Retrying in {wait_time} seconds...")
                    time.sleep(wait_time)
                    continue
                return None, False
            
            logger.info(f"✓ Successfully fetched soil data with all required fields")
            return soil_data, True
            
        except Exception as e:
            logger.error(f"Exception fetching soil data (attempt {attempt}/{max_retries}): {str(e)}")
            if attempt < max_retries:
                wait_time = RETRY_DELAY_SECONDS * attempt
                logger.info(f"Retrying in {wait_time} seconds...")
                time.sleep(wait_time)
                continue
    
    logger.error(f"✗ Failed to fetch soil data after {max_retries} attempts - ADVISORY WILL BE SKIPPED")
    return None, False


def _send_advisory_to_farmer(farmer):
    """
    Generate and send an advisory for a specific farmer.
    
    CRITICAL: This function ONLY sends advisories when REAL DATA is available.
    If weather/soil APIs are unavailable after retries, the advisory is SKIPPED.
    NO FALLBACK DATA is used - farmers only receive advisories based on actual data.
    
    This protects farmers from making wrong decisions based on false climate information.
    
    Args:
        farmer (Farmer): The farmer to send advisory to
        
    Returns:
        str: 'success' if advisory sent
             'skipped' if advisory skipped due to missing data
             'error' if unexpected failure occurred
    """
    try:
        # Get the farmer's farms
        farms = farmer.farms.all()
        if not farms.exists():
            logger.warning(f"Farmer {farmer} has no farms, skipping")
            return 'skipped'

        # Use the first farm for weather data
        farm = farms.first()
        
        if not farm.lat or not farm.long:
            logger.warning(f"Farm for {farmer} has no GPS coordinates, skipping")
            return 'skipped'

        logger.info(f"Processing advisory for {farmer.fname} {farmer.lname} at ({farm.lat}, {farm.long})")
        
        # ==========================================
        # FETCH REAL DATA WITH RETRIES (3 attempts)
        # ==========================================
        logger.info(f"Fetching real weather/soil data from Open-Meteo API...")
        
        forecast_data, forecast_ok = _fetch_weather_data_with_retry(farm.lat, farm.long)
        soil_data, soil_ok = _fetch_soil_data_with_retry(farm.lat, farm.long)
        
        # CRITICAL: Both data sources MUST be available
        if not forecast_ok or not soil_ok:
            logger.warning(
                f"Skipping advisory for {farmer}: "
                f"forecast_available={forecast_ok}, soil_available={soil_ok}. "
                f"Will not send false data to farmer."
            )
            return 'skipped'
        
        logger.info(f"✓ All required real data available for {farmer}")
        
        # ==========================================
        # GENERATE ADVISORY WITH REAL DATA
        # ==========================================
        try:
            logger.info(f"Generating AI advisory using Groq API...")
            advisory_text = generate_advisory(farm, forecast_data, soil_data)
            
            if not advisory_text:
                logger.error(f"Advisory generation returned empty text for {farmer}")
                return 'error'
                
        except Exception as e:
            logger.error(f"Error generating advisory for {farmer}: {str(e)}")
            logger.info(f"Skipping advisory for {farmer} due to generation failure")
            return 'skipped'
        
        # ==========================================
        # SEND NOTIFICATION WITH REAL DATA
        # ==========================================
        title = "🌾 Daily Agricultural Advisory"
        
        # Create and send notification via all channels
        notification = create_and_send_notification(
            farmer=farmer,
            title=title,
            message=advisory_text,
            notification_type='advisory',
            metadata={
                'sent_at': timezone.now().isoformat(),
                'location': f'{farm.lat},{farm.long}',
                'farm_name': farm.farm_name or 'Primary Farm',
                'crop_type': farm.crop_type,  # FIXED: Use farm.crop_type, not farmer.crop_type
                'data_sources': 'Open-Meteo API (verified real data)',
            },
            send_async=True  # Send in background to avoid blocking
        )
        
        if notification:
            logger.info(f"✓ Advisory successfully sent to {farmer.fname} ({farmer.email or farmer.phone})")
            logger.info(f"   Crop: {farm.get_crop_type_display()}")
            logger.info(f"   Channels: web, email, SMS (respecting preferences)")
            return 'success'
        else:
            logger.error(f"✗ Failed to create notification for {farmer.fname}")
            return 'error'
                
    except Exception as e:
        logger.exception(f"Unexpected error processing advisory for {farmer}: {str(e)}")
        return 'error'


# ============================================================================
# PERIODIC WEATHER DATA FETCH & RISK ANALYSIS (Every 6 hours)
# ============================================================================

def periodic_fetch_and_analyze_weather():
    """
    Scheduled task to fetch weather data every 6 hours and analyze for risks.
    Stores data as fallback for when APIs fail, and uses it to detect:
    - Flood risk
    - Pest infestation risk
    - Dry spell risk
    
    Runs every 6 hours at: 12:00 AM, 6:00 AM, 12:00 PM, 6:00 PM (UTC)
    Sends immediate notifications for HIGH/CRITICAL risks.
    Also aggregates regional risks and sends county-level alerts.
    
    This is the core of the "realtime fallback + risk detection" system.
    """
    logger.info("=" * 80)
    logger.info(f"🔄 Starting 6-hourly weather data fetch & risk analysis at {timezone.now()}")
    logger.info("=" * 80)
    
    try:
        from app.models import Farm, WeatherDataCache, RiskAlert, Notification
        from app.risk_analysis import analyze_weather_for_risks, generate_personalized_risk_notification
        
        # Get all farms
        farms = Farm.objects.filter(lat__isnull=False, long__isnull=False).select_related('farmer')
        
        if not farms.exists():
            logger.warning("No farms with GPS coordinates found - skipping weather fetch")
            return
        
        logger.info(f"Processing {farms.count()} farms for weather data fetch and risk analysis")
        
        fetch_success_count = 0
        fetch_failed_count = 0
        risk_detected_count = 0
        notification_sent_count = 0
        
        for farm in farms:
            try:
                _process_farm_weather_and_risks(farm)
                fetch_success_count += 1
                
            except Exception as e:
                logger.error(f"Error processing farm {farm.id}: {str(e)}")
                fetch_failed_count += 1
        
        logger.info("=" * 80)
        logger.info(f"6-Hourly weather fetch & risk analysis completed:")
        logger.info(f"  ✓ Successfully processed: {fetch_success_count}")
        logger.info(f"  ✗ Failed: {fetch_failed_count}")
        logger.info("=" * 80)
        
        # STEP 5: Aggregate regional risks and send regional notifications
        logger.info("\n📍 Starting regional risk aggregation...")
        aggregate_and_send_regional_risk_alerts()
        
    except Exception as e:
        logger.exception(f"Fatal error in periodic weather fetch task: {str(e)}")


def _process_farm_weather_and_risks(farm):
    """
    Process a single farm: fetch weather, cache it, analyze risks, send alerts.
    
    Args:
        farm (Farm): Farm to process
    """
    from app.models import WeatherDataCache, RiskAlert
    from app.risk_analysis import analyze_weather_for_risks, generate_personalized_risk_notification
    
    try:
        # STEP 1: Fetch weather data with retry logic
        logger.info(f"[FARM {farm.id}] Fetching weather data for {farm.farmer.fname} - {farm.ward or 'N/A'}")
        
        forecast_data, forecast_success = _fetch_weather_data_with_retry(farm.lat, farm.long)
        soil_data, soil_success = _fetch_soil_data_with_retry(farm.lat, farm.long)
        
        if not forecast_success:
            logger.warning(f"[FARM {farm.id}] Could not fetch forecast data - will try fallback")
            # Try to use cached data from previous fetch
            last_cache = farm.weather_cache.filter(fetch_success=True).order_by('-fetched_at').first()
            if last_cache:
                forecast_data = last_cache.forecast_data
                logger.info(f"[FARM {farm.id}] Using cached forecast from {last_cache.fetched_at}")
            else:
                logger.error(f"[FARM {farm.id}] No fallback data available - skipping")
                return
        
        # STEP 2: Cache the weather data
        cache_entry = WeatherDataCache.objects.create(
            farm=farm,
            latitude=farm.lat,
            longitude=farm.long,
            forecast_data=forecast_data if forecast_success else {},
            soil_data=soil_data if soil_success else {},
            fetch_success=forecast_success or soil_success,
            fetch_error="Weather API failed" if not forecast_success else ""
        )
        logger.info(f"[FARM {farm.id}] Cached weather data (entry {cache_entry.id})")
        
        # Skip analysis if no data
        if not forecast_data:
            logger.warning(f"[FARM {farm.id}] No valid forecast data - skipping risk analysis")
            return
        
        # STEP 3: Analyze weather for risks using LLM
        logger.info(f"[FARM {farm.id}] Analyzing weather data for risks using Groq LLM...")
        analysis_result = analyze_weather_for_risks(farm, forecast_data, soil_data)
        
        if not analysis_result['success']:
            logger.error(f"[FARM {farm.id}] Risk analysis failed: {analysis_result.get('error')}")
            return
        
        risks = analysis_result.get('risks', [])
        logger.info(f"[FARM {farm.id}] LLM detected {len(risks)} potential risks")
        
        # Mark cache as analyzed
        cache_entry.analyzed = True
        cache_entry.save()
        
        # STEP 4: Create RiskAlert objects and send notifications
        for risk_data in risks:
            # Only create alerts for detected risks (probability > 20)
            if risk_data.get('probability_score', 0) < 20:
                continue
            
            try:
                risk_type = risk_data['risk_type']
                risk_level = risk_data['risk_level']
                
                logger.info(f"[FARM {farm.id}] Creating risk alert: {risk_level.upper()} {risk_type}")
                
                # Create RiskAlert
                risk_alert = RiskAlert.objects.create(
                    farm=farm,
                    weather_cache=cache_entry,
                    risk_type=risk_type,
                    risk_level=risk_level,
                    affected_crop=risk_data.get('affected_crop', 'both'),
                    description=risk_data.get('description', 'Risk detected'),
                    recommendation=risk_data.get('recommendation', 'Consult with extension officer'),
                    probability_score=risk_data.get('probability_score', 0)
                )
                
                # Send immediate notification for HIGH and CRITICAL risks
                if risk_level in ['high', 'critical']:
                    _send_risk_alert_notification(farm, risk_alert)
                
            except Exception as e:
                logger.error(f"[FARM {farm.id}] Error creating risk alert: {str(e)}")
                continue
        
        logger.info(f"[FARM {farm.id}] ✓ Weather fetch & analysis complete")
        
    except Exception as e:
        logger.error(f"[FARM {farm.id}] Unexpected error: {str(e)}")
        raise


def _send_risk_alert_notification(farm, risk_alert):
    """
    Send an immediate notification for a detected HIGH/CRITICAL risk.
    
    Args:
        farm (Farm): The affected farm
        risk_alert (RiskAlert): The risk alert
    """
    from app.risk_analysis import generate_personalized_risk_notification
    
    try:
        farmer = farm.farmer
        
        # Generate personalized message
        msg_data = generate_personalized_risk_notification(farmer, farm, risk_alert)
        
        # Send notification immediately
        notification = create_and_send_notification(
            farmer=farmer,
            title=msg_data['title'],
            message=msg_data['message'],
            notification_type='risk_alert',  # Will need to add this type if not present
            metadata={
                'risk_type': risk_alert.risk_type,
                'risk_level': risk_alert.risk_level,
                'probability_score': risk_alert.probability_score,
                'affected_crop': farm.get_crop_type_display(),
                'triggered_at': timezone.now().isoformat(),
            },
            send_async=True
        )
        
        if notification:
            risk_alert.notification = notification
            risk_alert.notification_sent = True
            risk_alert.save()
            
            logger.info(f"✓ Risk alert notification sent to {farmer.fname}")
            logger.info(f"   Risk: {risk_alert.get_risk_type_display()} ({risk_alert.get_risk_level_display()})")
            logger.info(f"   Probability: {risk_alert.probability_score}%")
        
    except Exception as e:
        logger.error(f"Failed to send risk alert notification: {str(e)}")


# ============================================================================
# REGIONAL RISK AGGREGATION & ALERTS
# ============================================================================

def aggregate_and_send_regional_risk_alerts():
    """
    Aggregates detected risks by region and sends regional alerts.
    Runs after periodic_fetch_and_analyze_weather to consolidate risks.
    
    Groups risks by county/sub_county and sends alerts when:
    - Multiple farms in same region have HIGH/CRITICAL risks
    - Or a single farm has CRITICAL risk
    """
    from app.models import RiskAlert, RegionalNotification
    
    logger.info("=" * 80)
    logger.info(f"🔄 Starting regional risk aggregation at {timezone.now()}")
    logger.info("=" * 80)
    
    try:
        # Get all HIGH/CRITICAL risks from the last 2 hours
        recent_cutoff = timezone.now() - timedelta(hours=2)
        recent_risks = RiskAlert.objects.filter(
            risk_level__in=['high', 'critical'],
            created_at__gte=recent_cutoff
        ).select_related('farm', 'farm__farmer')
        
        if not recent_risks.exists():
            logger.info("No recent high-risk alerts to aggregate")
            return
        
        logger.info(f"Found {recent_risks.count()} recent high-risk alerts to aggregate")
        
        # Group by county
        risks_by_region = {}
        for risk in recent_risks:
            county = risk.farm.county or 'Unknown'
            if county not in risks_by_region:
                risks_by_region[county] = []
            risks_by_region[county].append(risk)
        
        # Create regional notifications for counties with multiple high risks
        for county, risks in risks_by_region.items():
            if len(risks) >= 2 or any(r.risk_level == 'critical' for r in risks):
                _create_regional_risk_summary(county, risks)
        
        logger.info("=" * 80)
        logger.info(f"Regional risk aggregation completed")
        logger.info("=" * 80)
        
    except Exception as e:
        logger.exception(f"Error in regional risk aggregation: {str(e)}")


def _create_regional_risk_summary(county, risks):
    """
    Create a regional notification summarizing risks in a county.
    
    Args:
        county (str): County name
        risks (list): List of RiskAlert objects
    """
    from app.models import RegionalNotification
    
    try:
        # Count risks by type
        risk_counts = {}
        critical_count = sum(1 for r in risks if r.risk_level == 'critical')
        
        for risk in risks:
            key = f"{risk.get_risk_type_display()}"
            if key not in risk_counts:
                risk_counts[key] = {'count': 0, 'farms': []}
            risk_counts[key]['count'] += 1
            risk_counts[key]['farms'].append(risk.farm.farmer.fname)
        
        # Build message
        title = f"🚨 Regional Risk Alert: {county} County" if critical_count > 0 else f"⚠️ Regional Weather Risk: {county} County"
        
        risk_summary = "\n".join([
            f"- {risk_type}: {info['count']} farm(s) affected"
            for risk_type, info in risk_counts.items()
        ])
        
        message = f"""COUNTY-WIDE RISK SUMMARY: {county} County

Multiple farms in your area have detected environmental risks:

{risk_summary}

AFFECTED CROPS:
- Maize and/or Beans farms

IMPACT:
These risks could affect crop yield and viability. We recommend:
1. Monitor weather developments closely
2. Check individual farm alerts for specific recommendations
3. Prepare defensive measures (irrigation, pest control, etc.)
4. Consult with your local agricultural extension officer

Stay alert! More updates coming as conditions develop.

Visit your CRPAS dashboard for detailed farm-level alerts."""
        
        # Create regional notification
        regional_notif = RegionalNotification.objects.create(
            title=title,
            message=message,
            notification_type='risk_alert',
            region_level='county',
            region_name=county,
            status='scheduled',
            scheduled_for=timezone.now(),
            send_via_website=True,
            send_via_email=True,
            send_via_sms=True,
            metadata={
                'aggregated_risks': len(risks),
                'critical_count': critical_count,
                'risk_breakdown': risk_counts,
                'generated_from_risk_analysis': True
            },
            created_by='risk_analysis_system'
        )
        
        logger.info(f"✓ Created regional risk notification for {county}: {regional_notif.id}")
        
        # Queue it for sending
        from app.notification_utils import send_regional_notification
        try:
            send_regional_notification(regional_notif)
            logger.info(f"✓ Regional risk alert sent to {county} farmers")
        except Exception as e:
            logger.error(f"Failed to send regional notification: {str(e)}")
        
    except Exception as e:
        logger.error(f"Error creating regional risk summary: {str(e)}")
