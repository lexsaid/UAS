from functools import wraps
from decimal import Decimal
from datetime import timedelta
from math import ceil
from uuid import UUID, uuid4

from django.contrib import messages
from django.contrib.auth import get_user_model, login, logout
from django.core import signing
from django.db import IntegrityError, transaction
from django.db.models import F
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.template.loader import render_to_string
from django.views.decorators.http import require_POST
from django.views.decorators.cache import never_cache

from comedor.models import Comida, HorarioPedidos
from .forms import CantidadCarritoForm, ConfirmarCompraForm, LoginAlumnoForm, RegistroAlumnoForm
from .models import Compra, Carrito


def registrar_alumno(form):
    """Guarda cuenta y perfil juntos; elimina la foto si falla la transacción."""
    alumno = form.save(commit=False)
    try:
        with transaction.atomic():
            alumno.usuario = get_user_model().objects.create_user(
                username=f'alumno_{uuid4().hex}', email=alumno.correo,
                password=form.cleaned_data['password'], first_name=alumno.nombre,
                last_name=f'{alumno.apellido_paterno} {alumno.apellido_materno}'.strip()[:150],
            )
            alumno.save()
    except Exception:
        if alumno.foto and alumno.foto._committed:
            alumno.foto.delete(save=False)
        raise
    return alumno


def verificar_acceso_alumno(user):
    return user.is_authenticated and user.is_active and not user.is_staff and not user.is_superuser and hasattr(user, 'alumno')


def requerir_alumno(view):
    @wraps(view)
    @never_cache
    def ejecutar_vista_protegida(request, *args, **kwargs):
        if not verificar_acceso_alumno(request.user):
            return redirect('alumnos:login')
        return view(request, *args, **kwargs)
    return ejecutar_vista_protegida


@never_cache
def iniciar_sesion(request):
    if verificar_acceso_alumno(request.user):
        return redirect('alumnos:inicio')
    form = LoginAlumnoForm(request.POST if request.method == 'POST' else None, request=request)
    if request.method == 'POST' and form.is_valid():
        login(request, form.usuario)
        return redirect('alumnos:inicio')
    return render(request, 'alumnos/login.html', {'form': form})


@never_cache
def registrar_cuenta(request):
    if verificar_acceso_alumno(request.user):
        return redirect('alumnos:inicio')
    form = RegistroAlumnoForm(request.POST if request.method == 'POST' else None, request.FILES or None)
    if request.method == 'POST' and form.is_valid():
        try:
            registrar_alumno(form)
        except IntegrityError:
            form.add_error(None, 'El correo o la matrícula ya se registraron. Revisa los datos.')
        else:
            messages.success(request, 'Tu cuenta se registró correctamente. Ya puedes iniciar sesión.')
            return redirect('alumnos:login')
    return render(request, 'alumnos/registro.html', {'form': form})


@requerir_alumno
def mostrar_inicio(request):
    horario = HorarioPedidos.objects.filter(pk=1).first() or HorarioPedidos()
    return render(request, 'alumnos/inicio.html', {'horario': horario, 'cuenta': obtener_estado_horario(horario)})


def obtener_estado_horario(horario):
    ahora = timezone.localtime()
    abierto = horario.permite_registro(ahora.time())
    limite = horario.hora_fin if abierto else horario.hora_inicio
    cambio = ahora.replace(hour=limite.hour, minute=limite.minute, second=limite.second, microsecond=0)
    if cambio <= ahora:
        cambio += timedelta(days=1)
    # La próxima apertura sirve para sincronizar, nunca como tiempo disponible para pedir.
    segundos = max(0, ceil(cambio.timestamp() - ahora.timestamp())) if abierto else 0
    horas, resto = divmod(segundos, 3600)
    minutos, segundos_resto = divmod(resto, 60)
    return {'abierto': abierto, 'servidor': ahora.isoformat(), 'cambio': cambio.isoformat(),
            'reloj': f'{horas:02}:{minutos:02}:{segundos_resto:02}'}


@requerir_alumno
def consultar_horario_pedidos(request):
    horario = HorarioPedidos.objects.filter(pk=1).first() or HorarioPedidos()
    return JsonResponse(obtener_estado_horario(horario))


@requerir_alumno
def mostrar_menu(request):
    resumen = obtener_resumen_carrito(request.user.alumno)
    cantidades = {item.comida_id: item.cantidad for item in resumen['items']}
    comidas = list(Comida.objects.all())
    for comida in comidas:
        comida.en_carrito = cantidades.get(comida.pk, 0)
    return render(request, 'alumnos/menu.html', {'comidas': comidas, **resumen})


def obtener_resumen_carrito(alumno):
    items = list(Carrito.objects.filter(alumno=alumno).select_related('comida'))
    return {'items': items, 'cantidad_carrito': sum(item.cantidad for item in items),
            'total_carrito': sum((item.subtotal for item in items), Decimal('0.00'))}


@requerir_alumno
def mostrar_carrito(request):
    resumen = obtener_resumen_carrito(request.user.alumno)
    resumen['numero_compra'] = f'UAS-{obtener_numero_carrito(request).hex[:12].upper()}'
    return render(request, 'alumnos/carrito.html', resumen)


def obtener_numero_carrito(request):
    clave = f'compra_alumno_{request.user.alumno.pk}'
    if clave not in request.session:
        request.session[clave] = str(uuid4())
    return UUID(request.session[clave])


def preparar_detalle_compra(items):
    return [{'id': item.comida_id, 'nombre': item.comida.nombre, 'cantidad': item.cantidad,
             'precio': str(item.comida.precio), 'subtotal': str(item.subtotal)} for item in items]


@requerir_alumno
def confirmar_compra(request):
    alumno = request.user.alumno
    resumen = obtener_resumen_carrito(alumno)
    numero = obtener_numero_carrito(request)
    detalle = preparar_detalle_compra(resumen['items'])
    horario = HorarioPedidos.objects.filter(pk=1).first() or HorarioPedidos()
    estado_horario = obtener_estado_horario(horario)
    form = ConfirmarCompraForm(request.POST or None, request.FILES or None, initial={
        'numero': numero, 'resumen': signing.dumps(detalle, salt=f'compra-{alumno.pk}'),
    })
    if request.method == 'POST' and form.is_valid():
        # Un reenvío del mismo formulario nunca genera otra compra.
        existente = Compra.objects.filter(numero=form.cleaned_data['numero'], alumno=alumno).first()
        if existente:
            return redirect('alumnos:compra_realizada', numero=existente.numero)
        if not horario.permite_registro():
            form.add_error(None, 'El registro de pedidos está cerrado. Consulta el horario en Inicio. Tu carrito se conserva.')
            estado_horario = obtener_estado_horario(horario)
            return render(request, 'alumnos/confirmar_compra.html', {
                **resumen, 'form': form, 'numero_compra': f'UAS-{numero.hex[:12].upper()}',
                'estado_horario': estado_horario,
            })
        try:
            mostrado = signing.loads(form.cleaned_data['resumen'], salt=f'compra-{alumno.pk}', max_age=3600)
        except signing.BadSignature:
            mostrado = None
        archivo_guardado = None
        try:
            with transaction.atomic():
                items = list(Carrito.objects.select_for_update().filter(alumno=alumno).select_related('comida'))
                if not items or mostrado != preparar_detalle_compra(items) or form.cleaned_data['numero'] != numero:
                    form.add_error(None, 'Tu selección cambió o la página venció. Vuelve al carrito y revisa el total antes de confirmar.')
                else:
                    compra = Compra(alumno=alumno, numero=numero, alimentos=mostrado,
                                    total=sum((item.subtotal for item in items), Decimal('0.00')))
                    compra.comprobante = form.cleaned_data['comprobante']
                    # Guardar primero el archivo permite limpiarlo incluso si falla el INSERT.
                    compra.comprobante.save(compra.comprobante.name, compra.comprobante.file, save=False)
                    archivo_guardado = compra.comprobante
                    compra.save()
                    Carrito.objects.filter(pk__in=[item.pk for item in items]).delete()
        except Exception:
            if archivo_guardado:
                archivo_guardado.delete(save=False)
            raise
        if not form.errors:
            request.session.pop(f'compra_alumno_{alumno.pk}', None)
            return redirect('alumnos:compra_realizada', numero=compra.numero)
    if not resumen['items']:
        return redirect('alumnos:carrito')
    return render(request, 'alumnos/confirmar_compra.html', {
        **resumen, 'form': form, 'numero_compra': f'UAS-{numero.hex[:12].upper()}',
        'estado_horario': estado_horario,
    })


@requerir_alumno
def mostrar_detalle_compra(request, numero):
    compra = get_object_or_404(Compra, numero=numero, alumno=request.user.alumno)
    return render(request, 'alumnos/detalle_pedido.html', {'compra': compra})


@requerir_alumno
def mostrar_razones_rechazo(request, numero):
    compra = get_object_or_404(Compra, numero=numero, alumno=request.user.alumno, estado_aceptacion='rechazado')
    # Pendiente del módulo de revisión del comedor: conectar aquí sus razones guardadas.
    return render(request, 'alumnos/razones_rechazo.html', {'compra': compra, 'razones': []})


@requerir_alumno
@require_POST
def agregar_al_carrito(request, pk):
    comida = get_object_or_404(Comida, pk=pk)
    with transaction.atomic():
        item, creado = Carrito.objects.get_or_create(alumno=request.user.alumno, comida=comida)
        agregado = creado or bool(Carrito.objects.filter(pk=item.pk, cantidad__lt=99).update(cantidad=F('cantidad') + 1))
        item.refresh_from_db()
    mensaje = f'{comida.nombre}: agregado al carrito.' if agregado else 'Puedes agregar hasta 99 unidades de cada comida.'
    if request.headers.get('Accept') == 'application/json':
        resumen = obtener_resumen_carrito(request.user.alumno)
        return JsonResponse({'mensaje': mensaje, 'cantidad': item.cantidad,
                             'cantidad_carrito': resumen['cantidad_carrito'],
                             'total': str(resumen['total_carrito'])}, status=200 if agregado else 400)
    (messages.success if agregado else messages.error)(request, mensaje)
    return redirect(f'{reverse("alumnos:menu")}#comida-{pk}')


@requerir_alumno
@require_POST
def actualizar_cantidad_carrito(request, pk):
    item = get_object_or_404(Carrito, pk=pk, alumno=request.user.alumno)
    form = CantidadCarritoForm(request.POST)
    if form.is_valid():
        item.cantidad = form.cleaned_data['cantidad']
        item.save(update_fields=['cantidad'])
        messages.success(request, 'Cantidad actualizada.')
    else:
        messages.error(request, 'Introduce una cantidad entera entre 1 y 99.')
    return redirect('alumnos:carrito')


@requerir_alumno
@require_POST
def ajustar_cantidad_carrito(request, pk, delta):
    item = get_object_or_404(Carrito, pk=pk, alumno=request.user.alumno)
    try:
        delta = int(delta)
    except (TypeError, ValueError):
        return redirect('alumnos:carrito')
    if delta not in (-1, 1):
        return redirect('alumnos:carrito')
    limite = {'cantidad__lt': 99} if delta == 1 else {'cantidad__gt': 1}
    Carrito.objects.filter(pk=item.pk, **limite).update(cantidad=F('cantidad') + delta)
    if request.headers.get('Accept') == 'application/json':
        return generar_respuesta_carrito(request, 'Cantidad actualizada.')
    return redirect('alumnos:carrito')


def generar_respuesta_carrito(request, mensaje):
    resumen = obtener_resumen_carrito(request.user.alumno)
    resumen['numero_compra'] = f'UAS-{obtener_numero_carrito(request).hex[:12].upper()}'
    return JsonResponse({'html': render_to_string('alumnos/carrito.html#contenido_carrito', resumen, request=request),
                         'mensaje': mensaje, 'cantidad_carrito': resumen['cantidad_carrito'],
                         'total': str(resumen['total_carrito'])})


@requerir_alumno
@require_POST
def eliminar_del_carrito(request, pk):
    item = get_object_or_404(Carrito, pk=pk, alumno=request.user.alumno)
    item.delete()
    if request.headers.get('Accept') == 'application/json':
        return generar_respuesta_carrito(request, 'Alimento eliminado del carrito.')
    messages.success(request, 'Comida retirada del carrito.')
    return redirect('alumnos:carrito')


@requerir_alumno
def mostrar_historial(request):
    return render(request, 'alumnos/historial.html', {'compras': request.user.alumno.compras.all()})


@require_POST
def cerrar_sesion(request):
    logout(request)
    return redirect('alumnos:login')
