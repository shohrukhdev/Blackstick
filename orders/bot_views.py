import asyncio
import json
import logging

from django.conf import settings
from django.http import HttpResponse, HttpResponseForbidden
from django.views.decorators.csrf import csrf_exempt
from telegram import Update

logger = logging.getLogger(__name__)

_application = None


def _get_application():
    global _application
    if _application is None:
        from orders.bot import get_application
        _application = get_application()
    return _application


async def _process(app, update):
    await app.initialize()
    await app.process_update(update)


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
        app = _get_application()
        data = json.loads(request.body)
        update = Update.de_json(data, app.bot)
        asyncio.run(_process(app, update))
    except Exception:
        logger.exception('Error processing Telegram update')

    return HttpResponse(status=200)
