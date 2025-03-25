from django.urls import path, include
from rest_framework.routers import DefaultRouter
from booket.dashboard import api_views as dashboard_api_view
from booket.dashboard import views

router = DefaultRouter()
router.register('appointments', dashboard_api_view.AppointmentViewSet, basename='appointments')

urlpatterns = [
    path('main/', views.dashboard, name='dashboard_main'),
    path('config/', views.configs, name='dashboard_config'),
    path('api/', include(router.urls))
]
