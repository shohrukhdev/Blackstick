from django.template.context_processors import request
from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated

from booket.dashboard.serializers import AppointmentDtSerializer
from booket.models import Appointment, Provider


class AppointmentDtViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Appointment
    serializer_class = AppointmentDtSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        if self.request.query_params.get("viewby") and self.request.query_params.get("viewby") == "provider":
            provider = Provider.objects.get(owner=self.request.user)
            return Appointment.objects.filter(
                server__providerserver__provider=provider,
                status__in=["CONFIRMED", "PENDING", "ACCEPTED", "CANCELLED", "NO_SHOW", "COMPLETED", "REJECTED"]
            ).order_by("-start_datetime")

        return Appointment.objects.filter(
            server=self.request.user.server_user,
            status__in=["CONFIRMED", "PENDING", "ACCEPTED", "CANCELLED", "NO_SHOW", "COMPLETED", "REJECTED"]
        ).order_by("-start_datetime")

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["lang_code"] = self.request.LANGUAGE_CODE
        return context


class ProviderAppointmentDtViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Appointment
    serializer_class = AppointmentDtSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Appointment.objects.filter(
            server__provider__owner=self.request.user,
            satatus__in=["CONFIRMED", "ACCEPTED", "CANCELLED", "NO_SHOW", "COMPLETED", "REJECTED"]
        ).order_by("-start_datetime")
