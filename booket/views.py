import traceback
from lib2to3.fixes.fix_input import context

from django.contrib.auth import authenticate, login
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseRedirect, HttpResponse
from django.shortcuts import render, get_object_or_404
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
        provider = sv.get_owners_provider(request.user)
        context_data = {
            "provider": provider,
        }
        return render(request, "booket/provider.html", context=context_data)


@login_required
def provider_edit(request):
    if request.method == "GET":
        try:
            provider = sv.get_owners_provider(request.user)
            context_data = {"provider": provider}
        except Exception as e:
            context_data = {
                "success": False,
                "error": traceback.format_exc()
            }
        return render(request, "booket/provider_edit.html", context=context_data)
    elif request.method == "POST":
        try:
            provider = get_object_or_404(Provider, id=request.POST.get("provider_id"))
            provider.name = request.POST.get("name")
            provider.address = request.POST.get("address")
            provider.city = request.POST.get("description")
            provider.is_active = 'is_active' in request.POST  # Boolean check

        except Exception as e:
            context_data = {
                "success": False,
                "error": traceback.format_exc()
            }


