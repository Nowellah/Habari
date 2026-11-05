import logging

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from channels.telegram import TelegramBot


class Command(BaseCommand):
    help = "Run the Habari Telegram bot (long polling). Needs TELEGRAM_TOKEN in .env."

    def handle(self, *args, **opts):
        if not settings.TELEGRAM_TOKEN:
            raise CommandError(
                "TELEGRAM_TOKEN is not set. In Telegram, message @BotFather, send /newbot, "
                "then put the token in .env as TELEGRAM_TOKEN=..."
            )
        logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
        self.stdout.write(self.style.SUCCESS("Telegram bot running. Press Ctrl+C to stop."))
        try:
            TelegramBot(settings.TELEGRAM_TOKEN).run_forever()
        except KeyboardInterrupt:
            self.stdout.write("Stopped.")
