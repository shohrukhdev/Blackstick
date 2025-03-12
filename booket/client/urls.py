from django.urls import path, include
from booket.client import views
from booket.client.api_views import ProviderServerDetailView, AvailableTimeSlotsView

urlpatterns = [
    path('<str:identifier>/', views.main_page, name='main_page'),
    path('provider-server/<int:p_server_id>/', ProviderServerDetailView.as_view(), name='provider-server-detail'),
    path('provider-server/<int:p_server_id>/available-slots/', AvailableTimeSlotsView.as_view(), name='available-slots'),
]
