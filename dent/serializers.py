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
                  'staff',
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
    created_by = serializers.CharField(source='cr_by.user.get_full_name')

    class Meta:
        model = Patient
        fields = ('id',
                  'reference_id',
                  'full_name',
                  'mobile_phone',
                  'sex',
                  'birth_date',
                  'created_by',
                  )


class DebtSerializer(serializers.ModelSerializer):
    class Meta:
        model = Treatment
        fields = '__all__'


class StaffServiceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Staff
        fields = '__all__'


class TreatmentSerializer(serializers.ModelSerializer):
    created_on = serializers.DateTimeField(format="%d.%m.%Y %H:%M", source="cr_on", read_only=True)
    doctor_full_name = serializers.CharField(source="doctor.user.get_full_name", read_only=True)
    patient_full_name = serializers.CharField(source="patient.full_name", read_only=True)
    mobile_phone_number = serializers.CharField(source="patient.mobile_phone")
    payment = serializers.SerializerMethodField()

    def get_payment(self, obj):
        return int(obj.total_amount * (100 - obj.discount)/100)

    class Meta:
        model = Treatment
        exclude = ()
        fields = [
            'reference_id',
            'doctor_full_name',
            'patient_full_name',
            'mobile_phone_number',
            'created_on',
            'payment',
            'cr_on',
            'cr_by'
        ]
