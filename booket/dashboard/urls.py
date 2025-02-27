from django.urls import path, include
from booket.dashboard import views
urlpatterns = [
    path('main/', views.dashboard, name='dashboard_main'),
]
