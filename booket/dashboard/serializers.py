from rest_framework import serializers

from booket.models import AppointmentService, Appointment, AppointmentFile, Server


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


class ServerSerializer(serializers.ModelSerializer):
    full_name = serializers.SerializerMethodField()

    class Meta:
        model = Server
        fields = ["id", "user", "full_name"]

    def get_full_name(self, obj):
        return obj.user.get_full_name()


class AppointmentFileSerializer(serializers.ModelSerializer):
    url = serializers.SerializerMethodField()

    class Meta:
        model = AppointmentFile
        fields = ['id', 'file_name', 'url', 'uploaded_at']

    def get_url(self, obj):
        return obj.file.url


class AppointmentSerializer(serializers.ModelSerializer):
    start = serializers.DateTimeField(format="%Y-%m-%dT%H:%M", source="start_datetime", read_only=True)
    end = serializers.DateTimeField(format="%Y-%m-%dT%H:%M", source="end_datetime", read_only=True)
    title = serializers.SerializerMethodField()
    client_name = serializers.CharField(source="client.full_name", read_only=True)
    client_phone = serializers.CharField(source="client.phone_number", read_only=True)
    client_email = serializers.CharField(source="client.email", read_only=True)
    status = serializers.CharField(read_only=True)
    services = AppointmentServiceSerializer(many=True, read_only=True, source="appointmentservice_set")
    server = ServerSerializer(many=False, read_only=True)
    files = AppointmentFileSerializer(many=True, read_only=True)

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
            "comment_by_server",
            "status",
            "server",
            "files",
        ]

    def get_title(self, obj):
        return f"{obj.client.full_name}"


class AppointmentDtSerializer(serializers.ModelSerializer):
    client_name = serializers.CharField(source="client.full_name", read_only=True)
    client_phone = serializers.CharField(source="client.phone_number", read_only=True)
    client_email = serializers.CharField(source="client.email", read_only=True)
    server_name = serializers.CharField(source="server.user.get_full_name", read_only=True)
    apptmt_date = serializers.DateTimeField(format="%d.%m.%Y", source="start_datetime", read_only=True)
    start_time = serializers.DateTimeField(format="%H:%M", source="start_datetime", read_only=True)
    end_time = serializers.DateTimeField(format="%H:%M", source="end_datetime", read_only=True)
    status = serializers.CharField(read_only=True)
    comment = serializers.CharField(read_only=True)
    time_slot = serializers.SerializerMethodField()
    services = AppointmentServiceSerializer(many=True, read_only=True, source="appointmentservice_set")
    files = AppointmentFileSerializer(many=True, read_only=True)

    class Meta:
        model = Appointment
        fields = [
            "id",
            "client_name",
            "client_email",
            "client_phone",
            "apptmt_date",
            "start_time",
            "end_time",
            "time_slot",
            "status",
            "comment",
            "comment_by_server",
            "server_name",
            "services",
            "files",
        ]

    def get_time_slot(self, obj):
        return f"{obj.start_datetime.strftime('%H:%M')} - {obj.end_datetime.strftime('%H:%M')}"
