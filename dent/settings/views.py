import functools
import logging
from datetime import datetime, date

from django.contrib.auth.decorators import login_required
from django.db.models import Sum, F, ExpressionWrapper, IntegerField
from django.http import HttpResponse
from django.shortcuts import render, redirect

from dent.models import Role, Staff, Clinic, Treatment, Patient
from dent.settings import service
from dent.settings.service import get_staff_services, get_clinic_categories

logger = logging.getLogger(__name__)


@login_required
def settings_window(request, *args, **kwargs) -> HttpResponse:
    """Main settings page view, only dentist or owner can access."""
    if request.method == "GET":
        if request.user.staff_user.role.code in ("OWN", "DEN"):
            return render(request, "dent/settings/main.html")
        return redirect("/")
    return HttpResponse()


@login_required
def staff_list(request, *args, **kwargs) -> HttpResponse:
    """Main staff list page view."""
    if request.method == "GET":
        staff = service.get_clinic_staff(request.session["clinic_id"])
        context_data = {
            "staff": staff
        }
        return render(
            request=request,
            template_name="dent/settings/user/list.html",
            context=context_data
        )
    return None


@login_required
def add_new_staff(request, *args, **kwargs) -> HttpResponse:
    """Add new staff."""
    if request.method == "GET":
        roles = service.get_roles()
        context_data = {"roles": roles}
        return render(
            request=request,
            template_name="dent/settings/user/add.html",
            context=context_data
        )

    if request.method == "POST":
        try:
            new_user = service.create_user(
                username=request.POST.get("username", ),
                password=request.POST.get("password", ),
                email=request.POST.get("email", ),
                first_name=request.POST.get("first_name", ),
                last_name=request.POST.get("last_name", )
            )
            try:
                new_staff = service.create_staff(
                    user=new_user,
                    clinic_id=request.session["clinic_id"],
                    role_code=request.POST.get("role_code", ),
                    additional_info=request.POST.get("additional_info", ),
                    cur_user=request.user,
                    cur_user_role=request.session["role"]
                )
                return redirect("/settings/user_list?successSave=true")
            except Exception as e:
                new_user.delete()  # delete user since staff not created
                logger.exception("Error creating staff for user")
                roles = service.get_roles()
                context_data = {"error_msg": str(e), "roles": roles}
                return render(
                    request=request,
                    template_name="dent/settings/user/add.html",
                    context=context_data
                )
        except Exception as e:
            logger.exception("Error creating user")
            roles = service.get_roles()
            error_msg = f"User creation error: {e}"
            if "UNIQUE constraint failed" in str(e):
                error_msg = f"Username '{request.POST.get('username')}' already exists."
            context_data = {"roles": roles, "error_msg": error_msg}
            return render(
                request=request,
                template_name="dent/settings/user/add.html",
                context=context_data
            )
    return None


@login_required
def edit_staff(request, *args, **kwargs):
    """Edit staff details."""
    roles = service.get_roles()
    if request.method == "GET":
        staff = service.get_staff(
            user_id=request.GET["user_id"],
            clinic_id=request.session.get("clinic_id")
        )
        context_data = {
            "staff": staff,
            "roles": roles,
        }
        return render(
            request=request,
            template_name="dent/settings/user/edit.html",
            context=context_data,
        )
    if request.method == "POST":
        staff_id = request.POST.get("staff_id", )
        try:
            staff = Staff.objects.get(pk=staff_id)
            user = staff.user
            user.first_name = request.POST.get("first_name", )
            user.last_name = request.POST.get("last_name", )
            user.email = request.POST.get("email", )
            role = Role.objects.get(code=request.POST.get("role_code", ))
            staff.user = user
            staff.role = role
            staff.additional_info = request.POST.get("additional_info")
            staff.status = request.POST.get("status")
            staff.user = user
            user.save()
            staff.save()
            return redirect("/settings/user_list?successSave=true")
        except Exception as e:
            logger.exception("Error updating staff")
            roles = service.get_roles()
            context_data = {"error_msg": str(e), "roles": roles}
            return render(
                request=request,
                template_name="dent/settings/user/add.html",
                context=context_data
            )
    return None


############################# CATEGORY ##############################################
@login_required
def category_list(request, *args, **kwargs):
    clinic_id = request.session.get("clinic_id")
    if request.method == "GET":
        try:
            categories = service.get_clinic_categories(clinic_id=clinic_id)
            context_data = {"categories": categories}
            return render(
                request=request,
                template_name="dent/settings/category/list.html",
                context=context_data
            )
        except Exception as e:
            logger.exception("Error fetching categories")
            context_data = {"error_msg": str(e)}
            return render(
                request=request,
                template_name="dent/settings/category/list.html",
                context=context_data
            )
    return None


@login_required
def category_add(request, *args, **kwargs):
    if request.method == "GET":
        return render(
                request=request,
                template_name="dent/settings/category/add.html",
            )
    if request.method == "POST":
        try:
            service.add_category(
                clinic_id=request.session.get("clinic_id"),
                user=request.user,
                name_uz=request.POST.get("name_uz"),
                name_en=request.POST.get("name"),
                name_ru=request.POST.get("name_ru")
            )
            return redirect("/settings/category_list?successSave=true")
        except Exception as e:
            logger.exception("Error adding category")
            context_data = {"error_msg": str(e)}
            return render(
                request=request,
                template_name="dent/settings/category/add.html",
                context=context_data
            )
    return None


@login_required
def category_edit(request, *args, **kwargs):
    if request.method == "GET":
        try:
            category = service.get_category(
                category_id=request.GET.get("category_id"),
                clinic_id=request.session.get("clinic_id")
            )
            context_data = {"category": category}
            return render(
                request=request,
                template_name="dent/settings/category/edit.html",
                context=context_data
            )
        except Exception as e:
            logger.exception("Error fetching category for edit")
            context_data = {"error_msg": str(e)}
            return render(
                request=request,
                template_name="dent/settings/category/list.html",
                context=context_data
            )
    if request.method == "POST":
        try:
            service.edit_category(
                category_id=request.POST.get("category_id"),
                clinic_id=request.session.get("clinic_id"),
                user_id=request.user.id,
                name_uz=request.POST.get("name_uz"),
                name_en=request.POST.get("name"),
                name_ru=request.POST.get("name_ru")
            )
            return redirect("/settings/category_list?successSave=true")
        except Exception as e:
            logger.exception("Error editing category")
            context_data = {"error_msg": str(e)}
            return render(
                request=request,
                template_name="dent/settings/category/edit.html",
                context=context_data
            )
    return None


############################# SERVICE ##############################################


@login_required
def service_list(request, *args, **kwargs):
    if request.method == "GET":
        try:
            services = get_staff_services(request.user.id)
            context_data = {"staff_services": services}
            return render(
                request=request,
                template_name="dent/settings/service/list.html",
                context=context_data
            )
        except Exception as e:
            logger.exception("Error fetching services")
            context_data = {"error_msg": str(e)}
            return render(
                request=request,
                template_name="dent/settings/service/list.html",
                context=context_data
            )
    return None


@login_required
def service_add(request, *args, **kwargs):
    if request.method == "GET":
        context_data = {
            "categories": get_clinic_categories(request.session.get("clinic_id"))
        }
        return render(
            request=request,
            context=context_data,
            template_name="dent/settings/service/add.html"
        )
    if request.method == "POST":
        try:
            service.create_staff_service(
                user_id=request.user.id,
                category_id=request.POST.get("category_id"),
                name_uz=request.POST.get("name_uz"),
                name_ru=request.POST.get("name_ru"),
                name=request.POST.get("name"),
                price=request.POST.get("price"),
                description=request.POST.get("description")
            )
            return redirect("/settings/service_list?successSave=true")
        except Exception as e:
            logger.exception("Error adding service")
            context_data = {"error_msg": str(e)}
            return render(
                request=request,
                template_name="dent/settings/service/add.html",
                context=context_data
            )
    return None


@login_required
def service_edit(request, *args, **kwargs):
    if request.method == "GET":
        try:
            staff_service = service.get_staff_service(
                id=request.GET.get("service_id"),
                user_id=request.user.id
            )
            categories = get_clinic_categories(request.session.get("clinic_id"))
            context_data = {
                "staff_service": staff_service,
                "categories": categories,
            }
            return render(
                request=request,
                template_name="dent/settings/service/edit.html",
                context=context_data,
            )
        except Exception as e:
            logger.exception("Error fetching service for edit")
            context_data = {"error_msg": str(e)}
            return render(
                request=request,
                template_name="dent/settings/service/list.html",
                context=context_data
            )
    elif request.method == "POST":
        try:
            service.edit_staff_service(
                user_id=request.user.id,
                service_id=request.POST.get("service_id"),
                category_id=request.POST.get("category_id"),
                name_uz=request.POST.get("name_uz"),
                name_ru=request.POST.get("name_ru"),
                name=request.POST.get("name"),
                status=request.POST.get("status"),
                price=request.POST.get("price"),
                description=request.POST.get("description")
            )
            return redirect("/settings/service_list?successSave=true")
        except Exception as e:
            logger.exception("Error editing service")
            context_data = {"error_msg": str(e)}
            return render(
                request=request,
                template_name="dent/settings/service/edit.html",
                context=context_data
            )
    return None


#################### TOOTH LIST ################################
@login_required
def tooth_state_list(request, *args, **kwargs):
    if request.method == "GET":
        try:
            context_data = {}
            return render(
                request,
                template_name="dent/settings/tooth_state/list.html",
                context=context_data
            )
        except Exception as e:
            logger.exception("Error fetching tooth state list")
            context_data = {"error_msg": str(e)}
            return render(
                request,
                template_name="dent/settings/tooth_state/list.html",
                context=context_data
            )
    return None


######################## CLINIC DETAILS ###############################
@login_required
def clinic_detail(request, *args, **kwargs):
    if request.method == "GET":
        clinic_object = Clinic.objects.get(id=request.session.get("clinic_id"))
        context_data = {"clinic": clinic_object}
        return render(
            request,
            context=context_data,
            template_name="dent/settings/clinic_details.html"
        )
    if request.method == "POST":
        try:
            Clinic.objects.filter(id=request.session.get("clinic_id")).update(
                name=request.POST.get("name"),
                address=request.POST.get("address"),
                info=request.POST.get("info"),
            )
            clinic_object = Clinic.objects.get(id=request.session.get("clinic_id"))
            context_data = {"clinic": clinic_object}
            return render(
                request,
                context=context_data,
                template_name="dent/settings/clinic_details.html"
            )
        except Exception as e:
            logger.exception("Error updating clinic details")
            context_data = {"error_msg": str(e)}
            return render(
                request,
                template_name="dent/settings/clinic_details.html",
                context=context_data
            )
    return None


@login_required
def dashboard(request, *args, **kwargs) -> HttpResponse:
    """Main settings page view, only dentist or owner can access."""
    if request.method == "GET":
        if request.user.staff_user.role.code in ("OWN", "DEN"):
            return render(request, "dent/settings/dashboard.html")
        return redirect("/")
    return HttpResponse()


# LRU cache with a timeout of 10 minutes and max size of 128 items
def lru_cache_with_timeout(maxsize=128, timeout_minutes=10):
    def decorator(func):
        @functools.lru_cache(maxsize=maxsize)
        def cached_func(*args, cache_timestamp=None, **kwargs):
            return func(*args, **kwargs)

        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # Generate a timestamp based on current time rounded to the nearest timeout period
            # This ensures the cache is invalidated after the timeout period
            now = datetime.now()
            cache_timestamp = int(now.timestamp() // (timeout_minutes * 60))
            return cached_func(*args, cache_timestamp=cache_timestamp, **kwargs)

        # Add cache_clear method for manual cache invalidation
        wrapper.cache_clear = cached_func.cache_clear
        return wrapper

    return decorator


def get_finance_data(user_id, date_start, date_end, cache_timestamp=None):
    """
    Calculate financial data for the given period.
    Cache is automatically invalidated every 5 minutes.
    """
    staff = Staff.objects.get(user_id=user_id)

    # Number of treatments by the current staff within the period
    treatments_count = Treatment.objects.filter(
        doctor=staff,
        cr_on__gte=date_start,
        cr_on__lte=date_end
    ).count()

    # Number of new patients created within the staff's clinic in the given period
    new_patients_count = Patient.objects.filter(
        clinic=staff.clinic,
        cr_on__gte=date_start,
        cr_on__lte=date_end
    ).count()

    # Total sum of paid_amount in Treatment for the given period by the staff
    total_payments = Treatment.objects.filter(
        doctor=staff,
        cr_on__gte=date_start,
        cr_on__lte=date_end
    ).aggregate(total=Sum('paid_amount'))['total'] or 0

    # List of debtor treatments (where paid_amount < total_amount) by the staff for all time
    debtor_treatments = Treatment.objects.annotate(
    actual_amount=ExpressionWrapper(
        F('total_amount') * (100 - F('discount')) / 100.0,
        output_field=IntegerField()
    )
).filter(
    doctor=staff,
    paid_amount__lt=F('actual_amount')
).select_related('patient').order_by('-cr_on')

    return {
        'treatments_count': treatments_count,
        'new_patients_count': new_patients_count,
        'total_payments': total_payments,
        'debtor_treatments': debtor_treatments
    }


@login_required
def finance_dashboard(request):
    if request.method == 'GET':
        # Default date range: start of current month to today
        today = date.today()
        default_date_start = date(today.year, today.month, 1)
        default_date_end = today

        # Get date range from request, or use defaults
        date_start_str = request.GET.get('date_start')
        date_end_str = request.GET.get('date_end')

        try:
            date_start = datetime.strptime(date_start_str, '%Y-%m-%d').date() if date_start_str else default_date_start
            date_end = datetime.strptime(date_end_str, '%Y-%m-%d').date() if date_end_str else default_date_end
        except (ValueError, TypeError):
            date_start = default_date_start
            date_end = default_date_end

        # Convert to datetime with time
        date_start_dt = datetime.combine(date_start, datetime.min.time())
        date_end_dt = datetime.combine(date_end, datetime.max.time())

        # Get financial data
        finance_data = get_finance_data(request.user.id, date_start_dt, date_end_dt)

        context_data = {
            'date_start': date_start,
            'date_end': date_end,
            'treatments_count': finance_data['treatments_count'],
            'new_patients_count': finance_data['new_patients_count'],
            'total_payments': finance_data['total_payments'],
            'debtor_treatments': finance_data['debtor_treatments'],
        }

        return render(
            request,
            'dent/settings/finance_board.html',
            context=context_data
        )
    return None


@login_required
def reception_dashboard(request):
    if request.method == "GET":
        staff_list = service.get_staff_list(clinic_id=request.session.get("clinic_id"))
        context_data = {"staff_list": staff_list}
        return render(request, "dent/reception_calendar.html", context=context_data)

    return None

