from django.core.management.base import BaseCommand

from core.services import run_reminders


class Command(BaseCommand):
    help = "Напоминания о дедлайнах за день и о днях рождения накануне и в сам день. Можно запускать из cron раз в час."

    def handle(self, *args, **opts):
        self.stdout.write(f"Создано уведомлений: {run_reminders()}")
