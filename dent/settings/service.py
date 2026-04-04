from django.core.exceptions import ValidationError

from dent.models import Staff, Role, Clinic, Category, ServiceStaff, Service
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
    categories = Category.objects.filter(clinic_id=clinic_id)
    return categories


def get_category(category_id, clinic_id):
    return Category.objects.get(id=category_id, clinic_id=clinic_id)


def add_category(
        name_uz,
        name_ru,
        name_en,
        clinic_id,
        user
):
    """Add new category."""
    clinic = Clinic.objects.get(id=clinic_id)
    category = Category.objects.create(
        clinic=clinic,
        name_uz=name_uz,
        name_ru=name_ru,
        name=name_en,
        cr_by=user
    )
    return category


def edit_category(
        category_id,
        clinic_id,
        user_id,
        name_uz,
        name_ru,
        name_en,
):
    """Edit category."""
    category = Category.objects.filter(
        id=category_id,
        clinic_id=clinic_id
    ).update(
        name=name_en,
        name_uz=name_uz,
        name_ru=name_ru,
    )


def delete_category(category_id):
    """Delete category."""
    Category.objects.filter(id=category_id).update(
        is_active=False
    )


############################  SERVICE SETTINGS ############################
def get_staff_services(user_id):
    """Get staff services."""
    return ServiceStaff.objects.filter(staff__user_id=user_id)


def get_staff_service(id, user_id):
    """Get service from staff_service model."""
    return ServiceStaff.objects.get(id=id, staff__user_id=user_id)


def create_staff_service(
        user_id,
        category_id,
        name,
        name_uz,
        name_ru,
        description,
        price
):
    """Create service and service_staff entry."""
    staff = Staff.objects.get(user_id=user_id)
    category = Category.objects.get(id=category_id)
    if staff and category:
        new_service = Service.objects.create(
            category=category,
            name=name,
            name_uz=name_uz,
            name_ru=name_ru,
            description=description,
            price=price
        )
        service_staff = ServiceStaff.objects.create(
            service=new_service,
            staff=staff
        )
        return service_staff


def edit_staff_service(
    user_id,
    service_id,
    category_id,
    name,
    name_uz,
    name_ru,
    description,
    status,
    price
):
    """Edit service staff details."""
    category_obj = Category.objects.get(id=category_id)
    service_staff_qs = ServiceStaff.objects.filter(
        staff__user_id=user_id,
        service_id=service_id
    )
    for service_staff in service_staff_qs:
        service = service_staff.service
        service.category = category_obj
        service.name = name
        service.name_uz = name_uz
        service.name_ru = name_ru
        service.description = description
        service.status = status
        service.price = price
        service.save()


def get_staff_list(clinic_id):
    """Get staff list of the clinic by clinic_id."""
    staff_list = Staff.objects.filter(clinic_id=clinic_id, status=1)
    return staff_list

############ TOOTH STATE #################################

# def add_tooth_state()
