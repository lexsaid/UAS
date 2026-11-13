from django.urls import path

from . import views

app_name = 'comedor'

urlpatterns = [
    path('', views.inicio, name='inicio'),
    path('login/', views.login_comedor, name='login'),
    path('salir/', views.salir, name='salir'),
    path('configuracion/', views.configurar_horario_pedidos, name='configuracion'),
    path('comidas/', views.lista, name='lista'),
    path('comidas/agregar/', views.agregar, name='agregar'),
    path('comidas/<int:pk>/editar/', views.editar, name='editar'),
    path('comidas/<int:pk>/eliminar/', views.eliminar, name='eliminar'),
]
