from django.urls import path
from booket import views as b_views
from django.contrib.auth import views as authview

urlpatterns = [
    path('login/', b_views.user_login, name="b_login"),
    path('logout/', authview.LogoutView.as_view(template_name="booket/logout.html"), name="b_logout"),
    path('provider/', b_views.provider_main, name="b_provider_main"),
    path('provider/edit/', b_views.provider_edit, name="b_provider_edit"),
    path('provider/photo/', b_views.provider_photos, name="b_provider_photos"),

    path('server/edit/<int:id>/', b_views.server_edit, name="b_server_edit"),
    path('servicetype/add/', b_views.service_type_add, name="b_service_type_add"),
    path('servicetype/edit/<int:id>/', b_views.service_type_edit, name="b_service_type_edit"),

    path('service/list/<int:type_id>/', b_views.service_list, name="b_service_list"),
    path('service/add/<int:type_id>/', b_views.service_add, name="b_service_add"),
    path('service/edit/<int:id>/', b_views.service_edit, name="b_service_edit"),

    path('server/<int:server_id>/services/', b_views.server_services, name="b_server_services"),
]
