from django.urls import path

from dent.settings import views

urlpatterns = [
    path('', views.settings_window, name='settings_window'),
    path('user_list', views.staff_list, name='staff_list'),
    path('user_add', views.add_new_staff, name='add_new_staff'),
    path('user_edit', views.edit_staff, name='edit_staff'),

    path('category_list', views.category_list, name='category_list'),
    path('category_add', views.category_add, name='category_add'),

]
