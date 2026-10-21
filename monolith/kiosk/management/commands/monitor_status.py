"""Print the app's operational status as JSON, for the server's watchdog (scripts/monitor.sh)."""

import datetime as dt
import json

from django.core.management.base import BaseCommand
from django.utils import timezone

from kiosk import queue
from kiosk.device_views import gateway_online
from kiosk.models import AuditEvent


class Command(BaseCommand):
    help = "Print operational status (gateway, doctors on duty) as JSON."

    def handle(self, *args, **options):
        self.stdout.write(
            json.dumps(
                {
                    "gateway_online": gateway_online(),
                    "doctors_on_duty": len(queue.doctors_on_duty()),
                    "events_last_hour": AuditEvent.objects.filter(created_at__gte=timezone.now() - dt.timedelta(hours=1)).count(),
                }
            )
        )
