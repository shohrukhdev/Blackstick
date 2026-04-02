from django.contrib.auth import authenticate, login
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseRedirect, HttpResponse
from django.shortcuts import render, get_object_or_404, redirect
from django.urls import reverse
from booket import services as sv
from booket.forms.provider_photo import ProviderPhotosFormSet
import qrcode
import io
from booket.models import Provider, Server, ProviderPhotos


def user_login(request):
    if request.method == "POST":
        username = request.POST.get("username")
        password = request.POST.get("password")
        user = authenticate(username=username, password=password)
        if user is not None:
            if user.is_active:
                login(request, user)
                if Provider.is_user_owner(user):
                    request.session['provider'] = True
                    return HttpResponseRedirect(reverse("provider_dashboard_main"))
                elif Server.is_user_server(user):
                    request.session['server'] = True
                    return HttpResponseRedirect(reverse("dashboard_main"))
                else:
                    return HttpResponse("Your account is not a server nor owner")
            else:
                return HttpResponse("Your account is disabled")
        else:
            return render(
                request,
                template_name="booket/login.html",
                context={"error": "Incorrect username or password"}
            )
    else:
        return render(request, "booket/login.html", {})


@login_required
def provider_main(request):
    context_data = sv.get_owners_provider(request.user)
    return render(request, "booket/provider.html", context=context_data)


@login_required
def provider_edit(request):
    if request.method == "POST":
        context_data = sv.edit_provider(request)
        return render(request, "booket/provider.html", context=context_data)
    context_data = sv.get_owners_provider(request.user)
    return render(request, "booket/provider_edit.html", context=context_data)


@login_required
def server_edit(request, id: int):
    if request.method == "POST":
        context_data = sv.edit_server(request)
        return render(request, "booket/server_edit.html", context=context_data)
    context_data = sv.get_server_by_id(user=request.user, server_id=id)
    return render(request, "booket/server_edit.html", context=context_data)


@login_required
def service_type_add(request):
    if request.method == "POST":
        context_data = sv.add_service_type(request)
        if not context_data["success"]:
            return render(request, "booket/service_type.html", context=context_data)
        return HttpResponseRedirect(reverse("b_provider_main"))
    return render(request, "booket/service_type.html")


@login_required
def service_type_edit(request, id: int):
    if request.method == "POST":
        context_data = sv.edit_service_type(request)
        if not context_data.get("success"):
            return render(request, "booket/service_type_edit.html", context=context_data)
        return HttpResponseRedirect(reverse("b_provider_main"))
    context_data = sv.get_service_type(id=id, user=request.user)
    return render(request, "booket/service_type_edit.html", context=context_data)


@login_required
def service_list(request, type_id: int):
    context_data = sv.get_service_list_by_type(type_id=type_id, user=request.user)
    return render(request, "booket/service_list.html", context=context_data)


@login_required
def service_add(request, type_id: int):
    if request.method == "POST":
        result = sv.add_service(request)
        if result.get("success") is False:
            context_data = sv.get_service_type(id=type_id, user=request.user)
            context_data["error"] = result.get("error")
            return render(request, "booket/service_add.html", context=context_data)
        sr = result["sr"]
        return HttpResponseRedirect(reverse("b_service_list", args=[sr.tip.id]))
    context_data = sv.get_service_type(id=type_id, user=request.user)
    return render(request, "booket/service_add.html", context=context_data)


@login_required
def service_edit(request, id: int):
    if request.method == "POST":
        result = sv.edit_service(request)
        if result.get("success") is False:
            context_data = sv.get_service(id=id, user=request.user)
            context_data["error"] = result.get("error")
            return render(request, "booket/service_edit.html", context=context_data)
        service = result["service"]
        return HttpResponseRedirect(reverse("b_service_list", args=[service.tip.id]))
    context_data = sv.get_service(id=id, user=request.user)
    return render(request, "booket/service_edit.html", context=context_data)


@login_required
def server_services(request, server_id: int):
    if request.method == "GET":
        context_data = sv.get_server_services(user=request.user, p_server_id=server_id)
        return render(request, "booket/server_service.html", context=context_data)
    elif request.method == "POST":
        result = sv.edit_server_service(request)
        context_data = sv.get_server_services(user=request.user, p_server_id=server_id)
        if result.get("success") is False:
            context_data["error"] = result.get("error")
        return HttpResponseRedirect(f'/b/server/{result.get("p_server_id")}/services/')


@login_required
def provider_photos(request):
    provider = get_object_or_404(Provider, owner=request.user)
    if request.method == 'POST':
        formset = ProviderPhotosFormSet(request.POST, request.FILES, instance=provider)
        if formset.is_valid():
            formset.save()
            return redirect('/b/provider/photo/')
    else:
        formset = ProviderPhotosFormSet(instance=provider)

    # Fetch existing photos for the carousel
    existing_photos = ProviderPhotos.objects.filter(provider=provider)

    return render(request, 'booket/provider_photo.html', {
        'provider': provider,
        'formset': formset,
        'existing_photos': existing_photos,
    })


@login_required
def provider_qr(request, provider_identifier: str):
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=4,
    )
    qr.add_data(f"https://booket.uz/{provider_identifier}/")  # The URL to encode
    qr.make(fit=True)

    img = qr.make_image(fill_color="black", back_color="white")

    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    buffer.seek(0)

    return HttpResponse(buffer.getvalue(), content_type="image/png")
