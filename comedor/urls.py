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
    path('pedidos/', views.lista_pedidos, name='lista_pedidos'),
    path('pedidos/pdf/', views.generar_pdf_pedidos, name='generar_pdf_pedidos'),
    path('pedidos/<int:pk>/', views.ver_detalles_pedido, name='detalles_pedido'),
    path('pedidos/<int:pk>/comprobante/', views.ver_comprobante_pedido, name='comprobante_pedido'),
    path('pedidos/<int:pk>/aceptar/', views.aceptar_pedido, name='aceptar_pedido'),
    path('pedidos/<int:pk>/rechazar/', views.rechazar_pedido, name='rechazar_pedido'),
]
