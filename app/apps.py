from django.apps import AppConfig
import logging

logger = logging.getLogger(__name__)


class AppConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'app'
    
    def ready(self):
        """
        Initialize APScheduler when Django starts.
        Registers the daily advisory task to run at 9 AM GMT+3 (Nairobi time).
        
        Uses:
        - BackgroundScheduler: Standard APScheduler scheduler
        - DjangoJobStore: Stores jobs in Django database
        - CronTrigger: Schedules job at specific time (6 AM UTC = 9 AM GMT+3)
        """
        from apscheduler.schedulers.background import BackgroundScheduler
        from apscheduler.triggers.cron import CronTrigger
        from django_apscheduler.jobstores import DjangoJobStore
        
        try:
            # Create scheduler instance
            scheduler = BackgroundScheduler()
            
            # Configure scheduler with DjangoJobStore (persists jobs in database)
            scheduler.configure(
                jobstores={'default': DjangoJobStore()},
                timezone='UTC'
            )
            
            # Import the task
            from .tasks import send_daily_advisories_task
            
            # Schedule the daily advisory task
            # 6 AM UTC = 9 AM GMT+3 (Nairobi/East Africa Time)
            scheduler.add_job(
                send_daily_advisories_task,
                trigger=CronTrigger(hour=6, minute=0),
                id='send_daily_advisories',
                name='Send daily agricultural advisories',
                replace_existing=True,
            )
            
            # Schedule the periodic weather fetch & risk analysis task
            # Runs every 6 hours at: 12:00 AM, 6:00 AM, 12:00 PM, 6:00 PM UTC
            from .tasks import periodic_fetch_and_analyze_weather
            
            scheduler.add_job(
                periodic_fetch_and_analyze_weather,
                trigger=CronTrigger(hour='*/6', minute=0),
                id='periodic_weather_fetch',
                name='Periodic weather data fetch & risk analysis',
                replace_existing=True,
            )
            
            # Start the scheduler if not already running
            if not scheduler.running:
                scheduler.start()
                logger.info("✓ APScheduler started successfully")
                logger.info("  Tasks scheduled:")
                logger.info("    1. send_daily_advisories - Daily at 6 AM UTC (9 AM GMT+3 Nairobi time)")
                logger.info("    2. periodic_weather_fetch - Every 6 hours at 12:00 AM, 6:00 AM, 12:00 PM, 6:00 PM UTC")
                logger.info("  Job store: DjangoJobStore (Django database)")
            else:
                logger.info("APScheduler already running")
                
        except Exception as e:
            logger.error(f"✗ Error initializing APScheduler: {str(e)}")
            logger.exception("Full traceback:")

