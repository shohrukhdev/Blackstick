from django.contrib.auth.models import User
from django.db import models


class Provider(models.Model):
    name = models.CharField(max_length=255, null=True, blank=True)
    logo = models.ImageField(upload_to='logo', null=True, blank=True)
    description = models.TextField(null=True, blank=True)
    address = models.CharField(max_length=255, null=True, blank=True)
    owner = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
    is_active = models.BooleanField(default=True)
    has_many_servers = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

    @staticmethod
    def is_user_owner(user):
        """
        Check if the given user is the owner of any Provider.
        Returns True if the user is an owner, otherwise False.
        """
        return Provider.objects.filter(owner=user).exists()


class Server(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='server_user')
    image = models.ImageField(upload_to='server', null=True, blank=True)
    phone_number = models.CharField(max_length=255, null=True, blank=True)
    info = models.TextField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    created = models.DateTimeField(auto_now_add=True)

    @staticmethod
    def is_user_server(user):
        """
        Check if the given user is the owner of any Provider.
        Returns True if the user is an owner, otherwise False.
        """
        return Server.objects.filter(user=user).exists()

    def __str__(self):
        return f"{self.user.get_full_name()}"


class ServiceType(models.Model):
    provider = models.ForeignKey(Provider, on_delete=models.CASCADE, related_name='service_type')
    name = models.CharField(max_length=150, null=True, blank=True)
    name_uz = models.CharField(max_length=150, null=True, blank=True)
    name_ru = models.CharField(max_length=150, null=True, blank=True)
    description = models.TextField(null=True, blank=True)
    initial_price = models.IntegerField(null=True, blank=True)
    is_active = models.BooleanField(default=True)


class ProviderServer(models.Model):  # Provider can have many servers and server can work for multiple providers
    provider = models.ForeignKey(Provider, on_delete=models.CASCADE)
    server = models.ForeignKey(Server, on_delete=models.CASCADE, null=True, blank=True)
    day_starts_on = models.TimeField(null=True, blank=True)
    day_ends_on = models.TimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.provider} {self.server}"


class Service(models.Model):
    tip = models.ForeignKey(ServiceType, on_delete=models.CASCADE)
    server = models.ForeignKey(Server, on_delete=models.CASCADE, null=True, blank=True)
    name = models.CharField(max_length=255, null=True, blank=True)
    name_uz = models.CharField(max_length=255, null=True, blank=True)
    name_ru = models.CharField(max_length=255, null=True, blank=True)
    description = models.TextField(null=True, blank=True)
    price = models.IntegerField(null=True, blank=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.name_uz


class ProviderServerService(models.Model):   # Services are performed by the servers of the provider
    provider_server = models.ForeignKey(ProviderServer, on_delete=models.CASCADE, null=True, blank=True)
    service = models.ForeignKey(Service, on_delete=models.CASCADE, null=True, blank=True)


def default_day_off():
    return [6, 7]  # default day offs of the week


class WeekSchedule(models.Model):
    service_provider = models.ForeignKey(Provider, on_delete=models.CASCADE, null=True, blank=True)
    server = models.ForeignKey(Server, on_delete=models.CASCADE, null=True, blank=True)
    date_start = models.DateField(null=True, blank=True)
    date_end = models.DateField(null=True, blank=True)
    off_days = models.JSONField(default=default_day_off, null=True, blank=True)


class Client(models.Model):
    service_provider = models.ForeignKey(Provider, on_delete=models.CASCADE)
    full_name = models.CharField(max_length=255, null=True, blank=True)
    phone_number = models.CharField(max_length=13, null=True, blank=True)
    sex = models.CharField(max_length=10, null=True, blank=True)

    class Meta:
        unique_together = ('full_name', 'phone_number', 'service_provider')


STATUSES = [
    ("PENDING", "PENDING"),  # waiting for a provider to confirm
    ("CONFIRMED", "CONFIRMED"),  # confirmed by the provider
    ("CANCELLED", "CANCELLED"),  # cancelled by the provider or client
    ("REJECTED", "REJECTED"),  # rejected by the provider
    ("COMPLETED", "COMPLETED"),  # completed
]


class Appointment(models.Model):
    client = models.ForeignKey(Client, on_delete=models.CASCADE, null=True, blank=True)
    server = models.ForeignKey(Server, on_delete=models.CASCADE)
    start_datetime = models.DateTimeField(null=True, blank=True)
    end_datetime = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=12, choices=STATUSES, null=True, blank=True)
    title = models.CharField(max_length=255, null=True, blank=True)
    comment = models.TextField(null=True, blank=True)

    def __str__(self):
        return f"{self.client} {self.server} {self.start_datetime} -- {self.end_datetime}"


class AppointmentService(models.Model):
    appointment = models.ForeignKey(Appointment, on_delete=models.CASCADE, null=True, blank=True)
    service = models.ForeignKey(Service, on_delete=models.CASCADE, null=True, blank=True)

    def __str__(self):
        return f"{self.appointment} {self.service}"







