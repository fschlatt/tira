from django.urls import path

from . import views

urlpatterns = [
    path('', views.index, name='index'),
    path('task', views.index, name='task'),
    path('tasks', views.index, name='task'),
    path('task/<str:task_id>', views.task_detail, name='task-detail'),
    path('task/<str:task_id>/user/<str:vm_id>', views.software_detail, name='software-detail'),
    path('task/<str:task_id>/dataset/<str:dataset_id>', views.dataset_detail, name='dataset-detail'),
    path('dataset', views.dataset_list, name='dataset'),
    # path('software/<str:user_id>', views.software_detail, name='software-detail'),
    path('login', views.login, name='login'),
    path('logout', views.logout, name='logout'),
]
app_name = 'tira'
