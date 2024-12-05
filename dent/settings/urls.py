from django.urls import path

from dent.settings import views

urlpatterns = [
    path('', views.settings_window, name='settings_window'),
    path('user_list', views.staff_list, name='staff_list'),
    path('user_add', views.add_new_staff, name='add_new_staff'),
    path('user_edit', views.edit_staff, name='edit_staff'),

    path('category_list', views.category_list, name='category_list'),
    path('category_add', views.category_add, name='category_add'),
    path('category_edit', views.category_edit, name='category_edit'),

    path('service_list', views.service_list, name='service_list'),
    path('service_add', views.service_add, name='service_add'),
    path('service_edit', views.service_edit, name='service_edit'),

    path('clinic_details', views.clinic_detail, name='clinic_details'),

    # path('tooth_state_list', views.tooth_state_list, name='tooth_state_list'),
    # path('tooth_state_add', views.tooth_state_list, name='tooth_state_add'),
    # path('tooth_state_edit', views.tooth_state_list, name='tooth_state_edit'),

]
