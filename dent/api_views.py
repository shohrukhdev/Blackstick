from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated

from .serializers import *
from .models import *
from datetime import datetime
from urllib.parse import unquote


class EventViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Event.objects.all()
    serializer_class = EventSerializer
    pagination_class = None
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        start_date = datetime.strptime(unquote(self.request.query_params['start'])[0:10], '%Y-%m-%d')
        end_date = datetime.strptime(unquote(self.request.query_params['end'])[0:10], '%Y-%m-%d')
        return Event.objects.filter(staff__user=self.request.user, start_time__range=(start_date, end_date), status=1)


class EventListViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Event.objects.all()
    serializer_class = EventSerializer
    pagination_class = None
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Event.objects.filter(staff__user=self.request.user, status=1, start_time__gte=datetime.now()).order_by('start_time')


class ReceptionEventViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Event.objects.all()
    serializer_class = EventSerializer
    pagination_class = None
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        clinic_id = self.request.session.get("clinic_id")
        return Event.objects.filter(
            patient__clinic_id=clinic_id
        )
