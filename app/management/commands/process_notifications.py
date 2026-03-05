"""
Django management command to process notification triggers.
This command checks rainfall, soil moisture, and planting conditions
and sends notifications to farmers accordingly.

Usage:
    python manage.py process_notifications
    python manage.py process_notifications --farmer-id=1
"""

from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
import logging
from app.models import Farmer
from app.notification_utils import (
    check_rainfall_alert,
    check_soil_moisture_alert,
    check_planting_date_alert,
)

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Process notification triggers for farmers based on weather and soil data'

    def add_arguments(self, parser):
        parser.add_argument(
            '--farmer-id',
            type=int,
            help='Process notifications for a specific farmer ID',
        )

    def handle(self, *args, **options):
        farmer_id = options.get('farmer_id')

        if farmer_id:
            farmers = Farmer.objects.filter(id=farmer_id)
            if not farmers.exists():
                self.stdout.write(self.style.ERROR(f'Farmer with ID {farmer_id} not found'))
                return
        else:
            farmers = Farmer.objects.all()

        self.stdout.write(self.style.SUCCESS(f'Processing notifications for {farmers.count()} farmers'))

        for farmer in farmers:
            try:
                self.process_farmer_notifications(farmer)
            except Exception as e:
                logger.error(f'Error processing notifications for {farmer}: {str(e)}')
                self.stdout.write(
                    self.style.ERROR(f'Error processing {farmer.fname} {farmer.lname}: {str(e)}')
                )

        self.stdout.write(self.style.SUCCESS('Notification processing completed'))

    def process_farmer_notifications(self, farmer):
        """
        Process all notification triggers for a specific farmer.
        """
        self.stdout.write(f'Processing farmer: {farmer.fname} {farmer.lname}')

        # Example rainfall data (in a real scenario, this would come from an API)
        # This is a sample implementation - you would fetch actual weather data
        rainfall_data = self.get_rainfall_data(farmer)
        if rainfall_data:
            check_rainfall_alert(farmer, rainfall_data)
            self.stdout.write(f'  ✓ Checked rainfall alert')

        # Check soil moisture
        soil_data = self.get_soil_data(farmer)
        if soil_data:
            check_soil_moisture_alert(farmer, soil_data)
            self.stdout.write(f'  ✓ Checked soil moisture alert')

        # Check planting dates
        check_planting_date_alert(farmer)
        self.stdout.write(f'  ✓ Checked planting date alert')

    def get_rainfall_data(self, farmer):
        """
        Fetch rainfall data for a farmer from external weather API.
        This is a placeholder - integrate with actual weather service.
        
        You can integrate with:
        - OpenWeatherMap API
        - NOAA Weather API
        - Kenya Meteorological Department API
        - Local weather station data
        """
        try:
            # This is a sample implementation
            # In production, fetch from actual weather API based on farmer's location
            import random
            
            rainfall_amount = random.uniform(0, 50)  # 0-50mm
            
            return {
                'amount': rainfall_amount,
                'date': timezone.now().date(),
                'location': f'{farmer.lat}, {farmer.long}'
            }
        except Exception as e:
            logger.error(f'Error getting rainfall data for {farmer}: {str(e)}')
            return None

    def get_soil_data(self, farmer):
        """
        Fetch soil moisture data for a farmer.
        This is a placeholder - integrate with actual soil sensors or API.
        
        You can integrate with:
        - USDA Soil Survey data
        - IoT soil moisture sensors
        - Satellite-based soil moisture data (ESA, NASA)
        - LocalTerraSense or similar services
        """
        try:
            # This is a sample implementation
            # In production, fetch from actual soil sensor API
            import random
            
            soil_moisture = random.uniform(20, 80)  # 20-80%
            
            return {
                'moisture_percent': soil_moisture,
                'soil_type': 'loam',
                'temperature': random.uniform(20, 30),  # 20-30°C
                'location': f'{farmer.lat}, {farmer.long}'
            }
        except Exception as e:
            logger.error(f'Error getting soil data for {farmer}: {str(e)}')
            return None
