import traceback
from datetime import timedelta
from turtledemo.penrose import start

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.db.models import Prefetch
from django.shortcuts import render, get_object_or_404, redirect
from django.urls import reverse
from django.utils import timezone

from booket.models import ProviderServer, logger, ServiceType, Service, ProviderServerService, Appointment


@login_required
def dashboard(request):
    if request.method == "POST":
        try:
            server = request.user.server_user
            memo = request.POST.get("memo")
            server.memo = memo
            server.save()
            messages.success(request, "Memo updated successfully.")
        except Exception as e:
            logger.error(traceback.format_exc())
            messages.error(request, f"Error updating memo: {str(e)}")

            # Redirect to the same page to prevent form resubmission
        return redirect(reverse("dashboard_main"))

    if request.method == "GET":
        try:
            # Get the current user's server
            server = request.user.server_user

            # Get the next upcoming appointment
            next_appointment = Appointment.objects.filter(
                server=server,
                status__in=["CONFIRMED", "ACCEPTED"],
                start_datetime__gte=timezone.now()
            ).order_by('start_datetime').first()

            # Get the number of appointments for today
            today_start = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
            today_end = today_start + timedelta(days=1)

            today_appointments_count = Appointment.objects.filter(
                server=server,
                status__in=["CONFIRMED", "ACCEPTED", "COMPLETED", "NO-SHOW"],
                start_datetime__gte=today_start,
                start_datetime__lt=today_end
            ).count()

            # Get the number of completed appointments for today
            today_completed_appointments_count = Appointment.objects.filter(
                server=server,
                start_datetime__gte=today_start,
                start_datetime__lt=today_end,
                status="COMPLETED"
            ).count()

            # no-show appointments
            no_show_appointments_count = Appointment.objects.filter(
                server=server,
                status="NO_SHOW",
                start_datetime__gte=today_start,
                start_datetime__lt=today_end
            ).count()

            context_data = {
                "appointment": next_appointment,
                "today_no_show_appointments_count": no_show_appointments_count,
                "today_appointments_count": today_appointments_count,
                "today_completed_appointments_count": today_completed_appointments_count,
                "memo": server.memo
            }
        except Exception as e:
            logger.error(traceback.format_exc())
            context_data = {
                "error": str(e)
            }
        return render(request, "booket/dashboard/dashboard.html", context=context_data)


@login_required
def configs(request):
    if request.method == "GET":
        try:
            p_server = get_object_or_404(ProviderServer, server__user=request.user)
            p_service_types = ServiceType.objects.filter(provider=p_server.provider).prefetch_related(
                Prefetch(
                    'service_set',
                    queryset=Service.objects.filter(tip__provider=p_server.provider).prefetch_related(
                        Prefetch(
                            'providerserverservice_set',
                            queryset=ProviderServerService.objects.filter(provider_server__server_id=p_server.id),
                            to_attr='assigned_service',
                        )
                    )
                )
            )
            p_s_services = ProviderServerService.objects.filter(
                provider_server_id=p_server.id
            )
            context_data = {
                "p_server": p_server,
                "service_types": p_service_types,
                "assigned_services": p_s_services
            }
        except Exception as e:
            context_data = {
                "success": False,
                "error": str(e)
            }
        return render(
            request,
            template_name="booket/dashboard/my_config.html",
            context=context_data
        )
    elif request.method == "POST":
        if "service_id" in request.POST:
            p_s_server = ProviderServer.objects.get(
                id=request.POST.get("provider_server_id"),
            )
            try:
                sr_type = ServiceType.objects.get(
                    id=request.POST.get("service_type_id"),
                    provider__owner=request.user
                )
                if request.POST.get("is_active") is None:
                    ProviderServerService.objects.filter(
                        id=request.POST.get("p_s_service_id"),
                    ).delete()
                else:
                    service = get_object_or_404(
                        Service,
                        id=request.POST.get("service_id"),
                        tip=sr_type,
                    )
                    private_price = request.POST.get("private_price")
                    if private_price == 0 or private_price is "":
                        private_price = None
                    provider_server_service, is_created = ProviderServerService.objects.update_or_create(
                        provider_server=p_s_server,
                        service=service,
                        defaults={
                            "service_private_price": private_price,
                        }
                    )
                messages.success(request, "Service settings updated successfully.")
                return redirect(reverse(f"dashboard_config"))
            except Exception as e:
                logger.error(traceback.format_exc())
                messages.error(request, f"Error updating service settings: {str(e)}")
                context_data = {
                    "p_server": p_s_server,
                }
                return render(request, "booket/dashboard/my_config.html", context=context_data)

        else:
            p_server = get_object_or_404(ProviderServer, id=request.POST["p_server_id"])
            # Handling time fields
            day_starts_on = request.POST.get("day_starts_on")
            day_ends_on = request.POST.get("day_ends_on")

            # Handling off days checkboxes
            off_days_mapping = {
                "mon": 1, "tue": 2, "wed": 3, "thu": 4, "fri": 5, "sat": 6, "sun": 7
            }
            selected_off_days = [str(value) for key, value in off_days_mapping.items() if
                                 request.POST.get(key) == "yes"]
            off_days_str = ",".join(selected_off_days)

            # Update the model instance
            p_server.day_starts_on = day_starts_on if day_starts_on else None
            p_server.day_ends_on = day_ends_on if day_ends_on else None
            p_server.off_days = off_days_str
            user = User.objects.get(
                id=p_server.server.user.id
            )
            user.first_name = request.POST.get("first_name")
            user.last_name = request.POST.get("last_name")
            user.email = request.POST.get("email")

            try:
                p_server.save()
                user.save()
                messages.success(request, "Settings updated successfully.")
                return redirect(reverse(f"dashboard_config"))  # Redirect to an appropriate page after saving
            except Exception as e:
                logger.error(traceback.format_exc())
                messages.error(request, f"Error updating settings: {str(e)}")
                context_data = {
                    "p_server": p_server,
                }
            return render(request, "booket/dashboard/my_config.html", context=context_data)


@login_required
def history(request):
    return render(request, "booket/dashboard/history.html")
