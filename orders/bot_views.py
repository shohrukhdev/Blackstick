import asyncio
import json
import logging

from django.conf import settings
from django.http import HttpResponse, HttpResponseForbidden
from django.views.decorators.csrf import csrf_exempt
from telegram import Update

logger = logging.getLogger(__name__)


@csrf_exempt
def telegram_webhook(request):
    if request.method != 'POST':
        return HttpResponse(status=405)

    secret = settings.TELEGRAM_BOT_WEBHOOK_SECRET
    if secret:
        incoming = request.headers.get('X-Telegram-Bot-Api-Secret-Token', '')
        if incoming != secret:
            return HttpResponseForbidden('Invalid secret token')

    try:
        from orders.bot import get_application
        data = json.loads(request.body)

        async def _process():
            app = get_application()
            async with app:
                update = Update.de_json(data, app.bot)
                await app.process_update(update)

        asyncio.run(_process())
    except Exception:
        logger.exception('Error processing Telegram update')

    return HttpResponse(status=200)
