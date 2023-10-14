from rest_framework import serializers
from .models import *


class EventSerializer(serializers.ModelSerializer):
    start = serializers.DateTimeField(format="%Y-%m-%dT%H:%M", source="start_time", read_only=True)
    end = serializers.DateTimeField(format="%Y-%m-%dT%H:%M", source="end_time", read_only=True, required=False)
    allDay = serializers.BooleanField(source="all_day", read_only=True)
    backgroundColor = serializers.CharField(source="background_color", read_only=True)
    borderColor = serializers.CharField(source="border_color", read_only=True)
    textColor = serializers.CharField(source="text_color", read_only=True)
    patient_id = serializers.IntegerField(source="patient.id", read_only=True)
    patient_name = serializers.CharField(source="patient.full_name", read_only=True)
    patient_phone = serializers.CharField(source='patient.mobile_phone')
    start_format = serializers.DateTimeField(format="%d.%m.%Y %H:%M", source="start_time", read_only=True)
    end_format = serializers.DateTimeField(format="%d.%m.%Y %H:%M", source="end_time", read_only=True)

    class Meta:
        model = Event
        fields = ('id',
                  'stuff',
                  'patient_id',
                  'patient_name',
                  'patient_phone',
                  'title',
                  'description',
                  'start',
                  'end',
                  'allDay',
                  'backgroundColor',
                  'borderColor',
                  'textColor',
                  'status',
                  'display',
                  'start_format',
                  'end_format')


class PatientSerializer(serializers.ModelSerializer):
    birth_date = serializers.DateField(source='date_birth', format='%d.%m.%Y')

    class Meta:
        model = Patient
        fields = ('id',
                  'reference_id',
                  'full_name',
                  'mobile_phone',
                  'sex',
                  'birth_date')


class DebtSerializer(serializers.ModelSerializer):
    class Meta:
        model = Treatment
        fields = '__all__'
