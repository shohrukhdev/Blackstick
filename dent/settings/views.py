import json
import traceback
from lib2to3.fixes.fix_input import context

from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.shortcuts import render, redirect

from dent.models import Role, Staff, Clinic
from dent.settings import service
from dent.settings.service import get_staff_services, get_clinic_categories


@login_required
def settings_window(request, *args, **kwargs) -> HttpResponse:
    """Main settings page view, only dentist or owner can access."""
    if request.method == "GET":
        if request.user.staff_user.role.code in ("OWN", "DEN"):
            return render(request, "dent/settings/main.html")
        return redirect("/")


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
                roles = service.get_roles()
                context_data = {"error_msg": str(traceback.format_exc()), "roles": roles}
                return render(
                    request=request,
                    template_name="dent/settings/user/add.html",
                    context=context_data
                )
        except Exception as e:
            roles = service.get_roles()
            error_msg = f"User creation error: {e}"
            if "UNIQUE constraint failed" in str(e):
                error_msg = f"username {request.POST.get('username', )} already exists!"
            context_data = {"roles": roles, "error_msg": error_msg}
            return render(
                request=request,
                template_name="dent/settings/user/add.html",
                context=context_data
            )

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
            roles = service.get_roles()
            context_data = {"error_msg": str(traceback.format_exc()), "roles": roles}
            return render(
                request=request,
                template_name="dent/settings/user/add.html",
                context=context_data
            )
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
            context_data = {"error_msg": str(traceback.format_exc())}
            return render(
                request=request,
                template_name="dent/settings/category/list.html",
                context=context_data
            )


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
            context_data = {"error_msg": str(traceback.format_exc())}
            return render(
                request=request,
                template_name="dent/settings/category/add.html",
                context=context_data
            )

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
            context_data = {"error_msg": str(traceback.format_exc())}
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
            context_data = {"error_msg": str(traceback.format_exc())}
            return render(
                request=request,
                template_name="dent/settings/category/edit.html",
                context=context_data
            )


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
            context_data = {"error_msg": str(traceback.format_exc())}
            return render(
                request=request,
                template_name="dent/settings/service/list.html",
                context=context_data
            )


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
            context_data = {"error_msg": str(traceback.format_exc())}
            return render(
                request=request,
                template_name="dent/settings/service/add.html",
                context=context_data
            )


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
            context_data = {"error_msg": str(traceback.format_exc())}
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
            context_data = {"error_msg": str(traceback.format_exc())}
            return render(
                request=request,
                template_name="dent/settings/service/edit.html",
                context=context_data
            )

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
            context_data = {"error_msg": str(traceback.format_exc())}
            return render(
                request,
                template_name="dent/settings/tooth_state/list.html",
                context=context_data
            )


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
            context_data = {"error_msg": str(traceback.format_exc())}
            return render(
                request,
                template_name="dent/settings/clinic_details.html",
                context=context_data
            )
