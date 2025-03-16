from django.shortcuts import get_object_or_404
from django.views.decorators.csrf import csrf_protect
from rest_framework import generics, viewsets
from rest_framework.decorators import action
from rest_framework.throttling import AnonRateThrottle
from rest_framework.views import APIView

from booket.models import ProviderServer, Client
from .serializers import ProviderServerSerializer, ClientSerializer
from rest_framework.response import Response
from datetime import datetime

from ..utils import validate_signature


class ProviderServerDetailView(generics.RetrieveAPIView):
    throttle_classes = [AnonRateThrottle]
    serializer_class = ProviderServerSerializer

    def get(self, request, p_server_id):
        if not validate_signature(request):
            return Response({"error": "Invalid request headers"}, status=400)
        try:
            provider_server = ProviderServer.objects.get(id=p_server_id)
            serializer = self.serializer_class(provider_server)
            return Response(serializer.data)
        except ProviderServer.DoesNotExist:
            return Response({"error": "Provider Server not found"}, status=404)


class AvailableTimeSlotsView(APIView):
    throttle_classes = [AnonRateThrottle]
    def get(self, request, p_server_id):
        if not validate_signature(request):
            return Response({"error": "Invalid request headers"}, status=400)
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


class ClientViewSet(viewsets.ReadOnlyModelViewSet):
    throttle_classes = [AnonRateThrottle]
    queryset = Client.objects.all()
    serializer_class = ClientSerializer

    @action(detail=False, methods=["get"])
    def search(self, request):
        if not validate_signature(request):
            return Response({"error": "Invalid request headers"}, status=400)
        email = request.query_params.get("email")
        phone_number = request.query_params.get("phone_number")

        if email:
            client = get_object_or_404(Client, email=email)
        elif phone_number:
            client = get_object_or_404(Client, phone_number=phone_number)
        else:
            return Response({"error": "Provide either email or phone_number"}, status=400)

        serializer = self.get_serializer(client)
        return Response(serializer.data)
