from rest_framework import generics
from rest_framework.views import APIView

from booket.models import ProviderServer
from .serializers import ProviderServerSerializer
from rest_framework.response import Response
from datetime import datetime


class ProviderServerDetailView(generics.RetrieveAPIView):
    serializer_class = ProviderServerSerializer

    def get(self, request, p_server_id):
        try:
            provider_server = ProviderServer.objects.get(id=p_server_id)
            serializer = self.serializer_class(provider_server)
            return Response(serializer.data)
        except ProviderServer.DoesNotExist:
            return Response({"error": "Provider Server not found"}, status=404)


class AvailableTimeSlotsView(APIView):
    def get(self, request, p_server_id):
        provider_server = ProviderServer.objects.filter(id=p_server_id).first()
        if not provider_server:
            return Response({"error": "Provider Server not found"}, status=404)
        start_date = request.GET.get('start_date')
        if (
            start_date
            and
            datetime.strptime(str(start_date), "%Y-%m-%d").date() < datetime.today().date()
        ):
            start_date = datetime.today().date()
        serializer = ProviderServerSerializer()
        available_slots = serializer._calculate_available_slots(provider_server, start_date)

        return Response({"available_slots": available_slots})
