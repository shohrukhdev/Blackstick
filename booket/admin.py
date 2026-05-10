from django.contrib import admin
from django.db.models import Count
from django.utils.html import format_html

from booket.models import (
    Provider, ProviderPhotos, ProviderClient,
    Server, ProviderServer, ProviderServerService,
    ServiceType, Service,
    Client,
    Appointment, AppointmentService, AppointmentFile,
    OTPVerification,
)

admin.site.site_header = "Booket Admin"
admin.site.site_title = "Booket"
admin.site.index_title = "Dashboard"


# ── Inlines ────────────────────────────────────────────────────────────────────

class ProviderServerInline(admin.TabularInline):
    model = ProviderServer
    extra = 0
    fields = ("server", "day_starts_on", "day_ends_on", "off_days")
    autocomplete_fields = ("server",)
    show_change_link = True
    verbose_name = "Specialist"
    verbose_name_plural = "Specialists"


class ProviderServerServiceInline(admin.TabularInline):
    model = ProviderServerService
    extra = 0
    fields = ("service", "duration", "service_private_price")
    autocomplete_fields = ("service",)
    verbose_name = "Service"
    verbose_name_plural = "Services offered"


class ServiceInline(admin.TabularInline):
    model = Service
    extra = 0
    fields = ("name", "name_uz", "name_ru", "price", "is_active")
    show_change_link = True


class ProviderPhotosInline(admin.TabularInline):
    model = ProviderPhotos
    extra = 0
    fields = ("photo",)


class ProviderClientInline(admin.TabularInline):
    model = ProviderClient
    extra = 0
    fields = ("provider",)
    autocomplete_fields = ("provider",)
    verbose_name = "Provider"
    verbose_name_plural = "Linked providers"


class AppointmentServiceInline(admin.TabularInline):
    model = AppointmentService
    extra = 0
    fields = ("service",)
    autocomplete_fields = ("service",)
    verbose_name = "Service"
    verbose_name_plural = "Services"


class AppointmentFileInline(admin.TabularInline):
    model = AppointmentFile
    extra = 0
    fields = ("file_name", "file", "uploaded_at")
    readonly_fields = ("uploaded_at",)
    verbose_name = "File"
    verbose_name_plural = "Files"


# ── Provider ───────────────────────────────────────────────────────────────────

@admin.register(Provider)
class ProviderAdmin(admin.ModelAdmin):
    list_display = ("name", "identifier", "is_active", "has_many_servers", "auto_accept", "server_count", "created_at")
    list_filter = ("is_active", "has_many_servers", "auto_accept")
    search_fields = ("name", "identifier")
    readonly_fields = ("created_at",)
    inlines = [ProviderServerInline, ProviderPhotosInline]
    fieldsets = (
        (None, {
            "fields": ("name", "identifier", "owner", "logo", "is_active", "has_many_servers", "auto_accept")
        }),
        ("Content", {
            "fields": ("description", "address", "latitude", "longitude",
                       "specialists_section_text", "specialists_section_text_2",
                       "footer_text", "phone_numbers", "social_media"),
            "classes": ("collapse",),
        }),
        ("Metadata", {
            "fields": ("created_at",),
            "classes": ("collapse",),
        }),
    )

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(_server_count=Count("providerserver", distinct=True))

    @admin.display(description="Specialists", ordering="_server_count")
    def server_count(self, obj):
        return obj._server_count


# ── ProviderServer ─────────────────────────────────────────────────────────────

@admin.register(ProviderServer)
class ProviderServerAdmin(admin.ModelAdmin):
    list_display = ("provider", "server_full_name", "day_starts_on", "day_ends_on", "off_days", "service_count")
    list_filter = ("provider",)
    search_fields = ("provider__name", "server__user__first_name", "server__user__last_name")
    autocomplete_fields = ("provider", "server")
    inlines = [ProviderServerServiceInline]

    def get_queryset(self, request):
        return (
            super().get_queryset(request)
            .select_related("provider", "server__user")
            .annotate(_service_count=Count("providerserverservice", distinct=True))
        )

    @admin.display(description="Specialist", ordering="server__user__last_name")
    def server_full_name(self, obj):
        return obj.server.user.get_full_name() or obj.server.user.username

    @admin.display(description="Services", ordering="_service_count")
    def service_count(self, obj):
        return obj._service_count


# ── Server ─────────────────────────────────────────────────────────────────────

@admin.register(Server)
class ServerAdmin(admin.ModelAdmin):
    list_display = ("full_name", "title", "phone_number", "is_active", "created")
    list_filter = ("is_active",)
    search_fields = ("user__first_name", "user__last_name", "user__username", "phone_number")
    readonly_fields = ("created",)
    fieldsets = (
        (None, {
            "fields": ("user", "image", "phone_number", "is_active")
        }),
        ("Titles", {
            "fields": ("title", "title_uz", "title_ru"),
        }),
        ("Profile", {
            "fields": ("info", "memo"),
            "classes": ("collapse",),
        }),
        ("Metadata", {
            "fields": ("created",),
            "classes": ("collapse",),
        }),
    )

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("user")

    @admin.display(description="Full Name", ordering="user__last_name")
    def full_name(self, obj):
        return obj.user.get_full_name() or obj.user.username


# ── ServiceType ────────────────────────────────────────────────────────────────

@admin.register(ServiceType)
class ServiceTypeAdmin(admin.ModelAdmin):
    list_display = ("name", "name_uz", "name_ru", "provider", "is_active")
    list_filter = ("provider", "is_active")
    search_fields = ("name", "name_uz", "name_ru", "provider__name")
    autocomplete_fields = ("provider",)
    inlines = [ServiceInline]

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("provider")


# ── Service ────────────────────────────────────────────────────────────────────

@admin.register(Service)
class ServiceAdmin(admin.ModelAdmin):
    list_display = ("name", "name_uz", "name_ru", "service_type", "provider_name", "price", "is_active")
    list_filter = ("tip__provider", "is_active")
    search_fields = ("name", "name_uz", "name_ru")
    autocomplete_fields = ("tip",)

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("tip__provider")

    @admin.display(description="Type", ordering="tip__name")
    def service_type(self, obj):
        return obj.tip.name if obj.tip else "—"

    @admin.display(description="Provider", ordering="tip__provider__name")
    def provider_name(self, obj):
        return obj.tip.provider.name if obj.tip and obj.tip.provider else "—"


# ── Client ─────────────────────────────────────────────────────────────────────

@admin.register(Client)
class ClientAdmin(admin.ModelAdmin):
    list_display = ("full_name", "phone_number", "email", "sex", "language_code", "is_active", "created_at")
    list_filter = ("is_active", "sex", "language_code")
    search_fields = ("full_name", "phone_number", "email")
    readonly_fields = ("created_at", "updated_at")
    inlines = [ProviderClientInline]


# ── Appointment ────────────────────────────────────────────────────────────────

@admin.register(Appointment)
class AppointmentAdmin(admin.ModelAdmin):
    list_display = ("id", "client_name", "server_name", "colored_status", "start_datetime", "end_datetime", "created_on")
    list_filter = ("status",)
    search_fields = (
        "client__full_name", "client__phone_number",
        "server__user__first_name", "server__user__last_name",
    )
    readonly_fields = ("created_on",)
    date_hierarchy = "start_datetime"
    inlines = [AppointmentServiceInline, AppointmentFileInline]

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("client", "server__user")

    @admin.display(description="Client", ordering="client__full_name")
    def client_name(self, obj):
        return obj.client.full_name if obj.client else "Guest"

    @admin.display(description="Specialist", ordering="server__user__last_name")
    def server_name(self, obj):
        return obj.server.user.get_full_name() if obj.server else "—"

    _STATUS_COLORS = {
        "NEW": "#6c757d",
        "CONFIRMED": "#0d6efd",
        "PENDING": "#ffc107",
        "ACCEPTED": "#198754",
        "CANCELLED": "#dc3545",
        "REJECTED": "#dc3545",
        "NO_SHOW": "#fd7e14",
        "COMPLETED": "#20c997",
    }

    @admin.display(description="Status", ordering="status")
    def colored_status(self, obj):
        color = self._STATUS_COLORS.get(obj.status, "#6c757d")
        return format_html(
            '<span style="color:{};font-weight:600">{}</span>',
            color,
            obj.status or "—",
        )


# ── OTPVerification ────────────────────────────────────────────────────────────

@admin.register(OTPVerification)
class OTPVerificationAdmin(admin.ModelAdmin):
    list_display = (
        "appointment_id", "phone_number", "email",
        "verification_method", "is_verified", "attempts", "created_at",
    )
    list_filter = ("is_verified", "verification_method")
    search_fields = ("phone_number", "email")
    readonly_fields = ("otp_code", "created_at", "sms_request_id", "sms_message_id", "sms_status", "sms_status_date")

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("appointment")
