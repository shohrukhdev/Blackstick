from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated

from booket.dashboard.serializers import AppointmentDtSerializer
from booket.models import Appointment


class AppointmentDtViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Appointment
    serializer_class = AppointmentDtSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Appointment.objects.filter(
            server=self.request.user.server_user,
            status__in=["CONFIRMED", "PENDING", "ACCEPTED", "CANCELLED", "NO_SHOW", "COMPLETED", "REJECTED"]
        ).order_by("-start_datetime")

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["lang_code"] = self.request.LANGUAGE_CODE
        return context
