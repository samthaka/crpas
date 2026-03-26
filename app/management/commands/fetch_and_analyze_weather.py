"""
Management command to manually trigger weather data fetch and risk analysis.

Usage:
    python manage.py fetch_and_analyze_weather [--farm-id ID] [--all] [--limit 10]

Options:
    --all       Process all farms with GPS coordinates
    --farm-id   Process specific farm by ID
    --limit N   Limit to N farms (default: 10)

Examples:
    # Process all farms
    python manage.py fetch_and_analyze_weather --all
    
    # Process first 5 farms
    python manage.py fetch_and_analyze_weather --limit 5
    
    # Process specific farm
    python manage.py fetch_and_analyze_weather --farm-id 3
"""

import logging
from django.core.management.base import BaseCommand
from django.utils import timezone
from app.models import Farm
from app.tasks import _process_farm_weather_and_risks

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Manually fetch weather data and analyze for risks'

    def add_arguments(self, parser):
        parser.add_argument(
            '--all',
            action='store_true',
            help='Process all farms with GPS coordinates',
        )
        parser.add_argument(
            '--farm-id',
            type=int,
            help='Process specific farm by ID',
        )
        parser.add_argument(
            '--limit',
            type=int,
            default=10,
            help='Limit to N farms (default: 10)',
        )

    def handle(self, *args, **options):
        self.stdout.write(
            self.style.SUCCESS(
                f'\n{"="*70}'
            )
        )
        self.stdout.write(
            self.style.SUCCESS(
                f'🔄 Starting manual weather fetch & risk analysis at {timezone.now()}'
            )
        )
        self.stdout.write(
            self.style.SUCCESS(
                f'{"="*70}\n'
            )
        )

        try:
            # Determine which farms to process
            if options.get('farm_id'):
                farms = Farm.objects.filter(id=options['farm_id']).select_related('farmer')
                if not farms.exists():
                    self.stdout.write(self.style.ERROR(f"Farm with ID {options['farm_id']} not found"))
                    return
                self.stdout.write(f"📍 Processing farm ID: {options['farm_id']}")
            
            elif options.get('all'):
                farms = Farm.objects.filter(
                    lat__isnull=False,
                    long__isnull=False
                ).select_related('farmer')
                self.stdout.write(f"📍 Processing ALL {farms.count()} farms with GPS coordinates")
            
            else:
                farms = Farm.objects.filter(
                    lat__isnull=False,
                    long__isnull=False
                ).select_related('farmer')[:options['limit']]
                self.stdout.write(f"📍 Processing up to {options['limit']} farms")
            
            if not farms.exists():
                self.stdout.write(self.style.WARNING("No farms found to process"))
                return
            
            self.stdout.write(f"Total farms to process: {farms.count()}\n")
            
            success_count = 0
            failed_count = 0
            
            for i, farm in enumerate(farms, 1):
                farmer_info = f"{farm.farmer.fname} {farm.farmer.lname}"
                farm_location = f"{farm.ward or 'N/A'}, {farm.sub_county or 'N/A'}"
                
                self.stdout.write(
                    f"\n[{i}/{farms.count()}] Processing {farmer_info} ({farm_location})"
                )
                self.stdout.write(f"    GPS: {farm.lat}, {farm.long}")
                
                try:
                    _process_farm_weather_and_risks(farm)
                    self.stdout.write(self.style.SUCCESS("    ✓ Success"))
                    success_count += 1
                    
                except Exception as e:
                    self.stdout.write(self.style.ERROR(f"    ✗ Error: {str(e)}"))
                    failed_count += 1
            
            # Summary
            self.stdout.write(
                self.style.SUCCESS(
                    f'\n{"="*70}'
                )
            )
            self.stdout.write(
                self.style.SUCCESS(
                    f'Weather fetch & risk analysis completed:'
                )
            )
            self.stdout.write(
                self.style.SUCCESS(
                    f'  ✓ Successful: {success_count}'
                )
            )
            self.stdout.write(
                self.style.WARNING(
                    f'  ✗ Failed: {failed_count}'
                )
            )
            self.stdout.write(
                self.style.SUCCESS(
                    f'{"="*70}\n'
                )
            )
            
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'\nFatal error: {str(e)}')
            )
            logger.exception("Fatal error in manual weather fetch command")
