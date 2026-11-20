import base64
import mimetypes
from datetime import date
from io import BytesIO
from urllib.request import urlopen

from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import user_passes_test
from django.http import FileResponse, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST
from PIL import Image, ImageDraw, ImageOps
from reportlab.lib import colors
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.utils import ImageReader, simpleSplit
from reportlab.pdfgen import canvas

from .forms import ComidaForm, HorarioPedidosForm, LoginComedorForm
from .models import Comida, HorarioPedidos

from alumnos.models import Compra

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

@comedor_requerido
def lista_pedidos(request):
    horario = HorarioPedidos.objects.filter(pk=1).first() or HorarioPedidos()
    hoy = horario.fecha_servicio_actual()
    fecha_str = request.GET.get('fecha')

    if fecha_str:
        try:
            fecha_consulta = date.fromisoformat(fecha_str)
        except ValueError:
            fecha_consulta = hoy
    else:
        fecha_consulta = hoy

    pedidos = Compra.objects.filter(fecha_servicio=fecha_consulta).select_related('alumno').order_by('-creada')
    pedidos_aceptados_count = sum(1 for pedido in pedidos if pedido.estado_aceptacion == 'aceptado')

    fechas_historial = Compra.objects.order_by().values_list(
        'fecha_servicio', flat=True,
    ).distinct().order_by('-fecha_servicio')

    return render(request, 'comedor/lista_pedidos.html', {
        'pedidos': pedidos,
        'pedidos_aceptados_count': pedidos_aceptados_count,
        'hoy': hoy,
        'fecha_consulta': fecha_consulta,
        'es_hoy': (fecha_consulta == hoy),
        'fechas_historial': fechas_historial,
    })


def _cargar_bytes_foto_alumno(foto_field):
    if not foto_field:
        return None
    try:
        with foto_field.open('rb') as archivo:
            return archivo.read()
    except Exception:
        pass
    try:
        with open(foto_field.path, 'rb') as archivo:
            return archivo.read()
    except Exception:
        pass
    try:
        url = getattr(foto_field, 'url', '') or str(foto_field)
        if url.startswith('data:image/') and ';base64,' in url:
            return base64.b64decode(url.split(';base64,', 1)[1])
        if url.startswith(('http://', 'https://')):
            with urlopen(url, timeout=5) as respuesta:
                return respuesta.read()
    except Exception:
        return None
    return None


def _preparar_avatar_circular(foto_field, diametro_px=240):
    datos = _cargar_bytes_foto_alumno(foto_field)
    if not datos:
        return None
    try:
        with Image.open(BytesIO(datos)) as img:
            img = ImageOps.exif_transpose(img).convert('RGBA')
            recorte = ImageOps.fit(
                img,
                (diametro_px, diametro_px),
                method=Image.Resampling.LANCZOS,
            )
            fondo = Image.new('RGBA', (diametro_px, diametro_px), (255, 255, 255, 255))
            mascara = Image.new('L', (diametro_px, diametro_px), 0)
            ImageDraw.Draw(mascara).ellipse((0, 0, diametro_px - 1, diametro_px - 1), fill=255)
            fondo.paste(recorte, (0, 0), mascara)
            salida = BytesIO()
            fondo.convert('RGB').save(salida, format='PNG')
            salida.seek(0)
            return ImageReader(salida)
    except Exception:
        return None


def _dibujar_avatar_por_defecto(pdf, cx, cy, radio):
    pdf.saveState()
    p = pdf.beginPath()
    p.circle(cx, cy, radio)
    pdf.clipPath(p, stroke=0, fill=0)

    pdf.setFillColor(colors.HexColor('#f1f3f5'))
    pdf.circle(cx, cy, radio, stroke=0, fill=1)

    pdf.setFillColor(colors.HexColor('#6c757d'))
    pdf.circle(cx, cy + radio * 0.25, radio * 0.36, stroke=0, fill=1)
    pdf.circle(cx, cy - radio * 0.85, radio * 0.72, stroke=0, fill=1)
    pdf.restoreState()


def _dibujar_tarjeta_pedido_pdf(pdf, pedido, x, y, ancho, alto):
    pdf.saveState()
    pdf.setStrokeColor(colors.HexColor('#17352b'))
    pdf.setFillColor(colors.white)
    pdf.setLineWidth(1.2)
    pdf.roundRect(x, y, ancho, alto, 8, stroke=1, fill=1)

    pad = 12
    left_w = 94
    div_x = x + pad + left_w

    pdf.setStrokeColor(colors.HexColor('#dce3df'))
    pdf.setLineWidth(0.8)
    pdf.line(div_x, y + pad, div_x, y + alto - pad)

    # Lado izquierdo: foto de perfil circular y nombre completo debajo
    cx = x + pad + (left_w - 6) / 2.0
    radio = 30.0
    cy = y + alto - pad - radio - 6.0

    avatar = _preparar_avatar_circular(getattr(pedido.alumno, 'foto', None))
    if avatar is not None:
        pdf.drawImage(
            avatar,
            cx - radio,
            cy - radio,
            width=radio * 2,
            height=radio * 2,
            preserveAspectRatio=True,
            mask='auto',
        )
    else:
        _dibujar_avatar_por_defecto(pdf, cx, cy, radio)

    pdf.setStrokeColor(colors.HexColor('#adb5bd'))
    pdf.setLineWidth(1.0)
    pdf.circle(cx, cy, radio, stroke=1, fill=0)

    nombre = (pedido.alumno.nombre_completo or str(pedido.alumno)).strip()
    lineas_nombre = simpleSplit(nombre, 'Helvetica-Bold', 9.5, left_w - 8)
    pdf.setFont('Helvetica-Bold', 9.5)
    pdf.setFillColor(colors.HexColor('#16231e'))
    nombre_y = cy - radio - 14.0
    for linea in lineas_nombre[:4]:
        if nombre_y < y + pad + 2:
            break
        pdf.drawCentredString(cx, nombre_y, linea)
        nombre_y -= 11.5

    # Lado derecho: fecha de realización arriba y listado de comidas debajo
    rx = div_x + 10.0
    rw = (x + ancho - pad) - rx
    ry = y + alto - pad - 12.0

    fecha_str = pedido.fecha_servicio.strftime('%d/%m/%Y')
    pdf.setFont('Helvetica-Bold', 9.5)
    pdf.setFillColor(colors.HexColor('#17352b'))
    pdf.drawString(rx, ry, f'Fecha: {fecha_str}')

    ry -= 8.0
    pdf.setStrokeColor(colors.HexColor('#cdd5d1'))
    pdf.setLineWidth(0.6)
    pdf.line(rx, ry, rx + rw, ry)

    ry -= 13.0
    pdf.setFont('Helvetica-Bold', 8.5)
    pdf.setFillColor(colors.HexColor('#4d5d56'))
    pdf.drawString(rx, ry, 'Comidas:')
    ry -= 12.0

    pdf.setFont('Helvetica', 9.0)
    pdf.setFillColor(colors.HexColor('#16231e'))

    alimentos = pedido.alimentos if isinstance(pedido.alimentos, list) else []
    total_alimentos = len(alimentos)
    for indice, item in enumerate(alimentos):
        if isinstance(item, dict):
            nombre_comida = str(item.get('nombre', '')).strip()
            cantidad = item.get('cantidad')
        else:
            nombre_comida = str(item).strip()
            cantidad = None

        if not nombre_comida:
            continue

        if cantidad not in (None, ''):
            texto_item = f'• {cantidad}x {nombre_comida}'
        else:
            texto_item = f'• {nombre_comida}'

        lineas_item = simpleSplit(texto_item, 'Helvetica', 9.0, rw)
        for i_linea, linea in enumerate(lineas_item):
            restantes = total_alimentos - indice - 1
            if ry < y + pad + 12.0 and (restantes > 0 or i_linea < len(lineas_item) - 1):
                pdf.setFont('Helvetica-Oblique', 8.0)
                pdf.drawString(rx, max(y + pad + 2.0, ry), f'... (+{restantes + 1} más)')
                pdf.restoreState()
                return
            pdf.drawString(rx if i_linea == 0 else rx + 8.0, ry, linea)
            ry -= 11.0
        ry -= 1.5

    pdf.restoreState()


def _construir_pdf_pedidos(pedidos):
    buffer = BytesIO()
    ancho_pagina, alto_pagina = LETTER
    pdf = canvas.Canvas(buffer, pagesize=LETTER)
    pdf.setTitle('Pedidos aceptados para lonches')

    columnas = 2
    filas = 3
    por_pagina = columnas * filas  # 6 tarjetas por página (2x3)

    margen_x = 28.0
    margen_sup = 28.0
    margen_inf = 28.0
    sep_x = 16.0
    sep_y = 16.0

    ancho_tarjeta = (ancho_pagina - (2 * margen_x) - sep_x) / columnas
    alto_tarjeta = (alto_pagina - margen_sup - margen_inf - (sep_y * (filas - 1))) / filas

    lista_pedidos = list(pedidos)
    for indice, pedido in enumerate(lista_pedidos):
        pos_en_pagina = indice % por_pagina
        if indice > 0 and pos_en_pagina == 0:
            pdf.showPage()

        fila = pos_en_pagina // columnas
        columna = pos_en_pagina % columnas

        x = margen_x + columna * (ancho_tarjeta + sep_x)
        y = alto_pagina - margen_sup - (fila + 1) * alto_tarjeta - (fila * sep_y)

        _dibujar_tarjeta_pedido_pdf(pdf, pedido, x, y, ancho_tarjeta, alto_tarjeta)

    pdf.save()
    buffer.seek(0)
    return buffer.getvalue()


@comedor_requerido
def generar_pdf_pedidos(request):
    horario = HorarioPedidos.objects.filter(pk=1).first() or HorarioPedidos()
    hoy = horario.fecha_servicio_actual()
    fecha_str = request.GET.get('fecha')

    if fecha_str:
        try:
            fecha_consulta = date.fromisoformat(fecha_str)
        except ValueError:
            messages.error(request, 'La fecha solicitada no es válida.')
            return redirect('comedor:lista_pedidos')
    else:
        fecha_consulta = hoy

    if fecha_consulta != hoy:
        messages.error(request, 'Solo se puede generar el PDF para los pedidos del día vigente.')
        return redirect(f"{reverse('comedor:lista_pedidos')}?fecha={fecha_consulta.isoformat()}")

    pedidos_aceptados = list(
        Compra.objects.filter(
            fecha_servicio=hoy,
            estado_aceptacion='aceptado',
        ).select_related('alumno').order_by('creada')
    )

    if not pedidos_aceptados:
        messages.warning(request, 'No hay pedidos aceptados para generar el PDF en esta fecha.')
        return redirect('comedor:lista_pedidos')

    contenido_pdf = _construir_pdf_pedidos(pedidos_aceptados)
    nombre_archivo = f'lonches_{hoy.isoformat()}.pdf'
    respuesta = HttpResponse(contenido_pdf, content_type='application/pdf')
    respuesta['Content-Disposition'] = f'inline; filename="{nombre_archivo}"'
    return respuesta

@comedor_requerido
@require_POST
def aceptar_pedido(request, pk):
    pedido = get_object_or_404(Compra, pk=pk)
    horario = HorarioPedidos.objects.filter(pk=1).first() or HorarioPedidos()
    fecha_actual = horario.fecha_servicio_actual()

    if pedido.fecha_servicio != fecha_actual:
        messages.error(request, 'Solo se pueden modificar pedidos de la tanda del día actual.')
        return redirect(f"{reverse('comedor:lista_pedidos')}?fecha={pedido.fecha_servicio.isoformat()}")

    if pedido.estado_aceptacion == 'pendiente':
        pedido.estado_aceptacion = 'aceptado'
        pedido.save()
        messages.success(request, f'Pedido {pedido.folio} aceptado.')

    return redirect('comedor:lista_pedidos')

@comedor_requerido
def ver_detalles_pedido(request, pk):
    pedido = get_object_or_404(Compra, pk=pk)
    horario = HorarioPedidos.objects.filter(pk=1).first() or HorarioPedidos()
    return render(request, 'comedor/detalles_pedido.html', {
        'pedido': pedido,
        'comprobante_pdf': pedido.comprobante.name.lower().endswith('.pdf'),
        'fecha_consulta': pedido.fecha_servicio,
        'es_hoy': pedido.fecha_servicio == horario.fecha_servicio_actual(),
    })


@comedor_requerido
def ver_comprobante_pedido(request, pk):
    pedido = get_object_or_404(Compra, pk=pk)
    tipo_contenido, _ = mimetypes.guess_type(pedido.comprobante.name)
    respuesta = FileResponse(
        pedido.comprobante.open('rb'),
        content_type=tipo_contenido or 'application/octet-stream',
    )
    respuesta['X-Content-Type-Options'] = 'nosniff'
    return respuesta


@comedor_requerido
@require_POST
def rechazar_pedido(request, pk):
    pedido = get_object_or_404(Compra, pk=pk)
    horario = HorarioPedidos.objects.filter(pk=1).first() or HorarioPedidos()
    if pedido.fecha_servicio != horario.fecha_servicio_actual():
        messages.error(request, 'Solo se pueden modificar pedidos de la tanda del día actual.')
        return redirect(f"{reverse('comedor:lista_pedidos')}?fecha={pedido.fecha_servicio.isoformat()}")

    razon = request.POST.get('razon_rechazo', '').strip()
    if not razon:
        messages.error(request, 'Debes indicar una razón para cancelar el pedido.')
        return redirect('comedor:lista_pedidos')

    if pedido.estado_aceptacion == 'pendiente':
        pedido.estado_aceptacion = 'rechazado'
        if hasattr(pedido, 'razon_rechazo'):
            pedido.razon_rechazo = razon
        pedido.save()
        messages.success(request, f'Pedido {pedido.folio} cancelado.')

    return redirect('comedor:lista_pedidos')
