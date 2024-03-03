from .models import *
from datetime import datetime
import traceback
from .serializers import *
from django.core import serializers
import json
from django.core.serializers.json import DjangoJSONEncoder


def get_staff(user):
    return Staff.objects.get(user=user)


def add_event(form, cur_user):
    response = {}
    try:
        staff = Staff.objects.get(user=cur_user)
        start_time_obj = datetime.strptime(form['start_time'], '%d.%m.%Y %H:%M')
        end_time_obj = datetime.strptime(form['end_time'], '%d.%m.%Y %H:%M')
        patient = Patient.objects.get(id=form['patient_id'])
        Event.objects.create(staff=staff,
                             patient=patient,
                             title=form['title'],
                             start_time=start_time_obj,
                             end_time=end_time_obj,
                             background_color=form['background'],
                             border_color=form['background'])
        response['success'] = True
    except Exception as e:
        response['success'] = False
        response['error_msg'] = str(traceback.format_exc())
    return response


def edit_event(form):
    response = {}
    try:
        event = Event.objects.get(id=form['event_id'])
        event.start_time = datetime.fromtimestamp(form['start_time'])
        event.end_time = datetime.fromtimestamp(form['end_time'])
        event.save()
        response['success'] = True
    except Exception as e:
        response['success'] = False
        response['error_msg'] = str(traceback.format_exc())
    return response


def delete_event(id):
    response = {}
    try:
        event = Event.objects.get(id=id)
        event.delete()
        response['success'] = True
    except Exception as e:
        response['error_msg'] = str(traceback.format_exc())
        response['success'] = False
    return response


def add_patient(form, cur_user):
    response = {}
    try:
        staff = Staff.objects.get(user=cur_user)
        date_birth = datetime.strptime(form['date_birth'], '%d.%m.%Y')
        new_patient = Patient.objects.create(clinic=staff.clinic,
                               full_name=form['full_name'],
                               mobile_phone=form['mobile_phone'],
                               sex=form['sex'],
                               date_birth=date_birth,
                               comments=form['comments'],
                               state='A',
                               cr_by=staff,
                               up_by=staff)
        new_patient.reference_id = str(new_patient.id) + '0' + str(int(datetime.now().timestamp()))
        new_patient.save()
        response['success'] = True
    except Exception as e:
        response['success'] = False
        response['error_msg'] = str(traceback.format_exc())

    return response


def get_patient(patient_ref_id):
    return Patient.objects.get(reference_id=patient_ref_id)


def edit_patient(form, cur_user):
    response = {}
    try:
        Patient.objects.filter(id=form['id']).update(
            full_name=form['full_name'],
            mobile_phone=form['mobile_phone'],
            sex=form['sex'],
            date_birth=datetime.strptime(form['date_birth'], '%d.%m.%Y'),
            comments=form['comments'],
            state=form['state'],
            up_by=get_staff(cur_user)
        )
        response['success'] = True
    except Exception as e:
        response['success'] = False
        response['error_msg'] = str(traceback.format_exc())
    return response


def delete_patient(patient_ref_id, cur_user):
    response = {}
    try:
        Patient.objects.filter(reference_id=patient_ref_id).update(
            state='D',
            up_by=get_staff(cur_user)
        )
        response['success'] = True
    except Exception as e:
        response['success'] = False
        response['error_msg'] = str(traceback.format_exc())
    return response


def get_clinic_patients_json(cur_user):
    patient_list = []
    staff = get_staff(cur_user)
    patients = Patient.objects.filter(clinic=staff.clinic, state='A')
    for p in patients:
        pat = {"id": p.id, "name": p.full_name, "phone": p.mobile_phone}
        patient_list.append(pat)
    return patient_list


def treatment_get_context(cur_user, patient_ref_id):
    staff = Staff.objects.get(user=cur_user)
    patient = Patient.objects.get(reference_id=patient_ref_id)
    services = Service.objects.filter(doctor=staff, status=1).values()
    categories = ServiceCategory.objects.filter(staff=staff)
    tooth_states = ToothState.objects.all().values()
    teeth = Teeth.objects.all()
    json_ser = json.dumps(list(services), cls=DjangoJSONEncoder)
    json_states = json.dumps(list(tooth_states), cls=DjangoJSONEncoder)
    context = {'doctor': staff,
               'patient': patient,
               'categories': categories,
               'tooth_states': json_states,
               'services': json_ser,
               'teeth': teeth}
    return context


def save_treatment(cur_user, data):
    procedure = None
    response = {}
    try:
        doctor = Staff.objects.get(user=cur_user)
        patient = Patient.objects.get(id=data['patient_id'])
        treatment = Treatment.objects.create(
            reference_id=f'{int(datetime.now().timestamp())}{patient.id}',
            doctor=doctor,
            patient=patient,
            complaint=data['complaint'],
            diagnosis=data['diagnosis'],
            cr_on=datetime.now(),
            description=data['recommendations'],
            total_amount=data['total'],
            discount=data['discount'],
            paid_amount=data['amount_paid'],
            cr_by=cur_user
        )
        treatment.reference_id = str(treatment.id) + '0' + str(int(datetime.now().timestamp()))
        treatment.save()
        for i in data.keys():
            if i.isnumeric():  # IF TOOTH NUMBER
                for s in data[i]:   # SERVICES FOR THAT TOOTH
                    tooth = Teeth.objects.get(id=i)
                    service = Service.objects.get(id=s['id'])
                    procedure = Procedure.objects.create(treatment=treatment,
                                                         teeth=tooth,
                                                         service=service,
                                                         quantity=s['quantity'],
                                                         price=s['price'])

                for ts in data['teeth_states'][i]:  # STATES OF THAT TOOTH
                    tooth_state = ToothState.objects.get(id=ts)
                    tooth = Teeth.objects.get(id=i)
                    ProcedureToothState.objects.create(treatment=treatment,
                                                       teeth=tooth,
                                                       tooth_state=tooth_state)
        response['success'] = True
        response['treatment_ref_id'] = treatment.reference_id
    except Exception as e:
        response['success'] = False
        response['error_msg'] = traceback.format_exc()
    return response


def get_treatment(treatment_ref_id):
    treatment = Treatment.objects.get(reference_id=treatment_ref_id)
    teeth_set = Treatment.objects.get(reference_id=treatment_ref_id).procedure_set
    context = {"treatment": treatment,
               "teeth_set": teeth_set}
    return context


def get_patient_treatment_history(patient_ref_id):
    treatments = Treatment.objects.filter(patient__reference_id=patient_ref_id)
    context = {"treatment_list": treatments}
    return context


def save_treatment_file(user, req):
    response = {}
    treatment = Treatment.objects.get(
        reference_id=req.POST["tr_ref_id"]
    )
    response["treatment_ref_id"] = treatment.reference_id
    try:

        TreatmentFile.objects.create(
            treatment=treatment,
            file_name=req.POST["file_name"],
            file=req.FILES["file"],
            cr_by=user
        )
        response["success"] = True
    except Exception as e:
        response['success'] = False
        response['error_msg'] = traceback.format_exc()
    return response


def get_date(is_today=False):
    import datetime
    today = datetime.date.today()
    beginning_of_month = today.replace(day=1)
    if is_today:
        return datetime.datetime.now()
    else:
        return beginning_of_month


def get_chart_service(pk=None, cid=None, update=False):
    procedure = Procedure.objects.all()
    if update:
        if (cid is not None) and (pk is None):
            procedure = Procedure.objects.filter(service__category_id=int(cid))
        elif (pk is not None) and (cid is None):
            procedure = Procedure.objects.filter(treatment__patient_id=int(pk))
        else:
            procedure = Procedure.objects.filter(treatment__patient_id=int(pk), service__category_id=int(cid))
    services = Service.objects.all()
    serv_key_val = {}
    for i in services:
        serv_amount = 0
        for j in procedure:
            if j.service == i:
                serv_amount += j.quantity
        serv_key_val[i.name] = serv_amount
    return serv_key_val


def report_board(cur_user, start=get_date(), end=get_date(is_today=True), update=False, pid='', c_id=''):
    staff = get_staff(cur_user)
    categories = ServiceCategory.objects.filter(staff=staff)
    patients = Patient.objects.filter(clinic=staff.clinic)
    if update:
        start = datetime.strptime(start, "%d.%m.%Y")
        end = datetime.strptime(end, "%d.%m.%Y")
    patient_date = Patient.objects.filter(
        clinic=staff.clinic,
        cr_on__date__gte=start,
        cr_on__date__lte=end
    )
    patient_amount = len(patient_date)
    patient_sum = 0
    patient_total_sum = 0
    patient_debt = 0
    treatment = Treatment.objects.filter(cr_on__gte=start, cr_on__lte=end)
    treatment_all = Treatment.objects.all()
    if treatment.exists():
        for i in treatment:
            patient_sum += i.total_amount
    for j in treatment_all:
        patient_total_sum += j.total_amount
        patient_debt += j.paid_amount
    patient_debt -= patient_total_sum
    context = {
        'start_date': start.strftime("%d.%m.%Y"),
        'end_date': end.strftime("%d.%m.%Y"),
        'categories': categories,
        'patients': patients,
        'patient_amount': patient_amount,
        'patient_sum': patient_sum,
        'patient_debt': patient_debt
    }
    if pid != '':
        patient = patients.get(id=pid)
        context['patient'] = patient
    if c_id != '':
        category = categories.get(id=pid)
        context['category'] = category
    return context

