import asyncio
import logging

from celery import shared_task
from django.conf import settings
from telegram import Bot
from telegram.error import TelegramError

logger = logging.getLogger(__name__)


def _build_welcome(role: str, name: str):
    """Return (text, keyboard) for the post-link welcome message."""
    from orders.bot import build_client_keyboard, build_supplier_keyboard
    site = settings.SITE_URL.rstrip('/')
    if role == 'client':
        keyboard = build_client_keyboard(site)
        text = (
            f"✅ Hisobingiz muvaffaqiyatli bog'landi!\n\n"
            f'Xush kelibsiz, <b>{name}</b>! 👋\n\n'
            f'Quyidagi tugmalar orqali ishlashingiz mumkin:\n'
            f'• 🛍 <b>Katalog</b> — buyurtma berish\n'
            f'• 📦 <b>Buyurtmalarim</b> — faol buyurtmalar holati\n'
            f'• 💰 <b>Hisobim</b> — balans va so\'nggi to\'lovlar\n'
            f'• 📍 <b>Joylashuvimni yangilash</b> — yetkazib berish manzili'
        )
    else:
        keyboard = build_supplier_keyboard(site)
        text = (
            f"✅ Hisobingiz muvaffaqiyatli bog'landi!\n\n"
            f'Xush kelibsiz, <b>{name}</b>! 👋\n\n'
            f'Quyidagi tugmalar orqali ishlashingiz mumkin:\n'
            f'• 📊 <b>Dashboard</b> — boshqaruv paneli\n'
            f'• 📋 <b>Yangi buyurtmalar</b> — kutilayotgan buyurtmalar\n'
            f'• 👥 <b>Mijozlar</b> — qoldiq bo\'yicha mijozlar ro\'yxati'
        )
    return text, keyboard


def send_welcome_sync(telegram_id: int, role: str, name: str) -> None:
    """Send the post-link welcome message synchronously (no Celery required)."""
    if not telegram_id:
        return
    text, keyboard = _build_welcome(role, name)

    async def _send():
        bot = Bot(token=settings.TELEGRAM_BOT_TOKEN)
        async with bot:
            await bot.send_message(
                chat_id=telegram_id, text=text, reply_markup=keyboard, parse_mode='HTML',
            )

    try:
        asyncio.run(_send())
    except Exception:
        logger.exception('Error sending Telegram welcome to %s', telegram_id)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def send_telegram_notification(self, telegram_id, text, parse_mode='HTML'):
    """Send a plain text notification to a Telegram user. Retries on TelegramError."""
    if not telegram_id:
        return

    async def _send():
        bot = Bot(token=settings.TELEGRAM_BOT_TOKEN)
        async with bot:
            await bot.send_message(chat_id=telegram_id, text=text, parse_mode=parse_mode)

    try:
        asyncio.run(_send())
    except TelegramError as exc:
        logger.warning('TelegramError sending to %s: %s', telegram_id, exc)
        raise self.retry(exc=exc)
    except Exception:
        logger.exception('Unexpected error sending Telegram notification to %s', telegram_id)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def send_telegram_welcome(self, telegram_id, role, name):
    """Celery task wrapper around send_welcome_sync (for retry support)."""
    try:
        send_welcome_sync(telegram_id, role, name)
    except TelegramError as exc:
        logger.warning('TelegramError sending welcome to %s: %s', telegram_id, exc)
        raise self.retry(exc=exc)
