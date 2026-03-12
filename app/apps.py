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
            
            # Start the scheduler if not already running
            if not scheduler.running:
                scheduler.start()
                logger.info("✓ APScheduler started successfully")
                logger.info("  Task: send_daily_advisories")
                logger.info("  Schedule: Daily at 6 AM UTC (9 AM GMT+3 Nairobi time)")
                logger.info("  Job store: DjangoJobStore (Django database)")
            else:
                logger.info("APScheduler already running")
                
        except Exception as e:
            logger.error(f"✗ Error initializing APScheduler: {str(e)}")
            logger.exception("Full traceback:")

