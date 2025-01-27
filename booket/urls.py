from django.urls import path, include
from booket import views as b_views
from django.contrib.auth import views as authview

urlpatterns = [
    path('login/', b_views.user_login, name="b_login"),
    path('logout/', authview.LogoutView.as_view(template_name="booket/logout.html"), name="b_logout"),
    path('provider/', b_views.provider_main, name="b_provider_main"),
]
