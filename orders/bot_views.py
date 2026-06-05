import logging

from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt

logger = logging.getLogger(__name__)


@csrf_exempt
def telegram_webhook(request):
    return HttpResponse(status=200)
