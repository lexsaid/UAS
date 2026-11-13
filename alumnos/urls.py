from django.urls import path
from . import views

app_name = 'alumnos'
urlpatterns = [
    path('horario/', views.consultar_horario_pedidos, name='horario_pedidos'),
    path('', views.mostrar_inicio, name='inicio'),
    path('login/', views.iniciar_sesion, name='login'),
    path('registro/', views.registrar_cuenta, name='registro'),
    path('menu/', views.mostrar_menu, name='menu'),
    path('carrito/', views.mostrar_carrito, name='carrito'),
    path('compra/confirmar/', views.confirmar_compra, name='confirmar_compra'),
    path('compra/<uuid:numero>/', views.mostrar_detalle_compra, name='compra_realizada'),
    path('compra/<uuid:numero>/rechazo/', views.mostrar_razones_rechazo, name='razones_rechazo'),
    path('carrito/agregar/<int:pk>/', views.agregar_al_carrito, name='agregar_carrito'),
    path('carrito/<int:pk>/cantidad/', views.actualizar_cantidad_carrito, name='actualizar_carrito'),
    path('carrito/<int:pk>/ajustar/<str:delta>/', views.ajustar_cantidad_carrito, name='ajustar_carrito'),
    path('carrito/<int:pk>/quitar/', views.eliminar_del_carrito, name='quitar_carrito'),
    path('historial/', views.mostrar_historial, name='historial'),
    path('salir/', views.cerrar_sesion, name='salir'),
]
