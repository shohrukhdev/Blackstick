import traceback

from django.core.exceptions import ValidationError

from dent.models import Staff, Role, Clinic, ServiceCategory
from django.contrib.auth.models import User
import datetime as dt


def get_clinic_staff(clinic_id):
    """Get staff by clinic_id."""
    return Staff.objects.filter(clinic_id=clinic_id)


def get_roles():
    """Get all roles."""
    return Role.objects.all()


def create_user(
        username,
        password,
        email,
        first_name,
        last_name
):
    """Create new user."""
    user = User.objects.create_user(
        username=username,
        password=password,
        email=email
    )
    user.first_name = first_name
    user.last_name = last_name
    user.save()
    return user


def create_staff(
        user,
        clinic_id,
        role_code,
        additional_info,
        cur_user,
        cur_user_role
):
    """Create new staff"""
    if role_code == "OWN" and cur_user_role != "OWN":
        raise ValidationError("Only owners can create new owner!")
    role = Role.objects.get(code=role_code)
    clinic = Clinic.objects.get(id=clinic_id)
    staff = Staff.objects.create(
        user=user,
        clinic=clinic,
        role=role,
        additional_info=additional_info,
        hire_date=dt.datetime.now(),
        cr_by=cur_user
    )
    return staff


def get_staff(user_id, clinic_id):
    """Get staff object."""
    return Staff.objects.get(user_id=user_id, clinic_id=clinic_id)


def get_clinic_categories(clinic_id):
    """Get clinic's all categories."""
    categories = ServiceCategory.objects.filter(clinic_id=clinic_id)
    return categories


def add_category(
        name_uz,
        name_ru,
        name_en,
        clinic_id,
        user
):
    """Add new category."""
    clinic = Clinic.objects.get(id=clinic_id)
    category = ServiceCategory.objects.create(
        clinic=clinic,
        name_uz=name_uz,
        name_ru=name_ru,
        name=name_en,
        cr_by=user
    )
    return category

