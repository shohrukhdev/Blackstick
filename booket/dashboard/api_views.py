import logging
from datetime import datetime
from urllib.parse import unquote
from django.utils import timezone
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from booket.dashboard.serializers import AppointmentSerializer, AppointmentFileSerializer
from booket.models import Appointment, AppointmentFile, Provider, Client, Server

logger = logging.getLogger(__name__)


class AppointmentViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = AppointmentSerializer
    pagination_class = None
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        if self.action in ('update_appointment', 'upload_file', 'delete_file'):
            try:
                return Appointment.objects.filter(server=self.request.user.server_user)
            except Exception:
                provider = Provider.objects.get(owner=self.request.user)
                return Appointment.objects.filter(server__providerserver__provider=provider)

        if self.request.query_params.get("viewby") and self.request.query_params.get("viewby") == "provider":
            provider = Provider.objects.get(owner=self.request.user)
            return Appointment.objects.filter(
                server__providerserver__provider=provider,
                status__in=["CONFIRMED", "ACCEPTED", "COMPLETED", "NO_SHOW", "CANCELLED"]
            ).order_by("start_datetime")

        if self.request.query_params.get("format") and self.request.query_params.get("format") == "datatables":
            return Appointment.objects.filter(
                server=self.request.user.server_user,
                status__in=["CONFIRMED", "ACCEPTED", "COMPLETED", "NO_SHOW", "CANCELLED"]

            ).order_by("start_datetime")

        server = self.request.user.server_user
        start_date = unquote(self.request.query_params.get("start")[0:19])
        end_date = unquote(self.request.query_params.get("end")[0:19])
        if start_date and end_date:
            start_date = timezone.make_aware(datetime.strptime(start_date, "%Y-%m-%dT%H:%M:%S"))
            end_date = timezone.make_aware(datetime.strptime(end_date, "%Y-%m-%dT%H:%M:%S"))
            return Appointment.objects.filter(
                server=server, status__in=["CONFIRMED", "ACCEPTED", "COMPLETED", "NO_SHOW", "CANCELLED"], start_datetime__gte=start_date, end_datetime__lte=end_date
            ).prefetch_related("appointmentservice_set__service").order_by("id")
        return Appointment.objects.filter(
            server=server, status__in=["CONFIRMED", "ACCEPTED", "COMPLETED", "NO_SHOW", "CANCELLED"]
        ).prefetch_related("appointmentservice_set__service")

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
                total_duration = sum(
                    s.service.providerserverservice_set.first().duration for s in
                    appointment.appointmentservice_set.all())
                appointment.end_datetime = new_datetime + timezone.timedelta(minutes=total_duration)
                appointment.comment_by_server = comment_by_server
                appointment.save()
                return Response({'success': 'Appointment time updated successfully.'})

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
            guest_client = Client.objects.get(email="guestclient@gmail.com")
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
            if ps.day_starts_on and ps.day_ends_on:
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
                status='CONFIRMED'  # Default status for the appointment
            )

            return Response({'success': 'Appointment created successfully.'})

        except Exception as e:
            logger.exception("API error")
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
