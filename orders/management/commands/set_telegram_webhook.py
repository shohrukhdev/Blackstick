import asyncio
import logging

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Register the Telegram bot webhook with the configured SITE_URL."

    def handle(self, *args, **options):
        token = settings.TELEGRAM_BOT_TOKEN
        if not token:
            raise CommandError('TELEGRAM_BOT_TOKEN is not set in settings.')

        site = settings.SITE_URL.rstrip('/')
        webhook_url = f'{site}/orders/telegram/webhook/'
        secret = settings.TELEGRAM_BOT_WEBHOOK_SECRET

        asyncio.run(self._set_webhook(token, webhook_url, secret))

    async def _set_webhook(self, token: str, webhook_url: str, secret: str) -> None:
        from telegram import Bot
        kwargs = {'url': webhook_url}
        if secret:
            kwargs['secret_token'] = secret
        async with Bot(token=token) as bot:
            await bot.set_webhook(**kwargs)
        self.stdout.write(self.style.SUCCESS(f'Webhook set to: {webhook_url}'))
