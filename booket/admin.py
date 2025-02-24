from django.contrib import admin
from booket.models import (
    Provider,
    Service, Server,
    Client,
    Appointment,
    AppointmentService,
    ProviderServer, ProviderServerService, ServiceType
)


# Inline for ProviderServer (Servers for a specific Provider)
class ProviderServerInline(admin.TabularInline):
    model = ProviderServer
    extra = 0  # Number of empty forms to display
    fields = ('server', 'day_starts_on', 'day_ends_on')  # Fields for each server related to the provider


# Admin for Provider
class ProviderServerAdmin(admin.ModelAdmin):
    # list_display = ('name', 'logo', 'is_active', 'created_at')
    inlines = [ProviderServerInline]  # Show related servers for each provider


@admin.register(Client)
class ClientAdmin(admin.ModelAdmin):
    pass


@admin.register(Appointment)
class AppointmentAdmin(admin.ModelAdmin):
    pass


@admin.register(AppointmentService)
class AppointmentServiceAdmin(admin.ModelAdmin):
    pass


@admin.register(ProviderServerService)
class ProviderServerServiceAdmin(admin.ModelAdmin):
    pass


@admin.register(Service)
class ServiceAdmin(admin.ModelAdmin):
    pass


@admin.register(ServiceType)
class ServiceTypeAdmin(admin.ModelAdmin):
    pass


@admin.register(Server)
class ServerAdmin(admin.ModelAdmin):
    pass


# @admin.register(Provider)
# class ProviderAdmin(admin.ModelAdmin):
#     pass






# Register models
admin.site.register(Provider, ProviderServerAdmin)
# admin.site.register(ProviderServer, ProviderServerServiceAdmin)
# admin.site.register(Service, ServiceAdmin)
# admin.site.register(Server, ServerAdmin)
