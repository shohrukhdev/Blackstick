from django.urls import path

from orders.client import views

app_name = 'orders_client'

urlpatterns = [
    path('login/', views.ClientLoginView.as_view(), name='client_login'),
    path('logout/', views.client_logout, name='client_logout'),
    path('invite/<uuid:token>/', views.invite_register, name='invite_register'),
    path('submit/', views.submit_order, name='submit_order'),
    path('', views.CatalogView.as_view(), name='client_catalog'),
]
