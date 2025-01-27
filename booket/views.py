from lib2to3.fixes.fix_input import context

from django.contrib.auth import authenticate, login
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseRedirect, HttpResponse
from django.shortcuts import render
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
        service_types = sv.get_provider_service_types(provider)
        context_data = {
            "provider": provider,
            "service_types": service_types,
        }
        return render(request, "booket/provider.html", context=context_data)
