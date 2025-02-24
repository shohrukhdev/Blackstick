from django.urls import path, include
from booket.client import views
urlpatterns = [
    path('<str:identifier>/', views.main_page, name='main_page'),
]
