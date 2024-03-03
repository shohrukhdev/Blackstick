import json
import traceback
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.shortcuts import render, redirect

from dent.models import Role, Staff
from dent.settings import service


@login_required
def settings_window(request, *args, **kwargs) -> HttpResponse:
    """Main settings page view."""
    if request.method == "GET":
        return render(request, "dent/settings/main.html")


@login_required
def staff_list(request, *args, **kwargs) -> HttpResponse:
    """Main staff list page view."""
    if request.method == "GET":
        staff = service.get_clinic_staff(request.session["clinic_id"])
        context = {
            "staff": staff
        }
        return render(
            request=request,
            template_name="dent/settings/user/list.html",
            context=context
        )


@login_required
def add_new_staff(request, *args, **kwargs) -> HttpResponse:
    """Add new staff."""
    if request.method == "GET":
        roles = service.get_roles()
        context = {"roles": roles}
        return render(
            request=request,
            template_name="dent/settings/user/add.html",
            context=context
        )

    if request.method == "POST":
        try:
            new_user = service.create_user(
                username=request.POST.get("username"),
                password=request.POST.get("password"),
                email=request.POST.get("email"),
                first_name=request.POST.get("first_name"),
                last_name=request.POST.get("last_name")
            )
            try:
                new_staff = service.create_staff(
                    user=new_user,
                    clinic_id=request.session["clinic_id"],
                    role_code=request.POST.get("role_code"),
                    additional_info=request.POST.get("additional_info"),
                    cur_user=request.user,
                    cur_user_role=request.session["role"]
                )
                return redirect("/settings/user_list?successSave=true")
            except Exception as e:
                new_user.delete()  # delete user since staff not created
                roles = service.get_roles()
                context = {"error_msg": str(traceback.format_exc()), "roles": roles}
                return render(
                    request=request,
                    template_name="dent/settings/user/add.html",
                    context=context
                )
        except Exception as e:
            roles = service.get_roles()
            error_msg = f"User creation error: {e}"
            if "UNIQUE constraint failed" in str(e):
                error_msg = f"username '{request.POST.get("username")}' already exists!"
            context = {"roles": roles, "error_msg": error_msg}
            return render(
                request=request,
                template_name="dent/settings/user/add.html",
                context=context
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
        context = {
            "staff": staff,
            "roles": roles,
        }
        return render(
            request=request,
            template_name="dent/settings/user/edit.html",
            context=context,
        )
    if request.method == "POST":
        staff_id = request.POST.get("staff_id")
        try:
            staff = Staff.objects.get(pk=staff_id)
            user = staff.user
            user.first_name = request.POST.get("first_name")
            user.last_name = request.POST.get("last_name")
            user.email = request.POST.get("email")
            role = Role.objects.get(code=request.POST.get("role_code"))
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
            context = {"error_msg": str(traceback.format_exc()), "roles": roles}
            return render(
                request=request,
                template_name="dent/settings/user/add.html",
                context=context
            )
############################# CATEGORY ##############################################
@login_required
def category_list(request, *args, **kwargs):
    clinic_id = request.session.get("clinic_id")
    if request.method == "GET":
        try:
            categories = service.get_clinic_categories(clinic_id=clinic_id)
            context = {"categories": categories}
            return render(
                request=request,
                template_name="dent/settings/category/list.html",
                context=context
            )
        except Exception as e:
            context = {"error_msg": str(traceback.format_exc())}
            return render(
                request=request,
                template_name="dent/settings/category/list.html",
                context=context
            )

@login_required
def category_add(request, *args, **kwargs):
    if request.method == "GET":
        context = {"error_msg": str(traceback.format_exc())}
        return render(
                request=request,
                template_name="dent/settings/category/add.html",
                context=context
            )

