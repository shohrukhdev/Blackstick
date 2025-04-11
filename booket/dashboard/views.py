import json
import traceback
from collections import defaultdict
from datetime import timedelta, datetime
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.db.models import Prefetch, Count
from django.shortcuts import render, get_object_or_404, redirect
from django.urls import reverse
from django.utils import timezone
from booket.models import (
    ProviderServer, logger, ServiceType, Service, ProviderServerService, Appointment,
    AppointmentService, Provider
)


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
                    if private_price == 0 or private_price == "":
                        private_price = None
                    provider_server_service, is_created = ProviderServerService.objects.update_or_create(
                        provider_server=p_s_server,
                        service=service,
                        defaults={
                            "service_private_price": private_price,
                        }
                    )
                messages.success(request, "Service settings updated successfully.")
                return redirect(reverse("dashboard_config"))
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
                return redirect(reverse("dashboard_config"))  # Redirect to an appropriate page after saving
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


@login_required
def statistics(request):
    STATUSES = ["COMPLETED", "CANCELLED", "REJECTED", "NO_SHOW"]
    server = request.user.server_user
    if request.method == "GET":
        start_date_str = request.GET.get("start_date")
        end_date_str = request.GET.get("end_date")
        if start_date_str and end_date_str:
            start_date = datetime.strptime(start_date_str, "%Y-%m-%d").date()
            end_date = datetime.strptime(end_date_str, "%Y-%m-%d").date()
        else:
            today = timezone.now().date()
            first_day_of_month = today.replace(day=1)
            start_date = first_day_of_month
            end_date = today

            # Ensure start_date is not after end_date
        if start_date > end_date:
            start_date, end_date = end_date, start_date

        # Get appointments within the date range and filter by status
        appointments = Appointment.objects.filter(
            server=server,
            start_datetime__date__gte=start_date,
            start_datetime__date__lte=end_date,
            status__in=STATUSES
        )

        # Group appointments by date and status
        data = defaultdict(lambda: {status: 0 for status in STATUSES})

        for appointment in appointments:
            date = appointment.start_datetime.date()
            data[date][appointment.status] += 1

        # Format data for Chart.js
        labels = []
        completed_counts = []
        rejected_counts = []
        no_show_counts = []
        cancelled_counts = []

        current_date = start_date
        while current_date <= end_date:
            labels.append(current_date.strftime("%Y-%m-%d"))
            completed_counts.append(data[current_date]["COMPLETED"])
            rejected_counts.append(data[current_date]["REJECTED"])
            no_show_counts.append(data[current_date]["NO_SHOW"])
            cancelled_counts.append(data[current_date]["CANCELLED"])
            current_date += timedelta(days=1)

        # =================== Service Count for Pie Chart =================== #
        service_counts = (
            AppointmentService.objects
            .filter(appointment__start_datetime__date__range=[start_date, end_date],
                    appointment__server=server,
                    appointment__status="COMPLETED")
            .values('service__name')
            .annotate(count=Count('id'))
            .order_by('-count')  # Order by highest count
        )

        # =================== Top 5 Clients by Completed Appointments =================== #
        top_completed_clients = (
            Appointment.objects
            .filter(start_datetime__date__range=[start_date, end_date],
                    status="COMPLETED",
                    server=server)
            .values("client__full_name")
            .annotate(count=Count("id"))
            .order_by("-count")[:5]  # Top 5
        )

        # =================== Top 5 Clients by No-Show Appointments =================== #
        top_no_show_clients = (
            Appointment.objects
            .filter(start_datetime__date__range=[start_date, end_date],
                    status="NO_SHOW",
                    server=server)
            .values("client__full_name")
            .annotate(count=Count("id"))
            .order_by("-count")[:5]  # Top 5
        )

        # Prepare pie chart data
        service_labels = [entry["service__name"] for entry in service_counts]
        service_data = [entry["count"] for entry in service_counts]

        context_data = {
            "start_date": start_date,
            "end_date": end_date,
            "labels": json.dumps(labels),
            "completed_counts": json.dumps(completed_counts),
            "rejected_counts": json.dumps(rejected_counts),
            "no_show_counts": json.dumps(no_show_counts),
            "cancelled_counts": json.dumps(cancelled_counts),
            "service_labels": json.dumps(service_labels),
            "service_data": json.dumps(service_data),
            "top_completed_clients": top_completed_clients,
            "top_no_show_clients": top_no_show_clients,
        }

        return render(request, "booket/dashboard/statistics.html", context=context_data)


@login_required
def provider_dashboard(request):
    provider_servers = ProviderServer.objects.filter(
        provider__owner=request.user,
        server__is_active=True
    )
    context_data = {
        "provider_servers": provider_servers
    }
    return render(request, "booket/dashboard/provider_dashboard.html", context=context_data)


@login_required
def provider_history(request):
    return render(request, "booket/dashboard/provider_history.html")


@login_required
def provider_statistics(request):
    provider = Provider.objects.get(owner=request.user)
    if request.method == "GET":
        start_date_str = request.GET.get("start_date")
        end_date_str = request.GET.get("end_date")
        if start_date_str and end_date_str:
            start_date = datetime.strptime(start_date_str, "%Y-%m-%d").date()
            end_date = datetime.strptime(end_date_str, "%Y-%m-%d").date()
        else:
            today = timezone.now().date()
            first_day_of_month = today.replace(day=1)
            start_date = first_day_of_month
            end_date = today

            # Ensure start_date is not after end_date
        if start_date > end_date:
            start_date, end_date = end_date, start_date
        provider_server_ids = ProviderServer.objects.filter(provider=provider).values("server_id")

        completed_appointments = (
            Appointment.objects
            .filter(start_datetime__date__range=[start_date, end_date],
                    status="COMPLETED",
                    server_id__in=provider_server_ids)
            .values("start_datetime__date")
            .annotate(count=Count("id"))
            .order_by("start_datetime__date")
        )

        completed_counts = {entry["start_datetime__date"].strftime("%Y-%m-%d"): entry["count"] for entry in completed_appointments}

        # Generate labels for the date range
        labels = []
        current_date = start_date
        while current_date <= end_date:
            labels.append(current_date.strftime("%Y-%m-%d"))
            current_date += timedelta(days=1)

        # =================== Top 5 Clients by Completed Appointments =================== #
        top_completed_clients = (
            Appointment.objects
            .filter(start_datetime__date__range=[start_date, end_date],
                    status="COMPLETED",
                    server_id__in=provider_server_ids)
            .values("client__full_name")
            .annotate(count=Count("id"))
            .order_by("-count")[:5]  # Top 5
        )

        # =================== Top 5 Clients by No-Show Appointments =================== #
        top_no_show_clients = (
            Appointment.objects
            .filter(start_datetime__date__range=[start_date, end_date],
                    status="NO_SHOW",
                    server_id__in=provider_server_ids)
            .values("client__full_name")
            .annotate(count=Count("id"))
            .order_by("-count")[:5]  # Top 5
        )

        # =================== Service Count for Pie Chart =================== #
        service_counts = (
            AppointmentService.objects
            .filter(appointment__start_datetime__date__range=[start_date, end_date],
                    appointment__server_id__in=provider_server_ids,
                    appointment__status="COMPLETED")
            .values('service__name')
            .annotate(count=Count('id'))
            .order_by('-count')  # Order by highest count
        )
        # Prepare pie chart data
        service_labels = [entry["service__name"] for entry in service_counts]
        service_data = [entry["count"] for entry in service_counts]

        # =================== Server Count for Bar Chart =================== #
        server_counts = (
            Appointment.objects
            .filter(start_datetime__date__range=[start_date, end_date],
                    status="COMPLETED",
                    server_id__in=provider_server_ids)
            .values("server__user__first_name", "server__user__last_name", "server")
            .annotate(count=Count("id"))
            .order_by("server")
        )

        server_labels = [f'{entry["server__user__first_name"]} {entry["server__user__last_name"]}' for entry in server_counts]
        server_data = [entry["count"] for entry in server_counts]

        context_data = {
            "start_date": start_date,
            "end_date": end_date,
            "labels": json.dumps(labels),
            "service_labels": json.dumps(service_labels),
            "service_data": json.dumps(service_data),
            "total_completed": len(completed_counts),
            "completed_counts": json.dumps(completed_counts),
            "top_completed_clients": top_completed_clients,
            "top_no_show_clients": top_no_show_clients,
            "server_labels": json.dumps(server_labels),
            "server_data": json.dumps(server_data),
        }
        return render(request, "booket/dashboard/provider_statistics.html", context=context_data)
