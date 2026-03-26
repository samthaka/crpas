"""
Management command to send scheduled regional notifications.

Usage:
    python manage.py send_regional_notifications [--all] [--limit 10]

Options:
    --all       Send all due scheduled notifications (default behavior)
    --limit N   Limit to N notifications per run (default: 10)

Schedule in crontab:
    0 7 * * * cd /path/to/CRPAS && python manage.py send_regional_notifications >> /var/log/crpas_regional_notifs.log 2>&1
"""

import logging
from django.core.management.base import BaseCommand
from django.utils import timezone
from app.models import RegionalNotification
from app.notification_utils import send_regional_notification

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Send scheduled regional notifications to farmers'

    def add_arguments(self, parser):
        parser.add_argument(
            '--all',
            action='store_true',
            help='Send all due scheduled notifications',
        )
        parser.add_argument(
            '--limit',
            type=int,
            default=10,
            help='Limit to N notifications per run (default: 10)',
        )
        parser.add_argument(
            '--region',
            type=str,
            help='Send notifications for a specific region (e.g., "Kisii")',
        )

    def handle(self, *args, **options):
        self.stdout.write(
            self.style.SUCCESS(
                f'\n{"="*60}'
            )
        )
        self.stdout.write(
            self.style.SUCCESS(
                f'🔔 Starting Regional Notification Sender at {timezone.now()}'
            )
        )
        self.stdout.write(
            self.style.SUCCESS(
                f'{"="*60}\n'
            )
        )

        try:
            # Get scheduled notifications that are ready
            query = RegionalNotification.objects.filter(
                status='scheduled',
                scheduled_for__lte=timezone.now()
            ).order_by('-created_at')

            # If specific region requested, filter further
            if options.get('region'):
                query = query.filter(region_name__iexact=options['region'])
                self.stdout.write(
                    f"📍 Filtering for region: {options['region']}"
                )

            # Apply limit
            limit = options.get('limit', 10)
            notifications = query[:limit]

            if not notifications.exists():
                self.stdout.write(
                    self.style.WARNING(
                        '\n⚠️  No scheduled notifications ready to send'
                    )
                )
                return

            self.stdout.write(
                self.style.SUCCESS(
                    f'\n✓ Found {notifications.count()} notifications to send\n'
                )
            )

            # Send each notification
            total_sent = 0
            total_failed = 0
            total_skipped = 0
            successful_sends = 0
            failed_sends = 0

            for i, regional_notif in enumerate(notifications, 1):
                self.stdout.write(
                    f'{i}. Sending: "{regional_notif.title}"'
                )
                self.stdout.write(
                    f'   Region: {regional_notif.region_name} ({regional_notif.region_level})'
                )

                try:
                    result = send_regional_notification(
                        regional_notif,
                        send_immediately=True
                    )

                    total_sent += result['sent']
                    total_failed += result['failed']
                    total_skipped += result['skipped']

                    if result['failed'] == 0:
                        self.stdout.write(
                            self.style.SUCCESS(
                                f'   ✓ Sent to {result["sent"]} farmers'
                            )
                        )
                        successful_sends += 1
                    else:
                        self.stdout.write(
                            self.style.WARNING(
                                f'   ⚠️  Sent to {result["sent"]} farmers, '
                                f'{result["failed"]} failed'
                            )
                        )
                        failed_sends += 1

                except Exception as e:
                    self.stdout.write(
                        self.style.ERROR(
                            f'   ✗ Error: {str(e)}'
                        )
                    )
                    failed_sends += 1

            # Summary
            self.stdout.write(
                self.style.SUCCESS(
                    f'\n{"="*60}'
                )
            )
            self.stdout.write(
                self.style.SUCCESS(
                    '📊 SUMMARY'
                )
            )
            self.stdout.write(
                self.style.SUCCESS(
                    f'{"="*60}'
                )
            )
            self.stdout.write(
                f'Total Notifications Processed:  {successful_sends + failed_sends}'
            )
            self.stdout.write(
                self.style.SUCCESS(
                    f'✓ Successfully Sent:           {successful_sends}'
                )
            )
            if failed_sends > 0:
                self.stdout.write(
                    self.style.ERROR(
                        f'✗ Failed to Send:              {failed_sends}'
                    )
                )
            self.stdout.write(f'\nTotal Recipients Reached:      {total_sent}')
            if total_failed > 0:
                self.stdout.write(
                    self.style.WARNING(
                        f'⚠️  Delivery Failures:           {total_failed}'
                    )
                )
            self.stdout.write(
                self.style.SUCCESS(
                    f'{"="*60}\n'
                )
            )

            logger.info(
                f"Regional notifications sent. Summary: {successful_sends} successful, "
                f"{failed_sends} failed, {total_sent} recipients reached"
            )

        except Exception as e:
            self.stdout.write(
                self.style.ERROR(
                    f'\n✗ Error running command: {str(e)}'
                )
            )
            logger.error(f"Error in send_regional_notifications: {str(e)}")
            raise
