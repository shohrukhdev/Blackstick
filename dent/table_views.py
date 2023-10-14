from dent.serializers import *
from .models import *
from rest_framework import viewsets


class PatientViewSet(viewsets.ModelViewSet):
    queryset = Patient.objects.all()
    serializer_class = PatientSerializer

    def get_queryset(self):
        stuff = Stuff.objects.get(user=self.request.user)
        return Patient.objects.filter(clinic=stuff.clinic)


class DebtViewSet(viewsets.ModelViewSet):
    queryset = Treatment.objects.all()
    serializer_class = DebtSerializer
