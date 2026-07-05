from django.urls import path

from orders.client import views

app_name = 'orders_client'

urlpatterns = [
    path('login/', views.ClientLoginView.as_view(), name='client_login'),
    path('logout/', views.client_logout, name='client_logout'),
    path('pick-supplier/', views.pick_supplier, name='pick_supplier'),
    path('invite/<uuid:token>/', views.invite_register, name='invite_register'),
    path('submit/', views.submit_order, name='submit_order'),
    path('orders/', views.client_order_list, name='client_order_list'),
    path('orders/<int:pk>/', views.client_order_detail, name='client_order_detail'),
    path('orders/<int:order_pk>/invoice/', views.client_invoice_download, name='client_invoice_download'),
    path('payments/', views.client_payments, name='client_payments'),
    path('link-telegram/', views.link_telegram, name='link_telegram'),
    path('tma-auth/', views.client_tma_auth, name='client_tma_auth'),
    path('settings/', views.client_settings, name='client_settings'),
    path('', views.CatalogView.as_view(), name='client_catalog'),
]
