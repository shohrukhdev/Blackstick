from django.contrib.auth import authenticate, login
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseRedirect, HttpResponse
from django.shortcuts import render, get_object_or_404, redirect
from booket import services as sv
from booket.forms.provider_photo import ProviderPhotosFormSet

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
                    return HttpResponseRedirect("/b/provider")
                elif Server.is_user_server(user):
                    request.session['server'] = True
                    return HttpResponseRedirect("/b/server")
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
    if request.method == "GET":
        context_data = sv.get_owners_provider(request.user)
        return render(request, "booket/provider.html", context=context_data)


@login_required
def provider_edit(request):
    if request.method == "GET":
        context_data = sv.get_owners_provider(request.user)
        return render(request, "booket/provider_edit.html", context=context_data)
    elif request.method == "POST":
        context_data = sv.edit_provider(request)
        return render(request, "booket/provider.html", context=context_data)


@login_required
def server_edit(request, id: int):
    if request.method == "GET":
        context_data = sv.get_server_by_id(user=request.user, server_id=id)
        return render(request, "booket/server_edit.html", context=context_data)
    elif request.method == "POST":
        context_data = sv.edit_server(request)
        return render(request, "booket/server_edit.html", context=context_data)


@login_required
def service_type_add(request):
    if request.method == "GET":
        return render(request, "booket/service_type.html")
    elif request.method == "POST":
        context_data = sv.add_service_type(request)
        if not context_data["success"]:
            return render(request, "booket/service_type.html", context=context_data)
        return HttpResponseRedirect('/b/provider/')


@login_required
def service_type_edit(request, id: int):
    if request.method == "GET":
        context_data = sv.get_service_type(id=id, user=request.user)
        return render(request, "booket/service_type_edit.html", context=context_data)
    elif request.method == "POST":
        context_data = sv.edit_service_type(request)
        if not context_data.get("success"):
            return render(request, "booket/service_type_edit.html", context=context_data)
        return HttpResponseRedirect('/b/provider/')


@login_required
def service_list(request, type_id: int):
    if request.method == "GET":
        context_data = sv.get_service_list_by_type(type_id=type_id, user=request.user)
        return render(request, "booket/service_list.html", context=context_data)


@login_required
def service_add(request, type_id: int):
    if request.method == "GET":
        context_data = sv.get_service_type(id=type_id, user=request.user)
        return render(request, "booket/service_add.html", context=context_data)
    elif request.method == "POST":
        result = sv.add_service(request)
        if result.get("success") is False:
            context_data = sv.get_service_type(id=type_id, user=request.user)
            context_data["error"] = result.get("error")
            return render(request, "booket/service_add.html", context=context_data)
        sr = result["sr"]
        return HttpResponseRedirect(f'/b/service/list/{sr.tip.id}')


@login_required
def service_edit(request, id: int):
    if request.method == "GET":
        context_data = sv.get_service(id=id, user=request.user)
        return render(request, "booket/service_edit.html", context=context_data)
    elif request.method == "POST":
        result = sv.edit_service(request)
        sr = result["service"]
        if result.get("success") is False:
            context_data = sv.get_service(id=id, user=request.user)
            context_data["success"] = False
            context_data["error"] = result.get("error")
            return render(request, "booket/service_edit.html", context=context_data)
        return HttpResponseRedirect(f'/b/service/list/{sr.tip.id}/')


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