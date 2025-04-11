from django.urls import path
from booket.client import views
from booket.client import api_views as api_view
from booket.client.api_views import ProviderServerDetailView, AvailableTimeSlotsView, ClientViewSet

urlpatterns = [
    path('<str:identifier>/', views.main_page, name='main_page'),
    path('client/search/', api_view.get_client_data, name='search_client'),
    path('provider-server/<int:p_server_id>/', ProviderServerDetailView.as_view(), name='provider-server-detail'),
    path('provider-server/<int:p_server_id>/available-slots/', AvailableTimeSlotsView.as_view(), name='available-slots'),
    path('client/appointment/create/', api_view.create_appointment_send_otp, name='create_appointment'),
    path('client/appointment/confirm/', api_view.confirmOTP, name='confirmOTP'),

]
