from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import user_passes_test
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from .forms import ComidaForm, HorarioPedidosForm, LoginComedorForm
from .models import Comida, HorarioPedidos


def es_comedor(user):
    return user.is_authenticated and user.is_staff


# Todas las vistas del comedor (menos el login) pasan por aquí.
comedor_requerido = user_passes_test(es_comedor, login_url='comedor:login')


def _url_lista():
    return reverse('comedor:lista')


def login_comedor(request):
    if es_comedor(request.user):
        return redirect('comedor:inicio')

    form = LoginComedorForm(request, data=request.POST or None)
    if request.method == 'POST' and form.is_valid():
        login(request, form.get_user())
        destino = request.POST.get('next', '')
        if url_has_allowed_host_and_scheme(destino, allowed_hosts={request.get_host()}):
            return redirect(destino)
        return redirect('comedor:inicio')

    return render(request, 'comedor/login.html', {
        'form': form,
        'next': request.GET.get('next', ''),
    })


@require_POST
def salir(request):
    logout(request)
    return redirect('comedor:login')


@comedor_requerido
def inicio(request):
    return render(request, 'comedor/inicio.html', {
        'total_comidas': Comida.objects.count(),
    })


@comedor_requerido
def configurar_horario_pedidos(request):
    horario = HorarioPedidos.objects.filter(pk=1).first() or HorarioPedidos()
    form = HorarioPedidosForm(request.POST if request.method == 'POST' else None, instance=horario)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Horario de pedidos guardado.')
        return redirect('comedor:configuracion')
    return render(request, 'comedor/configuracion.html', {'form': form})


@comedor_requerido
def lista(request):
    return render(request, 'comedor/lista.html', {
        'comidas': Comida.objects.all(),
    })


@comedor_requerido
def agregar(request):
    if request.method == 'POST':
        form = ComidaForm(request.POST, request.FILES)
        if form.is_valid():
            form.save()
            messages.success(request, 'Comida guardada.')
            return redirect(_url_lista())
    else:
        form = ComidaForm()

    return render(request, 'comedor/form.html', {
        'form': form,
        'titulo': 'Agregar comida',
        'volver': _url_lista(),
    })


@comedor_requerido
def editar(request, pk):
    comida = get_object_or_404(Comida, pk=pk)
    if request.method == 'POST':
        form = ComidaForm(request.POST, request.FILES, instance=comida)
        if form.is_valid():
            form.save()
            messages.success(request, 'Comida guardada.')
            return redirect(_url_lista())
    else:
        form = ComidaForm(instance=comida)

    return render(request, 'comedor/form.html', {
        'form': form,
        'comida': comida,
        'titulo': 'Editar comida',
        'volver': _url_lista(),
    })


@comedor_requerido
@require_POST
def eliminar(request, pk):
    comida = get_object_or_404(Comida, pk=pk)
    comida.imagen.delete(save=False)  # borra también la foto del disco
    comida.delete()
    messages.success(request, 'Comida eliminada.')
    return redirect(_url_lista())
