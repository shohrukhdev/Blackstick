import logging
import random

from django.contrib.auth.models import User
from django.db.models import JSONField
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import UniqueConstraint, Q, CheckConstraint

logger = logging.getLogger('booket')  # Use the app's logger


class Provider(models.Model):
    name = models.CharField(max_length=255, null=True, blank=True)
    identifier = models.CharField(max_length=255, unique=True)
    logo = models.ImageField(upload_to='logo', null=True, blank=True)
    description = models.TextField(null=True, blank=True)
    address = models.TextField(null=True, blank=True)
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    specialists_section_text = models.CharField(max_length=255, null=True, blank=True)
    specialists_section_text_2 = models.TextField(null=True, blank=True)
    footer_text = models.TextField(null=True, blank=True)
    phone_numbers = JSONField(default=list, blank=True, null=True)
    social_media = JSONField(default=list, blank=True, null=True)
    owner = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
    is_active = models.BooleanField(default=True)
    has_many_servers = models.BooleanField(default=False)
    auto_accept = models.BooleanField(default=True, help_text="Automatically accept appointments after OTP verification. Disable to require manual acceptance via dashboard.")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name or self.identifier

    @staticmethod
    def is_user_owner(user):
        """
        Check if the given user is the owner of any Provider.
        Returns True if the user is an owner, otherwise False.
        """
        return Provider.objects.filter(owner=user).exists()


class ProviderPhotos(models.Model):
    provider = models.ForeignKey(Provider, on_delete=models.CASCADE)
    photo = models.ImageField(upload_to='photos', null=True, blank=True)


class Server(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='server_user')
    image = models.ImageField(upload_to='server', null=True, blank=True)
    phone_number = models.CharField(max_length=255, null=True, blank=True)
    memo = models.TextField(null=True, blank=True)
    title = models.CharField(null=True, blank=True, max_length=255)
    title_uz = models.CharField(null=True, blank=True, max_length=255)
    title_ru = models.CharField(null=True, blank=True, max_length=255)
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
    is_active = models.BooleanField(default=True)


class ProviderServer(models.Model):  # Provider can have many servers and server can work for multiple providers
    provider = models.ForeignKey(Provider, on_delete=models.CASCADE)
    server = models.ForeignKey(Server, on_delete=models.CASCADE, null=True, blank=True)
    day_starts_on = models.TimeField(null=True, blank=True)
    day_ends_on = models.TimeField(null=True, blank=True)
    # Store off days as a comma-separated string (e.g., "1,5" for Monday and Friday off)
    off_days = models.CharField(max_length=100, blank=True, null=True)  # Blank means no off days by default

    def __str__(self):
        return f"{self.provider} {self.server}"

    def get_off_days(self):
        """
        Convert the comma-separated string to a list of days that are off.
        """
        try:
            if self.off_days:
                # Try to split the string and convert to integers
                off_days = [int(day) for day in self.off_days.split(',')]

                # Validate that all days are between 1 and 7
                if not all(1 <= day <= 7 for day in off_days):
                    raise ValueError("Off days must be integers between 1 and 7.")
                return off_days
            return []
        except ValueError as e:
            error_message = f"Invalid off days format: {str(e)}"
            logger.error(error_message, exc_info=True)  # Log the error with traceback
            raise ValidationError(error_message)
        except Exception as e:
            error_message = f"Error while parsing off days: {str(e)}"
            logger.error(error_message, exc_info=True)  # Log the error with traceback
            raise ValidationError(error_message)

    def set_off_days(self, off_days_list):
        """
        Set the off days by converting the list of days into a comma-separated string.
        The list contains days as numbers (1 = Monday, 7 = Sunday).
        """
        try:
            if not all(isinstance(day, int) and 1 <= day <= 7 for day in off_days_list):
                raise ValueError("All off days must be integers between 1 and 7.")

            # Convert the list of off days into a comma-separated string
            self.off_days = ','.join(map(str, off_days_list))
        except ValueError as e:
            error_message = f"Invalid input for off days: {str(e)}"
            logger.error(error_message, exc_info=True)  # Log the error with traceback
            raise ValidationError(error_message)
        except Exception as e:
            error_message = f"Error while setting off days: {str(e)}"
            logger.error(error_message, exc_info=True)  # Log the error with traceback
            raise ValidationError(error_message)


class Service(models.Model):
    tip = models.ForeignKey(ServiceType, on_delete=models.CASCADE)
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
    service_private_price = models.IntegerField(null=True, blank=True)
    duration = models.IntegerField(default=60)  # Single service duration time default 30 minutes

    class Meta:
        unique_together = (('provider_server', 'service'),)


class Client(models.Model):
    full_name = models.CharField(max_length=255, null=True, blank=True)
    email = models.EmailField(null=True, blank=True)
    phone_number = models.CharField(max_length=13, null=True, blank=True)
    sex = models.CharField(max_length=10, null=True, blank=True)
    date_of_birth = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)
    is_active = models.BooleanField(default=True)
    comments = models.TextField(null=True, blank=True)
    language_code = models.CharField(max_length=3, null=True, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=['email']),
            models.Index(fields=['phone_number']),
        ]
        constraints = [
            # 1. Constraint to ensure at least one of email or phone_number is NOT NULL.
            CheckConstraint(
                check=Q(email__isnull=False) | Q(phone_number__isnull=False),
                name='at_least_one_contact_info_required'
            ),

            # 2. Constraint for when BOTH email and phone_number are provided.
            # The combination of non-null email and non-null phone_number must be unique.
            UniqueConstraint(
                fields=['email', 'phone_number'],
                condition=Q(email__isnull=False) & Q(phone_number__isnull=False),
                name='unique_email_and_phone_when_both_provided'
            ),

            # 3. Constraint for when phone_number IS NULL (only email is provided as contact).
            # Email must be unique among all records where phone_number is NULL.
            # This addresses the error you saw: two records with (some_email, NULL) would conflict.
            UniqueConstraint(
                fields=['email'],
                condition=Q(phone_number__isnull=True) & Q(email__isnull=False),
                name='unique_email_when_phone_is_null'
            ),

            # 4. Constraint for when email IS NULL (only phone_number is provided as contact).
            # Phone_number must be unique among all records where email is NULL.
            UniqueConstraint(
                fields=['phone_number'],
                condition=Q(email__isnull=True) & Q(phone_number__isnull=False),
                name='unique_phone_when_email_is_null'
            )
        ]


class ProviderClient(models.Model):
    provider = models.ForeignKey(Provider, on_delete=models.CASCADE)
    client = models.ForeignKey(Client, on_delete=models.CASCADE)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["provider", "client"], name="unique_provider_client")
        ]


STATUSES = [
    ("NEW", "NEW"),
    ("CONFIRMED", "CONFIRMED"),  # confirmed by OTP verification
    ("PENDING", "PENDING"),  # waiting for a provider to confirm
    ("ACCEPTED", "ACCEPTED"),  # accepted by the provider
    ("CANCELLED", "CANCELLED"),  # cancelled by the provider or client
    ("REJECTED", "REJECTED"),  # rejected by the provider
    ("NO_SHOW", "NO_SHOW"),  # client did not show up
    ("COMPLETED", "COMPLETED"),  # completed
]


class Appointment(models.Model):
    client = models.ForeignKey(Client, on_delete=models.CASCADE, null=True, blank=True)
    server = models.ForeignKey(Server, on_delete=models.CASCADE)
    start_datetime = models.DateTimeField(null=True, blank=True)
    end_datetime = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=12, choices=STATUSES, null=True, blank=True)
    comment = models.TextField(null=True, blank=True)
    comment_by_server = models.TextField(null=True, blank=True)
    total_amount = models.DecimalField(max_digits=12, decimal_places=0, default=0)
    paid_amount = models.DecimalField(max_digits=12, decimal_places=0, default=0)
    payment_note = models.CharField(max_length=255, null=True, blank=True)
    created_on = models.DateTimeField(auto_now_add=True, null=True, blank=True)

    def __str__(self):
        return f"{self.client} {self.server} {self.start_datetime} -- {self.end_datetime}"

    @property
    def debt_amount(self):
        return self.total_amount - self.paid_amount

    def compute_total(self):
        from decimal import Decimal
        total = Decimal(0)
        for appt_svc in self.appointmentservice_set.select_related('service').all():
            pss = appt_svc.service.providerserverservice_set.filter(
                provider_server__server=self.server
            ).first()
            if pss:
                price = pss.service_private_price if pss.service_private_price else pss.service.price
            else:
                price = appt_svc.service.price
            if price:
                total += Decimal(str(price))
        return total

    class Meta:
        indexes = [
            models.Index(fields=["status", "end_datetime", "created_on"]),
            models.Index(fields=["server", "start_datetime", "status"]),
        ]


class AppointmentFile(models.Model):
    appointment = models.ForeignKey(Appointment, on_delete=models.CASCADE, related_name='files')
    file = models.FileField(upload_to='appointment_files/')
    file_name = models.CharField(max_length=255, blank=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.appointment_id} — {self.file_name}"


class AppointmentService(models.Model):
    appointment = models.ForeignKey(Appointment, on_delete=models.CASCADE, null=True, blank=True)
    service = models.ForeignKey(Service, on_delete=models.CASCADE, null=True, blank=True)

    def __str__(self):
        return f"{self.appointment} {self.service}"


class OTPVerification(models.Model):
    appointment = models.ForeignKey(Appointment, on_delete=models.CASCADE, null=True, blank=True)
    phone_number = models.CharField(max_length=13, null=True, blank=True)
    email = models.EmailField(null=True, blank=True)
    verification_method = models.CharField(max_length=1, null=True, blank=True)
    otp_code = models.CharField(max_length=6)
    created_at = models.DateTimeField(auto_now_add=True)
    is_verified = models.BooleanField(default=False)
    attempts = models.PositiveSmallIntegerField(default=0)

    # Eskiz SMS metadata
    sms_request_id = models.CharField(max_length=64, null=True, blank=True)  # UUID from Eskiz response
    sms_message_id = models.CharField(max_length=64, null=True, blank=True)  # Numeric ID if available
    sms_status = models.CharField(max_length=20, null=True, blank=True)  # 'waiting', 'DELIVRD', etc.
    sms_status_date = models.DateTimeField(null=True, blank=True)  # Delivery time

    class Meta:
        indexes = [
            models.Index(fields=['is_verified', 'created_at']),
        ]

    def save(self, *args, **kwargs):
        if not self.otp_code:
            self.otp_code = str(random.randint(100000, 999999))  # Generate 6-digit OTP
        super().save(*args, **kwargs)

    def update_code(self):
        from django.utils import timezone as tz
        self.otp_code = str(random.randint(100000, 999999))
        self.attempts = 0
        self.created_at = tz.now()  # reset expiry window (auto_now_add only fires on INSERT)
        self.save()
