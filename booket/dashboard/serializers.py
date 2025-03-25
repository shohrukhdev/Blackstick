from rest_framework import serializers

from booket.models import AppointmentService, Appointment


class AppointmentServiceSerializer(serializers.ModelSerializer):
    name = serializers.SerializerMethodField()
    duration = serializers.SerializerMethodField()
    price = serializers.SerializerMethodField()

    class Meta:
        model = AppointmentService
        fields = ["id", "name", "duration", "price"]

    def get_name(self, obj):
        lang_code = self.context.get("lang_code")
        if lang_code == "uz":
            return obj.service.name_uz
        elif lang_code == "ru":
            return obj.service.name_ru
        else:
            return obj.service.name

    def get_duration(self, obj):
        return obj.service.providerserverservice_set.first().duration

    def get_price(self, obj):
        if obj.service.providerserverservice_set.first().service_private_price:
            return obj.service.providerserverservice_set.first().service_private_price
        return obj.service.providerserverservice_set.first().service.price


class AppointmentSerializer(serializers.ModelSerializer):
    start = serializers.DateTimeField(format="%Y-%m-%dT%H:%M", source="start_datetime", read_only=True)
    end = serializers.DateTimeField(format="%Y-%m-%dT%H:%M", source="end_datetime", read_only=True)
    title = serializers.SerializerMethodField()
    client_name = serializers.CharField(source="client.full_name", read_only=True)
    client_phone = serializers.CharField(source="client.phone_number", read_only=True)
    client_email = serializers.CharField(source="client.email", read_only=True)
    status = serializers.CharField(read_only=True)
    services = AppointmentServiceSerializer(many=True, read_only=True, source="appointmentservice_set")

    class Meta:
        model = Appointment
        fields = [
            "id",
            "start",
            "end",
            "title",
            "client_name",
            "client_phone",
            "client_email",
            "services",
            "comment",
            "status"
        ]

    def get_title(self, obj):
        return f"{obj.client.full_name}"

