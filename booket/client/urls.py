from django.urls import path, include
from rest_framework.routers import DefaultRouter
from booket.client import views
from booket.client.api_views import ProviderServerDetailView, AvailableTimeSlotsView, ClientViewSet

router = DefaultRouter()
router.register('clients', ClientViewSet, basename='clients')

urlpatterns = [
    path('<str:identifier>/', views.main_page, name='main_page'),
    path('client/search/', views.get_client_data, name='search_client'),
    path('provider-server/<int:p_server_id>/', ProviderServerDetailView.as_view(), name='provider-server-detail'),
    path('provider-server/<int:p_server_id>/available-slots/', AvailableTimeSlotsView.as_view(), name='available-slots'),
]
