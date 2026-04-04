import json
import logging

from django.contrib.auth import authenticate, login
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpResponseRedirect, HttpResponse
from django.shortcuts import render, redirect
from django.utils import timezone

import dent.services as service
from dent.models import Event

logger = logging.getLogger(__name__)


def user_login(request):
    if request.method == "POST":
        username = request.POST.get("username")
        password = request.POST.get("password")
        user = authenticate(username=username, password=password)
        if user is not None:
            if user.is_active:
                login(request, user)
                staff = service.get_staff(user)
                request.session['role'] = staff.role.code
                request.session['clinic'] = staff.clinic.name
                request.session['clinic_id'] = staff.clinic.id
                return HttpResponseRedirect("/home")
            else:
                return HttpResponse("Your account is disabled")
        else:
            return render(
                request,
                template_name='login.html',
                context={"error": "Incorrect username or password"}
            )
    else:
        if request.get_host() in ["booket.uz"]:
            return redirect("https://booket.uz/b/login")
        return render(request, 'login.html', {})


def demo_user_login(request):
    if request.method == "POST":
        username = request.POST.get("username")
        password = request.POST.get("password")
        user = authenticate(username=username, password=password)
        if user is not None and "demo" in username:
            if user.is_active:
                login(request, user)
                staff = service.get_staff(user)
                request.session['role'] = staff.role.code
                request.session['clinic'] = staff.clinic.name
                request.session['clinic_id'] = staff.clinic.id
                return HttpResponseRedirect("/home")
            else:
                return HttpResponse("Your account is disabled")
        else:
            return render(
                request,
                template_name='demo_login.html',
                context={"error": "Incorrect username or password"}
            )
    else:
        return render(request, 'demo_login.html', {})


@login_required
def home(request):
    context_data = {}

    # Get the staff associated with the logged-in user
    staff = service.get_staff(request.user)

    # Get the 5 upcoming events for this staff
    upcoming_events = Event.objects.filter(
        staff=staff,
        start_time__gte=timezone.now()
    ).order_by('start_time')[:7]

    context_data['recent_events'] = upcoming_events
    context_data['staff_notes'] = staff.notes

    # Handle notes update if it's a POST request
    if request.method == 'POST' and 'notes' in request.POST:
        staff.notes = request.POST.get('notes')
        staff.save()
        # Redirect to prevent form resubmission
        return redirect('home')

    return render(
        request,
        'dent/report.html',
        context=context_data
    )


@login_required
def calendar(request):
    return render(request, 'dent/calendar.html')


@login_required
def calendar_list(request):
    return render(request, 'dent/calendar_list.html')


@login_required
def debt_list(request):
    return render(request, 'dent/debt_list.html')


@login_required
def add_event(request):
    if request.method != 'POST':
        return JsonResponse({"success": False, "message": "Method not allowed."}, status=405)
    response = service.add_event(request.POST, request.user)
    return JsonResponse(response, status=200)


@login_required
def delete_event(request):
    response = {}
    if request.method == 'POST':
        response = service.delete_event(request.POST['event_id'])
        return JsonResponse(response, status=200)
    else:
        return JsonResponse(response, status=400)


@login_required
def patient_list(request):
    return render(request, 'dent/patient_list.html')


@login_required
def patient_add(request):
    response = {}
    if request.method == 'GET':
        return render(request, 'dent/add_patient.html')
    elif request.method == 'POST':
        response = service.add_patient(request.POST, request.user)
        return JsonResponse(response, status=200, safe=False)
    else:
        return JsonResponse(response, status=405)


@login_required
def patient_edit(request):
    if request.method == 'GET':
        context = {"patient": service.get_patient(request.GET['patient_ref_id'])}
        return render(request, 'dent/edit_patient.html', context=context)
    elif request.method == 'POST':
        response = service.edit_patient(request.POST, request.user)
        return JsonResponse(response, status=200, safe=False)
    return None


@login_required
def get_patient_list_json(request):
    try:
        data = service.get_clinic_patients_json(request.user)
        return JsonResponse({"success": True, "data": data}, safe=False)
    except Exception as e:
        logger.exception("Error fetching patient list")
        return JsonResponse({"success": False, "message": str(e)}, status=500, safe=False)


@login_required
def treatment(request):
    if request.method == 'GET':
        context = service.treatment_get_context(
            cur_user=request.user,
            patient_ref_id=request.GET.get('patient_ref_id'),
            clinic_id=request.session.get('clinic_id')
        )
        return render(request, 'dent/treatement.html', context=context)
    return None


@login_required
def save_treatment(request):
    if request.method == 'POST':
        data = json.loads(request.body)
        response = service.save_treatment(request.user, data)
        return JsonResponse(response, status=200, safe=False)
    return None


@login_required
def get_treatment(request):
    if request.method == 'GET':
        context = service.get_treatment(request.GET['treatment_ref_id'])
        return render(request, 'dent/treatment_info.html', context=context)
    return None


@login_required
def treatment_print(request):
    if request.method == 'GET':
        context = service.get_treatment(request.GET['treatment_ref_id'])
        return render(request, 'dent/treatment_print.html', context=context)
    return None


@login_required
def patient_treatment_history(request):
    if request.method == 'GET':
        context = service.get_patient_treatment_history(
            cur_user=request.user,
            patient_ref_id=request.GET['patient_ref_id']
        )
        return render(request, 'dent/treatment_history.html', context=context)
    return None


@login_required
def treatment_history(request):
    if request.method == 'GET':
        return render(request, 'dent/settings/treatment_list.html')
    return None


@login_required
def event_edit(request):
    if request.method == 'POST':
        data = json.loads(request.body)
        response = service.edit_event(data)
        return JsonResponse(response, status=200, safe=False)
    return None


@login_required
def upload_file(request):
    if request.method == 'POST':
        response = service.save_treatment_file(
            request.user, request
        )
        return redirect(
            f"/treatment/info?treatment_ref_id={response['treatment_ref_id']}"
            f"&success={response['success']}"
            f"&error_msg={response.get('error_msg')}"
        )
    return None


@login_required
def edit_treatment(request):
    if request.method == 'GET':
        context = service.get_treatment(request.GET['treatment_ref_id'])
        return render(request, 'dent/treatment_edit.html', context=context)
    elif request.method == 'POST':
        request_data = json.loads(request.body)
        success, error_message = service.edit_treatment(
            treatment_ref_id=request_data.get("reference_id"),
            new_paid_amount=request_data.get("paid_amount")
        )
        return JsonResponse(
            {"success": success, "message": error_message},
            status=200 if success else 400
        )
    return None
