from datetime import datetime
from urllib.parse import unquote

from django.utils import timezone
from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated

from booket.dashboard.serializers import AppointmentSerializer
from booket.models import Appointment


class AppointmentViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = AppointmentSerializer
    pagination_class = None
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        server = self.request.user.server_user
        start_date = unquote(self.request.query_params.get("start")[0:19])
        end_date = unquote(self.request.query_params.get("end")[0:19])
        if start_date and end_date:
            start_date = timezone.make_aware(datetime.strptime(start_date, "%Y-%m-%dT%H:%M:%S"))
            end_date = timezone.make_aware(datetime.strptime(end_date, "%Y-%m-%dT%H:%M:%S"))
            return Appointment.objects.filter(
                server=server, status__in=["CONFIRMED", "ACCEPTED", "COMPLETED"], start_datetime__gte=start_date, end_datetime__lte=end_date
            ).prefetch_related("appointmentservice_set__service").order_by("id")
        return Appointment.objects.filter(
            server=server, status__in=["CONFIRMED", "ACCEPTED", "COMPLETED"]
        ).prefetch_related("appointmentservice_set__service")

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["lang_code"] = self.request.LANGUAGE_CODE
        return context
