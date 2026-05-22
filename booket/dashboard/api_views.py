import logging
from datetime import datetime
from urllib.parse import unquote
from django.core.mail import send_mail
from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from booket.dashboard.serializers import AppointmentSerializer, AppointmentFileSerializer
from booket.models import (
    Appointment, AppointmentFile, AppointmentService, Provider, Client,
    OTPVerification, ProviderClient, ProviderServerService, Service, Server,
)
from booket.sms_service import send_sms
from booket.utils import mask_email, mask_phone_number

logger = logging.getLogger(__name__)


class AppointmentViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = AppointmentSerializer
    pagination_class = None
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        _full_prefetch = [
            "appointmentservice_set__service__providerserverservice_set",
            "files",
        ]
        _full_select = ["client", "server__user"]

        if self.action in ('update_appointment', 'upload_file', 'delete_file'):
            try:
                return Appointment.objects.filter(server=self.request.user.server_user)
            except AttributeError:
                provider = Provider.objects.get(owner=self.request.user)
                return Appointment.objects.filter(server__providerserver__provider=provider)

        if self.request.query_params.get("viewby") == "provider":
            provider = Provider.objects.get(owner=self.request.user)
            return Appointment.objects.filter(
                server__providerserver__provider=provider,
                status__in=["CONFIRMED", "ACCEPTED", "COMPLETED", "NO_SHOW", "CANCELLED"]
            ).select_related(*_full_select).prefetch_related(*_full_prefetch).order_by("start_datetime")

        if self.request.query_params.get("format") == "datatables":
            return Appointment.objects.filter(
                server=self.request.user.server_user,
                status__in=["CONFIRMED", "ACCEPTED", "COMPLETED", "NO_SHOW", "CANCELLED", "REJECTED"]
            ).select_related(*_full_select).prefetch_related(*_full_prefetch).order_by("start_datetime")

        server = self.request.user.server_user
        start_date = unquote((self.request.query_params.get("start") or "")[0:19])
        end_date = unquote((self.request.query_params.get("end") or "")[0:19])
        if start_date and end_date:
            start_date = timezone.make_aware(datetime.strptime(start_date, "%Y-%m-%dT%H:%M:%S"))
            end_date = timezone.make_aware(datetime.strptime(end_date, "%Y-%m-%dT%H:%M:%S"))
            return Appointment.objects.filter(
                server=server, status__in=["CONFIRMED", "ACCEPTED", "COMPLETED", "NO_SHOW", "CANCELLED"],
                start_datetime__gte=start_date, end_datetime__lte=end_date
            ).select_related(*_full_select).prefetch_related(*_full_prefetch).order_by("id")
        return Appointment.objects.filter(
            server=server, status__in=["CONFIRMED", "ACCEPTED", "COMPLETED", "NO_SHOW", "CANCELLED"]
        ).select_related(*_full_select).prefetch_related(*_full_prefetch)

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["lang_code"] = self.request.LANGUAGE_CODE
        return context

    @action(detail=True, methods=['post'])
    def update_appointment(self, request, pk=None):
        appointment = self.get_object()
        try:
            action_type = request.data.get('action_type')
            comment_by_server = request.data.get('comment_by_server')

            if action_type == 'save_note':
                appointment.comment_by_server = comment_by_server
                appointment.save(update_fields=['comment_by_server'])
                return Response({'success': 'Note saved.'})

            elif action_type == 'change_time':
                new_datetime_str = request.data.get('new_datetime')
                if not new_datetime_str:
                    return Response({'error': 'New datetime is required.'}, status=status.HTTP_400_BAD_REQUEST)
                new_datetime = timezone.make_aware(datetime.fromisoformat(new_datetime_str))
                if new_datetime < timezone.now():
                    return Response({'error': 'New datetime must be in the future.'},
                                    status=status.HTTP_400_BAD_REQUEST)
                appointment.start_datetime = new_datetime
                total_duration = 0
                for s in appointment.appointmentservice_set.select_related(
                    'service'
                ).prefetch_related('service__providerserverservice_set').all():
                    pss_list = list(s.service.providerserverservice_set.all())
                    pss = pss_list[0] if pss_list else None
                    if pss and pss.duration:
                        total_duration += pss.duration
                if total_duration == 0:
                    return Response({'error': 'Could not determine appointment duration.'},
                                    status=status.HTTP_400_BAD_REQUEST)
                appointment.end_datetime = new_datetime + timezone.timedelta(minutes=total_duration)
                appointment.comment_by_server = comment_by_server
                appointment.save()
                return Response({'success': 'Appointment time updated successfully.'})

            elif action_type == 'accept':
                if appointment.status != 'CONFIRMED':
                    return Response({'error': 'Only CONFIRMED appointments can be accepted.'}, status=status.HTTP_400_BAD_REQUEST)
                appointment.status = 'ACCEPTED'
                appointment.comment_by_server = comment_by_server
                appointment.save()
                return Response({'success': 'Appointment accepted.'})

            elif action_type == 'reject':
                if appointment.status not in ('NEW', 'CONFIRMED'):
                    return Response({'error': 'Only NEW or CONFIRMED appointments can be rejected.'}, status=status.HTTP_400_BAD_REQUEST)
                appointment.status = 'REJECTED'
                appointment.comment_by_server = comment_by_server
                appointment.save()
                return Response({'success': 'Appointment rejected.'})

            elif action_type == 'cancel':
                appointment.status = 'CANCELLED'
                appointment.comment_by_server = comment_by_server
                appointment.save()
                return Response({'success': 'Appointment cancelled successfully.'})

            elif action_type == 'no_show':
                appointment.status = 'NO_SHOW'
                appointment.comment_by_server = comment_by_server
                appointment.save()
                return Response({'success': 'Appointment marked as no-show.'})

            else:
                return Response({'error': 'Invalid action type.'}, status=status.HTTP_400_BAD_REQUEST)

        except Exception as e:
            logger.exception("API error")
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=True, methods=['post'], url_path='upload_file')
    def upload_file(self, request, pk=None):
        appointment = self.get_object()
        files = request.FILES.getlist('files')
        if not files:
            return Response({'error': 'No files provided.'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            created = []
            for f in files:
                af = AppointmentFile.objects.create(
                    appointment=appointment,
                    file=f,
                    file_name=f.name,
                )
                created.append(af)
            serializer = AppointmentFileSerializer(created, many=True)
            return Response({'success': 'Files uploaded.', 'files': serializer.data}, status=status.HTTP_201_CREATED)
        except Exception as e:
            logger.exception("API error")
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=True, methods=['delete'], url_path='delete_file')
    def delete_file(self, request, pk=None):
        appointment = self.get_object()
        file_id = request.data.get('file_id')
        try:
            af = AppointmentFile.objects.get(id=file_id, appointment=appointment)
            af.file.delete(save=False)
            af.delete()
            return Response({'success': 'File deleted.'})
        except AppointmentFile.DoesNotExist:
            return Response({'error': 'File not found.'}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.exception("API error")
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['post'])
    def create_guest_appointment(self, request):
        server = request.user.server_user
        try:
            guest_client, _ = Client.objects.get_or_create(
                email="guestclient@gmail.com",
                defaults={"full_name": "Guest Client"},
            )
            # Get the start_date, end_date, and comment from the request body
            start_date_str = request.data.get('start_date')
            end_date_str = request.data.get('end_date')
            comment = request.data.get('comment', '')
            if request.data.get('server_id'):
                server = Server.objects.get(pk=request.data.get('server_id'))

            # Validate the required fields
            if not start_date_str or not end_date_str:
                return Response({'error': 'start_date and end_date are required.'}, status=status.HTTP_400_BAD_REQUEST)

            # Convert the date strings to datetime objects
            start_date = timezone.make_aware(datetime.fromisoformat(start_date_str))
            end_date = timezone.make_aware(datetime.fromisoformat(end_date_str))

            # Validate that the start_date is in the future
            if start_date < timezone.now():
                return Response({'error': 'start_date must be in the future.'}, status=status.HTTP_400_BAD_REQUEST)

            # Validate that the end_date is after the start_date
            if end_date <= start_date:
                return Response({'error': 'end_date must be after start_date.'}, status=status.HTTP_400_BAD_REQUEST)

            ps = server.providerserver_set.first()

            # Check if the selected time is within the server's working hours
            if ps and ps.day_starts_on and ps.day_ends_on:
                start_time = start_date.time()
                if not (ps.day_starts_on <= start_time < ps.day_ends_on):
                    return Response(
                        {'error': f'Appointment time must be within the server\'s working hours ({ps.day_starts_on} - {ps.day_ends_on}).'},
                        status=status.HTTP_400_BAD_REQUEST
                    )

            # Check for overlapping appointments
            overlapping_appointments = Appointment.objects.filter(
                server=server,
                start_datetime__lt=end_date,
                end_datetime__gt=start_date
            )

            if overlapping_appointments.exists():
                return Response({'error': 'The selected time slot is not available.'},
                                status=status.HTTP_400_BAD_REQUEST)

            # Create the appointment
            Appointment.objects.create(
                server=server,
                client=guest_client,
                start_datetime=start_date,
                end_datetime=end_date,
                comment=comment,
                status='ACCEPTED'  # Provider creates directly, no approval needed
            )

            return Response({'success': 'Appointment created successfully.'})

        except Exception as e:
            logger.exception("API error")
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    # ------------------------------------------------------------------
    # Server-initiated appointment creation — new multi-mode endpoints
    # ------------------------------------------------------------------

    @action(detail=False, methods=['get'])
    def search_client(self, request):
        q = request.query_params.get('q', '').strip()
        if len(q) < 3:
            return Response([])
        clients = Client.objects.filter(
            Q(phone_number__icontains=q) | Q(email__icontains=q)
        ).values('id', 'full_name', 'email', 'phone_number')[:10]
        return Response(list(clients))

    @action(detail=False, methods=['post'])
    def send_new_client_otp(self, request):
        contact_type = request.data.get('contact_type')
        contact_value = (request.data.get('contact_value') or '').strip()
        if not contact_value or contact_type not in ('phone', 'email'):
            return Response({'error': 'contact_type and contact_value are required.'}, status=status.HTTP_400_BAD_REQUEST)

        if contact_type == 'phone' and Client.objects.filter(phone_number=contact_value).exists():
            return Response({'error': 'A client with this phone is already registered. Use Existing Client mode.'}, status=status.HTTP_400_BAD_REQUEST)
        if contact_type == 'email' and Client.objects.filter(email=contact_value).exists():
            return Response({'error': 'A client with this email is already registered. Use Existing Client mode.'}, status=status.HTTP_400_BAD_REQUEST)

        otp = OTPVerification.objects.create(
            phone_number=contact_value if contact_type == 'phone' else None,
            email=contact_value if contact_type == 'email' else None,
            verification_method='p' if contact_type == 'phone' else 'e',
            appointment=None,
        )

        lang = getattr(request, 'LANGUAGE_CODE', 'ru')
        if lang == 'uz':
            text = f"booket.uz platformasida ro'yxatdan o'tish kodi: {otp.otp_code}"
        elif lang == 'ru':
            text = f"Код регистрации на платформе booket.uz: {otp.otp_code}"
        else:
            text = f"Registration code for booket.uz: {otp.otp_code}"

        if contact_type == 'phone':
            send_sms(phone_number=contact_value, message=text)
            masked = mask_phone_number(contact_value)
        else:
            send_mail("booket.uz confirmation code", text, "alphadevmanager@gmail.com", [contact_value], fail_silently=False)
            masked = mask_email(contact_value)

        return Response({'otp_id': otp.id, 'masked_contact': masked})

    @action(detail=False, methods=['post'])
    def verify_new_client_otp(self, request):
        otp_id = request.data.get('otp_id')
        otp_code = request.data.get('otp_code')
        try:
            otp = OTPVerification.objects.get(id=otp_id, is_verified=False, appointment=None)
        except OTPVerification.DoesNotExist:
            return Response({'success': False, 'message': 'OTP not found or already used.'}, status=status.HTTP_400_BAD_REQUEST)

        if (timezone.now() - otp.created_at).total_seconds() > 600:
            return Response({'success': False, 'message': 'OTP has expired.'}, status=status.HTTP_400_BAD_REQUEST)

        if otp.attempts >= 5:
            return Response({'success': False, 'message': 'Too many attempts. Request a new OTP.'}, status=status.HTTP_400_BAD_REQUEST)

        if otp.otp_code != otp_code:
            otp.attempts += 1
            otp.save(update_fields=['attempts'])
            remaining = 5 - otp.attempts
            return Response({'success': False, 'message': f'Incorrect code. {remaining} attempt(s) remaining.'}, status=status.HTTP_400_BAD_REQUEST)

        otp.is_verified = True
        otp.save(update_fields=['is_verified'])
        return Response({'success': True})

    @action(detail=False, methods=['post'])
    def create_server_appointment(self, request):
        try:
            server = request.user.server_user
        except AttributeError:
            return Response({'error': 'Only server users can use this endpoint.'}, status=status.HTTP_403_FORBIDDEN)

        if request.data.get('server_id'):
            server = get_object_or_404(Server, pk=request.data['server_id'])

        client_mode = request.data.get('client_mode', 'guest')
        start_date_str = request.data.get('start_date')
        end_date_str = request.data.get('end_date')
        comment = request.data.get('comment', '')
        service_ids = request.data.get('service_ids', [])

        if not start_date_str:
            return Response({'error': 'start_date is required.'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            start_date = timezone.make_aware(datetime.fromisoformat(start_date_str))
        except ValueError:
            return Response({'error': 'Invalid start_date format.'}, status=status.HTTP_400_BAD_REQUEST)

        # Resolve client
        if client_mode == 'guest':
            client, _ = Client.objects.get_or_create(
                email="guestclient@gmail.com",
                defaults={"full_name": "Guest Client"},
            )
            otp = None
        elif client_mode == 'existing':
            client_id = request.data.get('client_id')
            if not client_id:
                return Response({'error': 'client_id is required for existing client mode.'}, status=status.HTTP_400_BAD_REQUEST)
            client = get_object_or_404(Client, id=client_id, is_active=True)
            otp = None
        elif client_mode == 'new':
            otp_id = request.data.get('otp_id')
            client_data = request.data.get('client') or {}
            if not otp_id:
                return Response({'error': 'otp_id is required for new client mode.'}, status=status.HTTP_400_BAD_REQUEST)
            try:
                otp = OTPVerification.objects.get(id=otp_id, is_verified=True, appointment=None)
            except OTPVerification.DoesNotExist:
                return Response({'error': 'OTP not verified. Verify the client first.'}, status=status.HTTP_400_BAD_REQUEST)
            full_name = (client_data.get('full_name') or '').strip()
            if not full_name:
                return Response({'error': 'Client full name is required.'}, status=status.HTTP_400_BAD_REQUEST)
            client = Client.objects.create(
                full_name=full_name,
                phone_number=client_data.get('phone_number') or None,
                email=client_data.get('email') or None,
            )
        else:
            return Response({'error': 'Invalid client_mode. Use guest, existing, or new.'}, status=status.HTTP_400_BAD_REQUEST)

        # Calculate end_date — from services if provided, otherwise from explicit value
        end_date = None
        if service_ids:
            pss_qs = ProviderServerService.objects.filter(
                service__id__in=service_ids,
                provider_server__server=server,
            )
            total_minutes = sum(pss.duration for pss in pss_qs if pss.duration)
            if total_minutes:
                end_date = start_date + timezone.timedelta(minutes=total_minutes)

        if end_date is None:
            if not end_date_str:
                return Response({'error': 'end_date is required when no services are selected.'}, status=status.HTTP_400_BAD_REQUEST)
            try:
                end_date = timezone.make_aware(datetime.fromisoformat(end_date_str))
            except ValueError:
                return Response({'error': 'Invalid end_date format.'}, status=status.HTTP_400_BAD_REQUEST)

        if start_date < timezone.now():
            return Response({'error': 'start_date must be in the future.'}, status=status.HTTP_400_BAD_REQUEST)
        if end_date <= start_date:
            return Response({'error': 'end_date must be after start_date.'}, status=status.HTTP_400_BAD_REQUEST)

        ps = server.providerserver_set.first()
        if ps and ps.day_starts_on and ps.day_ends_on:
            if not (ps.day_starts_on <= start_date.time() < ps.day_ends_on):
                return Response(
                    {'error': f'Appointment must be within working hours ({ps.day_starts_on} - {ps.day_ends_on}).'},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        if Appointment.objects.filter(server=server, start_datetime__lt=end_date, end_datetime__gt=start_date).exists():
            return Response({'error': 'The selected time slot is not available.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            with transaction.atomic():
                if client_mode != 'guest' and ps:
                    ProviderClient.objects.get_or_create(provider=ps.provider, client=client)

                appointment = Appointment.objects.create(
                    server=server,
                    client=client,
                    start_datetime=start_date,
                    end_datetime=end_date,
                    comment=comment,
                    status='ACCEPTED',
                )

                if service_ids:
                    for svc in Service.objects.filter(id__in=service_ids):
                        AppointmentService.objects.create(appointment=appointment, service=svc)

                if otp is not None:
                    otp.appointment = appointment
                    otp.save(update_fields=['appointment'])

            return Response({'success': 'Appointment created successfully.', 'appointment_id': appointment.id})
        except Exception as e:
            logger.exception("API error on create_server_appointment")
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
