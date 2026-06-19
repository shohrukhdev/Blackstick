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
    path('orders/<int:pk>/partial/', views.order_detail_partial, name='order_detail_partial'),
    path('orders/<int:pk>/accept/', views.order_accept, name='order_accept'),
    path('orders/<int:pk>/decline/', views.order_decline, name='order_decline'),
    path('orders/<int:pk>/mark-paid/', views.order_mark_paid, name='order_mark_paid'),
    path('orders/<int:pk>/unmark-paid/', views.order_unmark_paid, name='order_unmark_paid'),
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

    # Clients — Task 05 + 11
    path('clients/', views.client_list, name='client_list'),
    path('clients/add/', views.client_create, name='client_create'),
    path('clients/invites/generate/', views.invite_generate, name='invite_generate'),
    path('clients/<int:pk>/', views.client_detail, name='client_detail'),
    path('clients/<int:pk>/update/', views.client_update, name='client_update'),
    path('clients/<int:client_pk>/payments/<int:pk>/update/', views.payment_update, name='payment_update'),
    path('clients/<int:client_pk>/payments/<int:pk>/delete/', views.payment_delete, name='payment_delete'),

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

    # Expenses — Task 12
    path('expenses/', views.expense_list, name='expense_list'),
    path('expenses/add/', views.expense_create, name='expense_create'),
    path('expenses/<int:pk>/delete/', views.expense_delete, name='expense_delete'),

    # Analytics — Task 13
    path('analytics/', views.analytics_dashboard, name='analytics'),
    path('analytics/chart-data/', views.analytics_chart_data, name='analytics_chart_data'),

    # Invoice — Task 14
    path('orders/<int:order_pk>/invoice/', views.invoice_download, name='invoice_download'),

    # Payment receipt
    path(
        'clients/<int:client_pk>/payments/<int:payment_pk>/receipt/',
        views.payment_receipt_download,
        name='payment_receipt_download',
    ),
]
