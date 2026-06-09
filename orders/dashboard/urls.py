from django.urls import path

from orders.dashboard import views

app_name = 'orders_dashboard'

urlpatterns = [
    # Auth
    path('login/', views.SupplierLoginView.as_view(), name='supplier_login'),
    path('logout/', views.supplier_logout, name='supplier_logout'),

    # Order queue — dashboard home (Task 07)
    path('', views.order_queue, name='dashboard_home'),
    path('orders/<int:pk>/', views.order_detail, name='order_detail'),
    path('orders/<int:pk>/accept/', views.order_accept, name='order_accept'),
    path('orders/<int:pk>/decline/', views.order_decline, name='order_decline'),
    path('orders/<int:order_pk>/items/<int:item_pk>/adjust/', views.order_adjust_price, name='order_adjust_price'),
    path('orders/<int:pk>/note/', views.order_update_note, name='order_update_note'),

    # Catalog — Task 04
    path('catalog/', views.catalog_management, name='catalog_home'),
    path('catalog/categories/add/', views.category_create, name='category_create'),
    path('catalog/categories/<int:pk>/edit/', views.category_update, name='category_update'),
    path('catalog/categories/<int:pk>/delete/', views.category_delete, name='category_delete'),
    path('catalog/items/add/', views.item_create, name='item_create'),
    path('catalog/items/<int:pk>/edit/', views.item_update, name='item_update'),
    path('catalog/items/<int:pk>/archive/', views.item_archive, name='item_archive'),
    path('catalog/items/<int:pk>/reactivate/', views.item_reactivate, name='item_reactivate'),

    # Clients — Task 05
    path('clients/', views.client_list, name='client_list'),
    path('clients/add/', views.client_create, name='client_create'),
    path('clients/invites/generate/', views.invite_generate, name='invite_generate'),

    # Shipments — Task 10
    path('shipments/', views.shipment_list, name='shipment_list'),
    path('shipments/new/', views.shipment_create, name='shipment_create'),
    path('shipments/<int:pk>/', views.shipment_detail, name='shipment_detail'),
    path('shipments/<int:pk>/assign/', views.shipment_assign_orders, name='shipment_assign_orders'),
    path(
        'shipments/<int:shipment_pk>/orders/<int:so_pk>/status/',
        views.shipment_order_update_status,
        name='shipment_order_update_status',
    ),

    # Stubs for future tasks
    path('expenses/', views.DashboardHomeView.as_view(), name='expense_list'),
    path('analytics/', views.DashboardHomeView.as_view(), name='analytics'),
]
