from django.contrib import admin
from .models import *


@admin.register(Clinic)
class ClinicAdmin(admin.ModelAdmin):
    pass


@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):
    pass


@admin.register(Stuff)
class StuffAdmin(admin.ModelAdmin):
    pass


@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    pass


@admin.register(Patient)
class PatientAdmin(admin.ModelAdmin):
    pass


@admin.register(Teeth)
class TeethAdmin(admin.ModelAdmin):
    pass


@admin.register(Service)
class ServiceAdmin(admin.ModelAdmin):
    pass


@admin.register(Treatment)
class TreatmentAdmin(admin.ModelAdmin):
    pass


@admin.register(Procedure)
class ProcedureAdmin(admin.ModelAdmin):
    pass


class ServiceInline(admin.TabularInline):
    model = Service
    extra = 0


@admin.register(ServiceCategory)
class ServiceCategoryAdmin(admin.ModelAdmin):
    inlines = [ServiceInline]


@admin.register(ToothState)
class ToothStateAdmin(admin.ModelAdmin):
    pass


@admin.register(ProcedureToothState)
class ProvedureToothStateAdmin(admin.ModelAdmin):
    pass


@admin.register(TreatmentFile)
class TreatmentFileAdmin(admin.ModelAdmin):
    pass
