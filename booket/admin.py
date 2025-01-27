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


# Inline for ProviderServerService (Services that the Server of a Provider performs)
class ProviderServiceTypeInline(admin.TabularInline):
    model = ServiceType
    extra = 0  # Number of empty forms to display
    fields = ('name', 'name_uz', 'name_ru', 'description', 'initial_price', 'is_active')  # ServiceType related to the server


# Admin for Provider
class ProviderServerAdmin(admin.ModelAdmin):
    list_display = ('name', 'logo', 'is_active', 'created_at')
    inlines = [ProviderServerInline, ProviderServiceTypeInline]  # Show related servers for each provider

    def get_inline_instances(self, request, obj=None):
        inlines = super().get_inline_instances(request, obj)
        if obj:
            # When a Provider instance is selected, also show the services for each server
            for inline in inlines:
                if isinstance(inline, ProviderServerInline):
                    inline.inlines = [ProviderServiceTypeInline]  # Attach ProviderServerServiceInline to each server
        return inlines


# class ProviderServerServiceAdmin(admin.ModelAdmin):
#     list_display = ('server', 'provider')
#     inlines = [ProviderServiceInline]


# Admin for Server
class ServerAdmin(admin.ModelAdmin):
    list_display = ('user', 'phone_number', 'is_active', 'created')
    inlines = []  # Show services associated with each server


# Admin for Service
class ServiceAdmin(admin.ModelAdmin):
    list_display = ('name_uz', 'name_ru', 'price', 'is_active')


@admin.register(Client)
class ClientAdmin(admin.ModelAdmin):
    pass


@admin.register(Appointment)
class AppointmentAdmin(admin.ModelAdmin):
    pass


@admin.register(AppointmentService)
class AppointmentServiceAdmin(admin.ModelAdmin):
    pass


# Register models
admin.site.register(Provider, ProviderServerAdmin)
# admin.site.register(ProviderServer, ProviderServerServiceAdmin)
admin.site.register(Service, ServiceAdmin)
admin.site.register(Server, ServerAdmin)
