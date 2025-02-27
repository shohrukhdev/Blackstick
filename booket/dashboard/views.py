from django.contrib.auth.decorators import login_required
from django.shortcuts import render


@login_required
def dashboard(request):
    if request.method == "GET":
        return render(request, "booket/dashboard/dashboard.html")
