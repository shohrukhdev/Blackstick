from datetime import datetime, timedelta

from rest_framework import serializers
from collections import defaultdict
from booket.models import ProviderServer, ProviderServerService, Service, ServiceType, \
    Appointment  # Assuming ServiceType exists


class ServiceSerializer(serializers.ModelSerializer):
    service_private_price = serializers.SerializerMethodField()
    duration = serializers.SerializerMethodField()

    class Meta:
        model = Service
        fields = [
            'id',
            'name',
            'name_uz',
            'name_ru',
            'description',
            'price',
            'is_active',
            'service_private_price',
            'duration'
        ]

    def get_service_private_price(self, obj):
        """ Fetch private price from the ProviderServerService relation. """
        provider_service = self.context.get("provider_services", {}).get(obj.id)
        return provider_service.service_private_price if provider_service else None

    def get_duration(self, obj):
        """ Fetch duration from the ProviderServerService relation. """
        provider_service = self.context.get("provider_services", {}).get(obj.id)
        return provider_service.duration if provider_service else None


class ServiceTypeSerializer(serializers.ModelSerializer):
    services = serializers.SerializerMethodField()

    class Meta:
        model = ServiceType
        fields = ['id', 'name', 'name_uz', 'name_ru', 'services']

    def get_services(self, obj):
        """ Return services filtered by service type. """
        services_by_type = self.context.get("services_by_type", {})
        services = services_by_type.get(obj.id, [])
        return ServiceSerializer(services, many=True, context=self.context).data


class ProviderServerSerializer(serializers.ModelSerializer):
    service_types = serializers.SerializerMethodField()
    available_time_slots = serializers.SerializerMethodField()

    class Meta:
        model = ProviderServer
        fields = [
            'id',
            'provider_id',
            'server_id',
            'day_starts_on',
            'day_ends_on',
            'off_days',
            'service_types',
            'available_time_slots'
        ]

    @staticmethod
    def get_service_types(obj):
        """ Fetch and group services by their type. """
        provider_services = ProviderServerService.objects.filter(
            provider_server=obj, service__is_active=True
        ).select_related("service__tip")  # `tip` is the service type

        # Mapping services to their IDs for efficient lookup
        service_map = {ps.service.id: ps for ps in provider_services}

        # Group services by their type
        services_by_type = defaultdict(list)
        for ps in provider_services:
            services_by_type[ps.service.tip_id].append(ps.service)

        # Fetch only required service types
        service_types = ServiceType.objects.filter(id__in=services_by_type.keys())

        return ServiceTypeSerializer(
            service_types, many=True, context={
                "services_by_type": services_by_type,
                "provider_services": service_map
            }
        ).data

    def get_available_time_slots(self, obj):
        return self._calculate_available_slots(obj, datetime.today().date())

    def _calculate_available_slots(self, obj, start_date):
        """
        Generate available time slots for the next 5 days considering off days and booked appointments.
        """
        available_slots = []
        current_date = datetime.strptime(str(start_date), "%Y-%m-%d").date()

        for _ in range(5):
            weekday = current_date.isoweekday()  # 1 = Monday, 7 = Sunday
            if str(weekday) not in obj.get_off_days():
                slots = self._generate_time_slots(obj, current_date)
                available_slots.append({"date": current_date, "slots": slots})

            current_date += timedelta(days=1)

        return available_slots

    def _generate_time_slots(self, obj, date):
        """
        Generate available time slots for a given date by checking booked appointments.
        """
        if not obj.day_starts_on or not obj.day_ends_on:
            return []

        start_time = obj.day_starts_on
        end_time = obj.day_ends_on
        slot_duration = 30  # Default to 30 minutes

        # Get current time if checking today's slots
        now = datetime.now().time()
        if date == datetime.today().date():
            # Round current time to the next half-hour mark
            next_half_hour = (datetime.now() + timedelta(minutes=(30 - datetime.now().minute % 30))).time()
            start_time = max(start_time, next_half_hour)  # Ensure it does not go below `day_starts_on`

        booked_appointments = Appointment.objects.filter(
            server=obj.server,
            start_datetime__date=date
        ).values_list("start_datetime", "end_datetime")

        slots = []
        current_slot = datetime.combine(date, start_time)

        while current_slot.time() < end_time:
            slot_end = current_slot + timedelta(minutes=slot_duration)

            # Check if the slot is already booked
            is_booked = any(start <= current_slot < end for start, end in booked_appointments)
            if not is_booked:
                slots.append(current_slot.strftime("%H:%M"))

            current_slot = slot_end

        return slots
