from django.urls import path, include
from booket.dashboard import views
urlpatterns = [
    path('main/', views.dashboard, name='dashboard_main'),
    path('config/', views.configs, name='dashboard_config'),
]
