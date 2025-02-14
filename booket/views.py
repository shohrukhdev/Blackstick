import traceback
from lib2to3.fixes.fix_input import context

from django.contrib.auth import authenticate, login
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseRedirect, HttpResponse
from django.shortcuts import render, get_object_or_404, redirect
from booket import services as sv

from booket.models import Provider, Server


def user_login(request):
    if request.method == "POST":
        username = request.POST.get("username")
        password = request.POST.get("password")
        user = authenticate(username=username, password=password)
        if user is not None:
            if user.is_active:
                login(request, user)
                if Provider.is_user_owner(user):
                    return HttpResponseRedirect("/b/provider")
                elif Server.is_user_server(user):
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
