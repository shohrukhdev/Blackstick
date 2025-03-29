import logging
import traceback
from datetime import datetime
from urllib.parse import unquote

from django.utils import timezone
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from booket.dashboard.serializers import AppointmentSerializer
from booket.models import Appointment

logger = logging.getLogger(__name__)


class AppointmentViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = AppointmentSerializer
    pagination_class = None
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        if self.action == 'update_appointment':
            return Appointment.objects.filter(pk=self.request.data.get('appointment_id'))

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
        server = request.user.server_user
        try:
            action_type = request.data.get('action_type')

            if action_type == 'change_time':
                new_datetime_str = request.data.get('new_datetime')
                if not new_datetime_str:
                    return Response({'error': 'New datetime is required.'}, status=status.HTTP_400_BAD_REQUEST)
                new_datetime = timezone.make_aware(datetime.fromisoformat(new_datetime_str))
                if new_datetime < timezone.now():
                    return Response({'error': 'New datetime must be in the future.'},
                                    status=status.HTTP_400_BAD_REQUEST)
                appointment.start_datetime = new_datetime
                # Calculate new end_datetime based on the duration of the services
                total_duration = sum(
                    s.service.providerserverservice_set.first().duration for s in
                    appointment.appointmentservice_set.all())
                appointment.end_datetime = new_datetime + timezone.timedelta(minutes=total_duration)
                appointment.comment = request.data.get('comment')
                appointment.save()
                return Response({'success': 'Appointment time updated successfully.'})

            elif action_type == 'cancel':
                appointment.status = 'CANCELLED'
                appointment.comment = request.data.get('comment')
                appointment.save()
                return Response({'success': 'Appointment cancelled successfully.'})

            elif action_type == 'no_show':
                appointment.status = 'NO_SHOW'
                appointment.comment = request.data.get('comment')
                appointment.save()
                return Response({'success': 'Appointment marked as no-show.'})

            else:
                return Response({'error': 'Invalid action type.'}, status=status.HTTP_400_BAD_REQUEST)

        except Exception as e:
            logger.error(traceback.format_exc())
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
