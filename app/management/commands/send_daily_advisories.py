"""
Django management command to send daily advisory messages to all farmers.
This command is designed to be run daily at 9 AM GMT+3 (Nairobi time) via cron.

Usage:
    python manage.py send_daily_advisories
    
Cron Configuration:
    0 6 * * * cd /home/sam/wabisuke/CRPAS && python manage.py send_daily_advisories >> /var/log/crpas_advisories.log 2>&1
    
Note: The cron time is 6 AM UTC, which corresponds to 9 AM GMT+3 (Nairobi time)
"""

from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
import logging
from app.models import Farmer, Farm
from app.notification_utils import create_and_send_notification
from app.utils import get_rainfall_forecast, get_soil_data, generate_advisory

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Send daily agricultural advisories to all farmers with farms'

    def add_arguments(self, parser):
        parser.add_argument(
            '--farmer-id',
            type=int,
            help='Send advisory to a specific farmer ID',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Print what would be sent without actually sending',
        )

    def handle(self, *args, **options):
        farmer_id = options.get('farmer_id')
        dry_run = options.get('dry_run', False)

        # Get farmers to process
        if farmer_id:
            farmers = Farmer.objects.filter(id=farmer_id)
            if not farmers.exists():
                self.stdout.write(self.style.ERROR(f'Farmer with ID {farmer_id} not found'))
                return
            self.stdout.write(f'Processing advisory for specific farmer: ID {farmer_id}')
        else:
            # Get all farmers who have at least one farm
            farmers = Farmer.objects.filter(farms__isnull=False).distinct()
            self.stdout.write(self.style.SUCCESS(f'Processing daily advisories for {farmers.count()} farmers'))

        if dry_run:
            self.stdout.write(self.style.WARNING('⚠️  DRY RUN - No notifications will be sent'))

        success_count = 0
        error_count = 0

        for farmer in farmers:
            try:
                if self._send_advisory_to_farmer(farmer, dry_run):
                    success_count += 1
                else:
                    error_count += 1
            except Exception as e:
                logger.error(f'Error sending advisory to {farmer}: {str(e)}')
                self.stdout.write(
                    self.style.ERROR(f'Error sending advisory to {farmer.fname} {farmer.lname}: {str(e)}')
                )
                error_count += 1

        # Summary
        self.stdout.write(self.style.SUCCESS(
            f'\n✓ Daily advisories completed: {success_count} sent, {error_count} failed'
        ))

    def _send_advisory_to_farmer(self, farmer, dry_run=False):
        """
        Generate and send an advisory for a specific farmer.
        
        Args:
            farmer (Farmer): The farmer to send advisory to
            dry_run (bool): If True, only print what would be sent
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # Get the farmer's farms
            farms = farmer.farms.all()
            if not farms.exists():
                logger.warning(f'Farmer {farmer} has no farms, skipping')
                return False

            # Use the first farm for weather data (most farmers have one farm)
            farm = farms.first()
            
            if not farm.lat or not farm.long:
                logger.warning(f'Farm for {farmer} has no GPS coordinates, skipping')
                return False

            self.stdout.write(f'\n  Processing {farmer.fname} {farmer.lname}')
            
            # Fetch weather and soil data
            try:
                forecast_data = get_rainfall_forecast(farm.lat, farm.long, days=10)
                soil_data = get_soil_data(farm.lat, farm.long)
                
                # Check for API errors
                if isinstance(forecast_data, dict) and 'error' in forecast_data:
                    logger.warning(f'Failed to get forecast for {farmer}: {forecast_data["error"]}')
                    forecast_data = None
                    
                if isinstance(soil_data, dict) and 'error' in soil_data:
                    logger.warning(f'Failed to get soil data for {farmer}: {soil_data.get("error", "Unknown error")}')
                    soil_data = None
                
                if not forecast_data or not soil_data:
                    logger.warning(f'Missing weather/soil data for {farmer}, using fallback values')
                    # Use fallback/dummy data to ensure advisory is still generated
                    forecast_data = forecast_data or [{'date': str(timezone.now().date()), 'rain_mm': 0, 'prob_max': 0, 'temp_min': 25, 'temp_max': 30}]
                    soil_data = soil_data or {'soil_moisture_top': 0.25, 'soil_moisture_mid': 0.30, 'soil_moisture_deep': 0.35, 'soil_temp_surface': 25, 'soil_temp_mid': 20}
                
            except Exception as e:
                logger.error(f'Error fetching weather/soil data for {farmer}: {str(e)}')
                self.stdout.write(self.style.WARNING(f'  ⚠️  Using fallback data due to API error'))
                forecast_data = [{'date': str(timezone.now().date()), 'rain_mm': 0, 'prob_max': 0, 'temp_min': 25, 'temp_max': 30}]
                soil_data = {'soil_moisture_top': 0.25, 'soil_moisture_mid': 0.30, 'soil_moisture_deep': 0.35, 'soil_temp_surface': 25, 'soil_temp_mid': 20}
            
            # Generate advisory message using AI
            try:
                advisory_text = generate_advisory(farm, forecast_data, soil_data)
            except Exception as e:
                logger.error(f'Error generating advisory for {farmer}: {str(e)}')
                self.stdout.write(self.style.WARNING(f'  ⚠️  Error generating advisory'))
                
                # Fallback to basic advisory
                crop_name = dict(farmer._meta.get_field('crop_type').choices).get(
                    farmer.crop_type, farmer.crop_type
                )
                advisory_text = f"Daily advisory for your {crop_name} farm. Check local weather forecasts and soil moisture levels. Ensure proper irrigation management based on recent rainfall patterns."
            
            # Create the advisory message
            title = "🌾 Daily Agricultural Advisory"
            message = advisory_text if advisory_text else "Check weather conditions and adjust your farming practices accordingly."
            
            if dry_run:
                self.stdout.write(f'  [DRY RUN] Would send to {farmer.email or farmer.phone}')
                self.stdout.write(f'  Title: {title}')
                self.stdout.write(f'  Message: {message[:200]}...')
                return True
            
            # Create and send notification via all channels
            notification = create_and_send_notification(
                farmer=farmer,
                title=title,
                message=message,
                notification_type='advisory',
                metadata={
                    'sent_at': timezone.now().isoformat(),
                    'location': f'{farm.lat},{farm.long}',
                    'farm_name': farm.farm_name or 'Primary Farm',
                    'crop_type': farmer.crop_type
                },
                send_async=True  # Send in background to avoid blocking
            )
            
            if notification:
                self.stdout.write(self.style.SUCCESS(f'  ✓ Advisory sent to {farmer.fname}'))
                logger.info(f'Advisory sent to {farmer}: {title}')
                return True
            else:
                self.stdout.write(self.style.ERROR(f'  ✗ Failed to create notification for {farmer.fname}'))
                return False
                
        except Exception as e:
            logger.exception(f'Unexpected error processing advisory for {farmer}: {str(e)}')
            self.stdout.write(self.style.ERROR(f'  ✗ Unexpected error: {str(e)}'))
            return False
