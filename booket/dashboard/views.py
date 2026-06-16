import json
import logging
from collections import defaultdict
from datetime import timedelta, datetime
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.db.models import Prefetch, Count, Sum, Q, Min
from django.db.models.functions import TruncDate, ExtractIsoWeekDay
from django.shortcuts import render, get_object_or_404, redirect
from django.urls import reverse
from django.utils import timezone
from booket.models import (
    ProviderServer, ServiceType, Service, ProviderServerService, Appointment,
    AppointmentService, Provider,
)

logger = logging.getLogger(__name__)


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
            logger.exception("View error")
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

            server_services = list(
                ProviderServerService.objects.filter(
                    provider_server__server=server
                ).select_related('service').values(
                    'id', 'service__id', 'service__name', 'service__name_uz', 'service__name_ru', 'duration'
                )
            )

            context_data = {
                "appointment": next_appointment,
                "today_no_show_appointments_count": no_show_appointments_count,
                "today_appointments_count": today_appointments_count,
                "today_completed_appointments_count": today_completed_appointments_count,
                "memo": server.memo,
                "server_services_json": json.dumps(server_services),
            }
        except Exception as e:
            logger.exception("View error")
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
                    provider=p_s_server.provider
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
                    service_duration = int(request.POST.get("service_duration", 60))
                    if service_duration < 30:
                        service_duration = 30

                    provider_server_service, is_created = ProviderServerService.objects.update_or_create(
                        provider_server=p_s_server,
                        service=service,
                        defaults={
                            "service_private_price": private_price,
                            "duration": service_duration
                        }
                    )
                messages.success(request, "Service settings updated successfully.")
                return redirect(reverse("dashboard_config"))
            except Exception as e:
                logger.exception("View error")
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

            provider = p_server.provider
            provider.auto_accept = request.POST.get("auto_accept") == "yes"

            try:
                p_server.save()
                user.save()
                provider.save(update_fields=["auto_accept"])
                messages.success(request, "Settings updated successfully.")
                return redirect(reverse("dashboard_config"))
            except Exception as e:
                logger.exception("View error")
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
    TERMINAL_STATUSES = ["COMPLETED", "NO_SHOW", "CANCELLED", "REJECTED"]
    server = request.user.server_user
    lang = getattr(request, 'LANGUAGE_CODE', 'en')

    start_date_str = request.GET.get("start_date")
    end_date_str = request.GET.get("end_date")
    try:
        if start_date_str and end_date_str:
            start_date = datetime.strptime(start_date_str, "%Y-%m-%d").date()
            end_date = datetime.strptime(end_date_str, "%Y-%m-%d").date()
        else:
            raise ValueError
    except ValueError:
        today = timezone.now().date()
        start_date = today.replace(day=1)
        end_date = today

    if start_date > end_date:
        start_date, end_date = end_date, start_date

    base_qs = Appointment.objects.filter(
        server=server,
        start_datetime__date__range=[start_date, end_date],
        status__in=TERMINAL_STATUSES,
    )

    # ── KPI aggregates — single DB query ───────────────────────────────
    kpi = base_qs.aggregate(
        total=Count('id'),
        completed=Count('id', filter=Q(status='COMPLETED')),
        no_show=Count('id', filter=Q(status='NO_SHOW')),
        cancelled=Count('id', filter=Q(status='CANCELLED')),
        rejected=Count('id', filter=Q(status='REJECTED')),
        total_paid=Sum('paid_amount', filter=Q(status='COMPLETED')),
    )
    total = kpi['total'] or 0
    completed = kpi['completed'] or 0
    no_show = kpi['no_show'] or 0
    cancelled = kpi['cancelled'] or 0
    rejected = kpi['rejected'] or 0
    total_paid = int(kpi['total_paid'] or 0)

    def pct(part, whole):
        return f"{round(part / whole * 100, 1):.1f}" if whole else "0.0"

    # ── Trend time-series — single aggregated DB query ─────────────────
    trend_qs = (
        base_qs
        .annotate(appt_date=TruncDate('start_datetime'))
        .values('appt_date', 'status')
        .annotate(count=Count('id'))
        .order_by('appt_date', 'status')
    )
    trend = defaultdict(lambda: dict.fromkeys(TERMINAL_STATUSES, 0))
    for row in trend_qs:
        trend[row['appt_date'].strftime("%Y-%m-%d")][row['status']] = row['count']

    labels, completed_counts, no_show_counts, cancelled_counts, rejected_counts = [], [], [], [], []
    cur = start_date
    while cur <= end_date:
        d = cur.strftime("%Y-%m-%d")
        labels.append(d)
        completed_counts.append(trend[d]['COMPLETED'])
        no_show_counts.append(trend[d]['NO_SHOW'])
        cancelled_counts.append(trend[d]['CANCELLED'])
        rejected_counts.append(trend[d]['REJECTED'])
        cur += timedelta(days=1)

    # ── Service distribution — single DB query ─────────────────────────
    service_qs = (
        AppointmentService.objects
        .filter(
            appointment__server=server,
            appointment__start_datetime__date__range=[start_date, end_date],
            appointment__status='COMPLETED',
        )
        .values('service__name', 'service__name_uz', 'service__name_ru')
        .annotate(count=Count('id'))
        .order_by('-count')
    )

    def svc_label(row):
        if lang == 'uz':
            return row['service__name_uz'] or row['service__name'] or '—'
        if lang == 'ru':
            return row['service__name_ru'] or row['service__name'] or '—'
        return row['service__name'] or '—'

    service_labels = [svc_label(r) for r in service_qs]
    service_data = [r['count'] for r in service_qs]

    GUEST_CLIENT_ID = 6
    # ── Top clients — one query per status ─────────────────────────────
    top_completed_clients = list(
        Appointment.objects
        .filter(server=server, start_datetime__date__range=[start_date, end_date],
                status='COMPLETED', client__isnull=False)
        .exclude(client_id=GUEST_CLIENT_ID)
        .values('client__full_name', 'client__phone_number', 'client__email')
        .annotate(count=Count('id'))
        .order_by('-count')[:5]
    )
    top_no_show_clients = list(
        Appointment.objects
        .filter(server=server, start_datetime__date__range=[start_date, end_date],
                status='NO_SHOW', client__isnull=False)
        .exclude(client_id=GUEST_CLIENT_ID)
        .values('client__full_name', 'client__phone_number', 'client__email')
        .annotate(count=Count('id'))
        .order_by('-count')[:5]
    )
    top_debtor_clients = list(
        Appointment.objects
        .filter(server=server, start_datetime__date__range=[start_date, end_date],
                status='COMPLETED', client__isnull=False)
        .exclude(client_id=GUEST_CLIENT_ID)
        .values('client__full_name', 'client__phone_number', 'client__email')
        .annotate(total_debt=Sum('total_amount') - Sum('paid_amount'))
        .filter(total_debt__gt=0)
        .order_by('-total_debt')[:5]
    )

    # ── Day-of-week distribution — single DB query — 1=Mon … 7=Sun ────
    dow_qs = (
        base_qs
        .annotate(weekday=ExtractIsoWeekDay('start_datetime'))
        .values('weekday')
        .annotate(count=Count('id'))
        .order_by('weekday')
    )
    dow_map = {r['weekday']: r['count'] for r in dow_qs}
    dow_data = [dow_map.get(i, 0) for i in range(1, 8)]

    context_data = {
        'start_date': start_date,
        'end_date': end_date,
        # KPIs
        'kpi_total': total,
        'kpi_completed': completed,
        'kpi_no_show': no_show,
        'kpi_cancelled': cancelled,
        'kpi_rejected': rejected,
        'kpi_total_paid': f"{total_paid:,}",
        'rate_completed': pct(completed, total),
        'rate_no_show': pct(no_show, total),
        'rate_cancelled': pct(cancelled, total),
        # Charts
        'labels': json.dumps(labels),
        'completed_counts': json.dumps(completed_counts),
        'no_show_counts': json.dumps(no_show_counts),
        'cancelled_counts': json.dumps(cancelled_counts),
        'rejected_counts': json.dumps(rejected_counts),
        'service_labels': json.dumps(service_labels),
        'service_data': json.dumps(service_data),
        'has_service_data': bool(service_data),
        'dow_data': json.dumps(dow_data),
        # Tables
        'top_completed_clients': top_completed_clients,
        'top_no_show_clients': top_no_show_clients,
        'top_debtor_clients': top_debtor_clients,
    }
    return render(request, 'booket/dashboard/statistics.html', context=context_data)


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
    TERMINAL_STATUSES = ["COMPLETED", "NO_SHOW", "CANCELLED", "REJECTED"]
    provider = get_object_or_404(Provider, owner=request.user)
    lang = getattr(request, 'LANGUAGE_CODE', 'en')

    start_date_str = request.GET.get("start_date")
    end_date_str = request.GET.get("end_date")
    try:
        if start_date_str and end_date_str:
            start_date = datetime.strptime(start_date_str, "%Y-%m-%d").date()
            end_date = datetime.strptime(end_date_str, "%Y-%m-%d").date()
        else:
            raise ValueError
    except ValueError:
        today = timezone.now().date()
        start_date = today.replace(day=1)
        end_date = today

    if start_date > end_date:
        start_date, end_date = end_date, start_date

    # Subquery — no Python evaluation needed here
    provider_server_ids = ProviderServer.objects.filter(provider=provider).values_list('server_id', flat=True)

    base_qs = Appointment.objects.filter(
        server_id__in=provider_server_ids,
        start_datetime__date__range=[start_date, end_date],
        status__in=TERMINAL_STATUSES,
    )

    # ── KPI aggregates — single DB query ───────────────────────────────
    kpi = base_qs.aggregate(
        total=Count('id'),
        completed=Count('id', filter=Q(status='COMPLETED')),
        no_show=Count('id', filter=Q(status='NO_SHOW')),
        cancelled=Count('id', filter=Q(status='CANCELLED')),
        rejected=Count('id', filter=Q(status='REJECTED')),
        total_paid=Sum('paid_amount', filter=Q(status='COMPLETED')),
    )
    total = kpi['total'] or 0
    completed = kpi['completed'] or 0
    no_show = kpi['no_show'] or 0
    cancelled = kpi['cancelled'] or 0
    rejected = kpi['rejected'] or 0
    total_paid = int(kpi['total_paid'] or 0)

    def pct(part, whole):
        return f"{round(part / whole * 100, 1):.1f}" if whole else "0.0"

    # ── Trend time-series — single aggregated DB query ─────────────────
    trend_qs = (
        base_qs
        .annotate(appt_date=TruncDate('start_datetime'))
        .values('appt_date', 'status')
        .annotate(count=Count('id'))
        .order_by('appt_date', 'status')
    )
    trend = defaultdict(lambda: dict.fromkeys(TERMINAL_STATUSES, 0))
    for row in trend_qs:
        trend[row['appt_date'].strftime("%Y-%m-%d")][row['status']] = row['count']

    labels, completed_counts, no_show_counts, cancelled_counts, rejected_counts = [], [], [], [], []
    cur = start_date
    while cur <= end_date:
        d = cur.strftime("%Y-%m-%d")
        labels.append(d)
        completed_counts.append(trend[d]['COMPLETED'])
        no_show_counts.append(trend[d]['NO_SHOW'])
        cancelled_counts.append(trend[d]['CANCELLED'])
        rejected_counts.append(trend[d]['REJECTED'])
        cur += timedelta(days=1)

    # ── Service distribution — single DB query ─────────────────────────
    service_qs = (
        AppointmentService.objects
        .filter(
            appointment__server_id__in=provider_server_ids,
            appointment__start_datetime__date__range=[start_date, end_date],
            appointment__status='COMPLETED',
        )
        .values('service__name', 'service__name_uz', 'service__name_ru')
        .annotate(count=Count('id'))
        .order_by('-count')
    )

    def svc_label(row):
        if lang == 'uz':
            return row['service__name_uz'] or row['service__name'] or '—'
        if lang == 'ru':
            return row['service__name_ru'] or row['service__name'] or '—'
        return row['service__name'] or '—'

    service_labels = [svc_label(r) for r in service_qs]
    service_data = [r['count'] for r in service_qs]

    GUEST_CLIENT_ID = 6
    # ── Top clients — one query per status ─────────────────────────────
    top_completed_clients = list(
        Appointment.objects
        .filter(server_id__in=provider_server_ids,
                start_datetime__date__range=[start_date, end_date],
                status='COMPLETED', client__isnull=False)
        .exclude(client_id=GUEST_CLIENT_ID)
        .values('client__full_name', 'client__phone_number', 'client__email')
        .annotate(count=Count('id'))
        .order_by('-count')[:5]
    )
    top_no_show_clients = list(
        Appointment.objects
        .filter(server_id__in=provider_server_ids,
                start_datetime__date__range=[start_date, end_date],
                status='NO_SHOW', client__isnull=False)
        .exclude(client_id=GUEST_CLIENT_ID)
        .values('client__full_name', 'client__phone_number', 'client__email')
        .annotate(count=Count('id'))
        .order_by('-count')[:5]
    )

    # ── Staff performance — single aggregated DB query ─────────────────
    staff_qs = (
        base_qs
        .values('server__id', 'server__user__first_name', 'server__user__last_name')
        .annotate(
            total=Count('id'),
            completed=Count('id', filter=Q(status='COMPLETED')),
            no_show=Count('id', filter=Q(status='NO_SHOW')),
            cancelled=Count('id', filter=Q(status='CANCELLED')),
            total_paid=Sum('paid_amount', filter=Q(status='COMPLETED')),
        )
        .order_by('-completed')
    )
    staff_performance = []
    server_labels = []
    server_data = []
    for s in staff_qs:
        s_total = s['total'] or 0
        s_completed = s['completed'] or 0
        name = f"{s['server__user__first_name'] or ''} {s['server__user__last_name'] or ''}".strip() or '—'
        rate_num = round(s_completed / s_total * 100, 1) if s_total else 0.0
        staff_performance.append({
            'name': name,
            'total': s_total,
            'completed': s_completed,
            'no_show': s['no_show'] or 0,
            'cancelled': s['cancelled'] or 0,
            'completion_rate': pct(s_completed, s_total),
            'completion_rate_num': rate_num,
            'total_paid': f"{int(s['total_paid'] or 0):,}",
        })
        server_labels.append(name)
        server_data.append(s_completed)

    # ── New vs returning clients — two targeted queries ─────────────────
    local_tz = timezone.get_current_timezone()
    # Step 1: distinct non-guest client IDs who had any terminal appointment in range
    client_id_subquery = (
        base_qs
        .filter(client__isnull=False)
        .exclude(client_id=GUEST_CLIENT_ID)
        .values('client_id')
        .distinct()
    )
    total_unique_clients = client_id_subquery.count()

    if total_unique_clients:
        # Step 2: for each of those clients find their very first visit to this provider.
        # Use astimezone to compare against local dates (USE_TZ=True stores in UTC).
        first_visits = list(
            Appointment.objects
            .filter(server_id__in=provider_server_ids, client_id__in=client_id_subquery)
            .values('client_id')
            .annotate(first_visit=Min('start_datetime'))
        )
        new_clients_count = sum(
            1 for c in first_visits
            if start_date <= c['first_visit'].astimezone(local_tz).date() <= end_date
        )
    else:
        new_clients_count = 0
    returning_clients_count = total_unique_clients - new_clients_count

    # ── Day-of-week distribution — single DB query — 1=Mon … 7=Sun ────
    dow_qs = (
        base_qs
        .annotate(weekday=ExtractIsoWeekDay('start_datetime'))
        .values('weekday')
        .annotate(count=Count('id'))
        .order_by('weekday')
    )
    dow_map = {r['weekday']: r['count'] for r in dow_qs}
    dow_data = [dow_map.get(i, 0) for i in range(1, 8)]

    context_data = {
        'start_date': start_date,
        'end_date': end_date,
        # KPIs
        'kpi_total': total,
        'kpi_completed': completed,
        'kpi_no_show': no_show,
        'kpi_cancelled': cancelled,
        'kpi_rejected': rejected,
        'kpi_total_paid': f"{total_paid:,}",
        'rate_completed': pct(completed, total),
        'rate_no_show': pct(no_show, total),
        'rate_cancelled': pct(cancelled, total),
        # Clients
        'new_clients': new_clients_count,
        'returning_clients': returning_clients_count,
        'total_unique_clients': total_unique_clients,
        # Charts
        'labels': json.dumps(labels),
        'completed_counts': json.dumps(completed_counts),
        'no_show_counts': json.dumps(no_show_counts),
        'cancelled_counts': json.dumps(cancelled_counts),
        'rejected_counts': json.dumps(rejected_counts),
        'service_labels': json.dumps(service_labels),
        'service_data': json.dumps(service_data),
        'has_service_data': bool(service_data),
        'server_labels': json.dumps(server_labels),
        'server_data': json.dumps(server_data),
        'dow_data': json.dumps(dow_data),
        # Tables
        'staff_performance': staff_performance,
        'top_completed_clients': top_completed_clients,
        'top_no_show_clients': top_no_show_clients,
    }
    return render(request, 'booket/dashboard/provider_statistics.html', context=context_data)
