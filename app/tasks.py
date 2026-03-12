"""
Scheduled tasks for CRPAS.
These tasks are automatically run by APScheduler at specified times.

IMPORTANT: This module uses REAL DATA ONLY - no fallback/false data is used.
If APIs are unavailable, advisories are SKIPPED rather than sent with false data.
This protects farmers from making wrong decisions based on inaccurate information.
"""

import logging
import time
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
