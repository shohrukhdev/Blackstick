from dent.serializers import *
from .models import *
from rest_framework import viewsets


class PatientViewSet(viewsets.ModelViewSet):
    queryset = Patient.objects.all()
    serializer_class = PatientSerializer

    def get_queryset(self):
        staff = Staff.objects.get(user=self.request.user)
        return Patient.objects.filter(clinic=staff.clinic)


class DebtViewSet(viewsets.ModelViewSet):
    queryset = Treatment.objects.all()
    serializer_class = DebtSerializer


class TreatmentViewSet(viewsets.ModelViewSet):
    queryset = Treatment.objects.all()
    serializer_class = TreatmentSerializer

    def get_queryset(self):
        return Treatment.objects.filter(
            doctor__user=self.request.user
        )
