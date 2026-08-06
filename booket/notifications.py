"""
Centralized appointment status-change notifications.

Every place in the app that changes an Appointment's status and needs to
tell the client (or the specialist) about it should call one of the
functions below, instead of hand-building SMS text inline. This keeps
templates/demo-suppression/channel logic in one place, and is the seam
where a future channel (e.g. Telegram) would plug in alongside SMS.
"""
import logging

from django.core.mail import send_mail
from django.utils import timezone

from .sms_service import send_sms
from .utils import is_demo_provider

logger = logging.getLogger(__name__)

FROM_EMAIL = "alphadevmanager@gmail.com"


def _client_language(client):
    return client.language_code or "ru"


def _format_dt(dt):
    return timezone.localtime(dt).strftime("%d.%m.%Y %H:%M")


def _resolve_provider(appointment):
    provider_server = appointment.server.providerserver_set.select_related("provider").first()
    return provider_server.provider if provider_server else None


def _send_to_client(client, text):
    if client.phone_number:
        sms_result = send_sms(phone_number=client.phone_number, message=text)
        logger.info(f"Status change SMS to client {client.id}: {sms_result}")
    elif client.email:
        send_mail("booket.uz appointment update", text, FROM_EMAIL, [client.email], fail_silently=True)
        logger.info(f"Status change email sent to {client.email}")


def _client_accept_text(lang, appointment):
    dt = _format_dt(appointment.start_datetime)
    if lang == "uz":
        return (f"Xursandchilik bilan xabar beramiz: №{appointment.id} uchrashuvingiz "
                f"mutaxassis tomonidan tasdiqlandi. Sana: {dt}. Ko'rishguncha!")
    if lang == "ru":
        return (f"Ваша запись №{appointment.id} подтверждена специалистом. "
                f"Дата: {dt}. Не опаздывайте!")
    return (f"Your appointment №{appointment.id} has been confirmed by the specialist. "
            f"Date: {dt}. See you!")


def _client_reject_text(lang, appointment):
    if lang == "uz":
        return (f"Afsuski, №{appointment.id} uchrashuvingiz rad etildi. "
                f"Batafsil ma'lumot uchun bizga murojaat qiling.")
    if lang == "ru":
        return (f"К сожалению, ваша запись №{appointment.id} была отклонена. "
                f"Свяжитесь с нами для получения подробностей.")
    return (f"Unfortunately, your appointment №{appointment.id} has been declined. "
            f"Please contact us for more details.")


def _client_cancel_text(lang, appointment):
    if lang == "uz":
        return (f"Afsuski, №{appointment.id} uchrashuvingiz bekor qilindi. "
                f"Batafsil ma'lumot uchun bizga murojaat qiling.")
    if lang == "ru":
        return (f"К сожалению, ваша запись №{appointment.id} была отменена. "
                f"Свяжитесь с нами для получения подробностей.")
    return (f"Unfortunately, your appointment №{appointment.id} has been cancelled. "
            f"Please contact us for more details.")


def _client_reschedule_text(lang, appointment):
    dt = _format_dt(appointment.start_datetime)
    if lang == "uz":
        return (f"Xabar beramiz: №{appointment.id} uchrashuvingiz vaqti o'zgartirildi. "
                f"Yangi sana: {dt}. Kechikmaslikka harakat qiling!")
    if lang == "ru":
        return (f"Время вашей записи №{appointment.id} было изменено. "
                f"Новая дата и время: {dt}. Не опаздывайте!")
    return (f"Your appointment №{appointment.id} has been rescheduled. "
            f"New date and time: {dt}. Don't be late!")


_CLIENT_STATUS_TEXT_BUILDERS = {
    "accept": _client_accept_text,
    "reject": _client_reject_text,
    "cancel": _client_cancel_text,
    "reschedule": _client_reschedule_text,
}


def notify_client_status_change(appointment, event: str):
    """
    event: one of 'accept', 'reject', 'cancel', 'reschedule'.
    Notifies the client only — server-initiated events are already visible
    to the server in the dashboard that triggered them.
    """
    try:
        client = appointment.client
        if not client:
            return
        provider = _resolve_provider(appointment)
        if not provider:
            return
        if is_demo_provider(provider.identifier):
            return

        builder = _CLIENT_STATUS_TEXT_BUILDERS.get(event)
        if not builder:
            logger.warning(f"notify_client_status_change: unknown event '{event}'")
            return

        lang = _client_language(client)
        text = builder(lang, appointment)
        _send_to_client(client, text)
    except Exception:
        logger.exception(f"Failed to notify client on {event}")


def notify_new_booking(appointment, provider_identifier: str):
    """
    Sent once OTP is verified and the appointment becomes CONFIRMED/ACCEPTED:
    confirms the booking to the client and alerts the specialist of a new
    appointment on their calendar.
    """
    try:
        if is_demo_provider(provider_identifier):
            return

        server = appointment.server
        client = appointment.client
        specialist_name = server.user.get_full_name() or server.user.username
        local_start = timezone.localtime(appointment.start_datetime)
        local_end = timezone.localtime(appointment.end_datetime)
        dt = local_start.strftime("%d.%m.%Y %H:%M")

        lang = _client_language(client)
        if lang == "uz":
            client_sms = (
                f"Siz No{appointment.id} uchrashuvni tasdiqlading. "
                f"Sana: {dt}. Mutaxassis: {specialist_name}. Kechikmaslikka harakat qiling!"
            )
        elif lang == "ru":
            client_sms = (
                f"Вы записаны на приём №{appointment.id}. "
                f"Дата: {dt}. Специалист: {specialist_name}. Не опаздывайте!"
            )
        else:
            client_sms = (
                f"Your appointment No{appointment.id} is confirmed. "
                f"Date: {dt}. Specialist: {specialist_name}. Don't be late!"
            )

        specialist_sms = (
            f"Sizda yangi uchrashuv/У вас новая встреча! "
            f"Vaqti/Время: {dt} - {local_end.strftime('%H:%M')}. "
            f"Mijoz/Клиент: {client.full_name}. Batafsil/Подробнее: https://booket.uz/dashboard/main/"
        )

        if client.phone_number:
            sms_result = send_sms(phone_number=client.phone_number, message=client_sms)
            logger.info(f"Client confirmation SMS: {sms_result}")
        if server.phone_number:
            sms_result = send_sms(phone_number=server.phone_number, message=specialist_sms)
            logger.info(f"Specialist notification SMS: {sms_result}")
    except Exception:
        logger.exception("Failed to notify on new booking")
