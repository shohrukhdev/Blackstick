from django.db import models
from django.contrib.auth.models import User
from hashid_field import HashidField, HashidAutoField



class Clinic(models.Model):
    name = models.CharField(max_length=200, null=True, blank=True)
    address = models.CharField(max_length=2000, null=True, blank=True)
    info = models.TextField()
    status = models.CharField(max_length=2, default='A')
    balance = models.IntegerField(default=1000)
    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name='clinic_owner')

    class Meta:
        verbose_name = 'Clinic'
        verbose_name_plural = 'Clinics'

    def __str__(self):
        return self.name


class Role(models.Model):
    name = models.CharField(max_length=200)
    code = models.CharField(max_length=10)

    class Meta:
        verbose_name = 'Role'
        verbose_name_plural = 'Roles'

    def __str__(self):
        return self.name


class Stuff(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='stuff_user')
    clinic = models.ForeignKey(Clinic, on_delete=models.CASCADE, related_name='stuff_clinic')
    role = models.ForeignKey(Role, on_delete=models.CASCADE, related_name='stuff_role')
    status = models.IntegerField(default=1)
    hire_date = models.DateField()
    cr_on = models.DateTimeField(auto_now_add=True)
    up_on = models.DateTimeField(auto_now=True)
    cr_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='stuff_crby', null=True)
    up_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='stuff_upby', null=True)

    class Meta:
        verbose_name = 'Stuff'
        verbose_name_plural = 'Stuff'

    def __str__(self):
        return self.user.username


class Patient(models.Model):
    reference_id = models.CharField(max_length=128, unique=True, null=True)
    clinic = models.ForeignKey(Clinic, on_delete=models.CASCADE, related_name='patient_clinic')
    photo = models.ImageField(null=True, blank=True)
    full_name = models.CharField(max_length=512)
    mobile_phone = models.CharField(max_length=512)
    sex = models.CharField(max_length=1)
    date_birth = models.DateField()
    comments = models.TextField(null=True, blank=True)
    state = models.CharField(max_length=1)
    cr_on = models.DateTimeField(auto_now_add=True)
    cr_by = models.ForeignKey(Stuff, on_delete=models.CASCADE, related_name='patient_crby')
    up_on = models.DateTimeField(auto_now=True)
    up_by = models.ForeignKey(Stuff, on_delete=models.CASCADE, related_name='patient_upby')

    class Meta:
        verbose_name = 'Patient'
        verbose_name_plural = 'Patients'
        unique_together = ('full_name', 'mobile_phone',)

    def __str__(self):
        return self.full_name


class ServiceCategory(models.Model):
    stuff = models.ForeignKey(Stuff, on_delete=models.CASCADE, related_name='category_stuff', null=True, blank=True)
    name = models.CharField(max_length=400, null=True, blank=True)
    name_uz = models.CharField(max_length=400, null=True, blank=True)
    name_ru = models.CharField(max_length=400, null=True, blank=True)

    class Meta:
        verbose_name = 'Service Category'
        verbose_name_plural = 'Service Categories'

    def __str__(self):
        return self.name


class Event(models.Model):
    stuff = models.ForeignKey(Stuff, on_delete=models.CASCADE, related_name='event_stuff')
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name='event_patient')
    service_category = models.ForeignKey(ServiceCategory, on_delete=models.CASCADE, null=True, blank=True)
    title = models.CharField(max_length=500, null=True, blank=True)
    description = models.CharField(max_length=4000, blank=True, null=True)
    start_time = models.DateTimeField()
    end_time = models.DateTimeField(null=True, blank=True)
    all_day = models.BooleanField(default=False)
    background_color = models.CharField(max_length=128, null=True, blank=True)
    border_color = models.CharField(max_length=128, null=True, blank=True)
    text_color = models.CharField(max_length=128, default='#000000')
    status = models.IntegerField(default=1)
    display = models.CharField(max_length=200, null=True, blank=True, default='auto')

    class Meta:
        verbose_name = 'Event'
        verbose_name_plural = 'Events'

    def __str__(self):
        return self.title


class Service(models.Model):
    category = models.ForeignKey(ServiceCategory, on_delete=models.CASCADE, related_name='service_category')
    doctor = models.ForeignKey(Stuff, on_delete=models.CASCADE, related_name='service_doctor')
    name = models.CharField(max_length=500, null=True, blank=True)
    name_uz = models.CharField(max_length=500, null=True, blank=True)
    name_ru = models.CharField(max_length=500, null=True, blank=True)
    description = models.TextField()
    status = models.IntegerField(default=1)
    price = models.IntegerField(default=0)

    class Meta:
        verbose_name = 'Service'
        verbose_name_plural = 'Services'

    def __str__(self):
        return self.name


class Teeth(models.Model):
    name = models.CharField(max_length=128)
    code = models.CharField(max_length=50, null=True, blank=True)

    class Meta:
        verbose_name = 'Tooth'
        verbose_name_plural = 'Teeth'

    def __str__(self):
        return "{} - {}".format(self.code, self.name)


class Treatment(models.Model):
    reference_id = models.CharField(max_length=128, null=True, blank=True, unique=True)
    doctor = models.ForeignKey(Stuff, on_delete=models.CASCADE, related_name='procedure_doctor')
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name='procedure_patient')
    complaint = models.CharField(max_length=4000, null=True, blank=True)
    diagnosis = models.TextField(null=True, blank=True)
    cr_on = models.DateTimeField(auto_created=True, null=True, blank=True)
    description = models.TextField()
    total_amount = models.IntegerField(default=0)
    discount = models.IntegerField(default=0)
    paid_amount = models.IntegerField(default=0)
    cr_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='treatment_cr_by', null=True, blank=True)

    @property
    def get_actual_amount(self):
        return int(self.total_amount * (100 - self.discount)/100)

    def __str__(self):
        return "{} - {}".format(self.patient, self.cr_on)

    class Meta:
        verbose_name = 'Treatment'
        verbose_name_plural = 'Treatments'


class TreatmentFile(models.Model):
    """Treatment files."""
    treatment = models.ForeignKey(
        Treatment,
        on_delete=models.CASCADE,
        related_name='file_treatment'
    )
    file_name = models.CharField(max_length=128, null=True)
    file = models.FileField(upload_to='stom_files/%Y/%m/%d')
    cr_on = models.DateTimeField(auto_now_add=True, null=True)
    cr_by = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        null=True
    )

    class Meta:
        verbose_name = 'File'
        verbose_name_plural = 'Files'


class Procedure(models.Model):
    treatment = models.ForeignKey(Treatment, on_delete=models.CASCADE)
    teeth = models.ForeignKey(Teeth, on_delete=models.CASCADE, related_name='procedure_teeth')
    service = models.ForeignKey(Service, on_delete=models.CASCADE, related_name='procedure_service')
    quantity = models.IntegerField(default=0)
    price = models.IntegerField(default=0)


class ToothState(models.Model):
    name = models.CharField(max_length=500, null=True, blank=True)
    name_uz = models.CharField(max_length=500, null=True, blank=True)
    name_ru = models.CharField(max_length=500, null=True, blank=True)


class ProcedureToothState(models.Model):
    treatment = models.ForeignKey(Treatment, on_delete=models.CASCADE, null=True, blank=True)
    teeth = models.ForeignKey(Teeth, on_delete=models.CASCADE, null=True, blank=True)
    tooth_state = models.ForeignKey(ToothState, on_delete=models.CASCADE, null=True, blank=True)




