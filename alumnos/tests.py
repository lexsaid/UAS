import tempfile
from io import BytesIO
from unittest.mock import patch
from PIL import Image
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.files.storage import FileSystemStorage
from django.db import IntegrityError, transaction
from django.test import TestCase, override_settings, Client
from django.urls import reverse
from comedor.models import Comida
from .forms import RegistroAlumnoForm
from .models import Alumno, Compra, Carrito
from .views import registrar_alumno


def foto():
    buffer = BytesIO()
    Image.new('RGB', (8, 8), 'green').save(buffer, 'PNG')
    return SimpleUploadedFile('perfil.png', buffer.getvalue(), content_type='image/png')


class AlumnosTests(TestCase):
    def setUp(self):
        horario = patch('comedor.models.HorarioPedidos.permite_registro', return_value=True)
        horario.start()
        self.addCleanup(horario.stop)
        media = tempfile.TemporaryDirectory()
        self.addCleanup(media.cleanup)
        self.override = override_settings(MEDIA_ROOT=media.name)
        self.override.enable()
        self.addCleanup(self.override.disable)
        storage = patch.object(Compra._meta.get_field('comprobante'), 'storage', FileSystemStorage(location=media.name))
        storage.start()
        self.addCleanup(storage.stop)

    def datos(self, **cambios):
        return dict(dict(nombre='María José', apellido_paterno='Muñoz', apellido_materno='Pérez', correo='alumna@example.com', matricula='00123456', password='Arbol!Luna-92verde', confirmar_password='Arbol!Luna-92verde'), **cambios)

    def registrar(self, **cambios):
        return self.client.post(reverse('alumnos:registro'), self.datos(**cambios))

    def entrar(self):
        return self.client.post(reverse('alumnos:login'), {'correo': 'ALUMNA@example.com', 'password': self.datos()['password'], 'next': 'https://example.org'})

    def test_registro_persistente_sin_sesion(self):
        self.assertRedirects(self.registrar(foto=foto(), correo='ALUMNA@EXAMPLE.COM', nombre=' María  José '), reverse('alumnos:login'))
        alumno = Alumno.objects.get()
        self.assertEqual(alumno.nombre, 'María José')
        self.assertEqual(alumno.correo, 'alumna@example.com')
        self.assertEqual(alumno.matricula, '00123456')
        self.assertTrue(alumno.foto.storage.exists(alumno.foto.name))
        self.assertTrue(alumno.usuario.check_password(self.datos()['password']))
        self.assertFalse(alumno.usuario.is_staff)
        self.assertNotEqual(alumno.usuario.password, self.datos()['password'])
        self.assertNotIn('_auth_user_id', self.client.session)

    def test_cancelar_no_guarda(self):
        response = self.client.get(reverse('alumnos:registro'))
        self.assertContains(response, f'href="{reverse("alumnos:login")}">Cancelar</a>')
        self.client.get(reverse('alumnos:login'))
        self.assertFalse(Alumno.objects.exists())

    def test_matricula_exactamente_ocho_digitos(self):
        mensaje = 'La matrícula debe contener exactamente 8 dígitos (0–9).'
        for matricula in ('1234567', '123456789', '1234567A', '1234-678',
                          '1234 678', ' 12345678', '12345678 ', '１２３４５６７８',
                          '12345678\n'):
            with self.subTest(matricula=matricula):
                response = self.registrar(matricula=matricula)
                self.assertEqual(response.context['form'].errors['matricula'], [mensaje])
                self.assertContains(response, mensaje, count=1)
                self.assertFalse(Alumno.objects.exists())
        response = self.client.get(reverse('alumnos:registro'))
        self.assertContains(response, 'inputmode="numeric"')
        self.assertContains(response, 'pattern="[0-9]{8}"')
        self.assertContains(response, 'maxlength="8"')
        self.assertRedirects(self.registrar(matricula='00001234'), reverse('alumnos:login'))
        self.assertEqual(Alumno.objects.get().matricula, '00001234')

    def test_validaciones_no_crean_cuentas(self):
        inicial = get_user_model().objects.count()
        casos = [({'nombre': '123'}, 'nombre'), ({'nombre': '  '}, 'nombre'), ({'correo': 'mal-correo'}, 'correo'), ({'confirmar_password': 'otra'}, 'confirmar_password'), ({'password': '123', 'confirmar_password': '123'}, 'password'), ({'matricula': '../123'}, 'matricula'), ({'foto': SimpleUploadedFile('falso.png', b'not an image')}, 'foto')]
        for cambios, campo in casos:
            with self.subTest(campo=campo):
                response = self.registrar(**cambios)
                self.assertEqual(response.status_code, 200)
                self.assertIn(campo, response.context['form'].errors)
                self.assertFalse(Alumno.objects.exists())
                self.assertEqual(get_user_model().objects.count(), inicial)

    def test_limite_foto_y_campos_opcionales(self):
        archivo = foto()
        archivo.size = 5 * 1024 * 1024 + 1
        form = RegistroAlumnoForm(self.datos(), {'foto': archivo})
        self.assertFalse(form.is_valid())
        self.assertIn('foto', form.errors)
        self.assertEqual(self.registrar(apellido_materno='').status_code, 302)

    def test_duplicados_normalizados(self):
        self.registrar(matricula='00123456')
        for cambios, campo in [({'correo': 'ALUMNA@example.com', 'matricula': '00234567'}, 'correo'), ({'correo': 'otra@example.com', 'matricula': '00123456'}, 'matricula')]:
            response = self.registrar(**cambios)
            self.assertIn(campo, response.context['form'].errors)
        self.assertEqual(Alumno.objects.count(), 1)

    def test_conflicto_concurrente(self):
        with patch('alumnos.views.registrar_alumno', side_effect=IntegrityError):
            self.assertContains(self.registrar(), 'El correo o la matrícula ya se registraron.')

    def test_transaccion_revierte_cuenta(self):
        form = RegistroAlumnoForm(self.datos())
        self.assertTrue(form.is_valid())
        inicial = get_user_model().objects.count()
        with patch.object(Alumno, 'save', side_effect=IntegrityError):
            with self.assertRaises(IntegrityError):
                registrar_alumno(form)
        self.assertEqual(get_user_model().objects.count(), inicial)

    def test_constraint_correo(self):
        self.registrar()
        usuario = get_user_model().objects.create_user('otro')
        with self.assertRaises(IntegrityError), transaction.atomic():
            Alumno.objects.create(usuario=usuario, nombre='Otro', apellido_paterno='Alumno', correo='ALUMNA@EXAMPLE.COM', matricula='999')

    def test_login_y_navegacion(self):
        self.registrar()
        self.assertRedirects(self.entrar(), reverse('alumnos:inicio'))
        response = self.client.get(reverse('alumnos:inicio'))
        for texto in ('María José', reverse('alumnos:menu'), reverse('alumnos:historial')):
            self.assertContains(response, texto)
        self.assertContains(response, '<strong>3:00 <small>p. m.</small></strong>', html=True)
        for pagina in ('menu', 'historial'):
            self.assertEqual(self.client.get(reverse(f'alumnos:{pagina}')).status_code, 200)
        self.assertRedirects(self.client.get(reverse('alumnos:login')), reverse('alumnos:inicio'))

    def test_login_incorrecto_inactivo_y_staff(self):
        self.registrar()
        for correo in ('alumna@example.com', 'nadie@example.com'):
            self.assertContains(self.client.post(reverse('alumnos:login'), {'correo': correo, 'password': 'incorrecta'}), 'El correo o la contraseña no son correctos.')
        usuario = Alumno.objects.get().usuario
        for campo in ('is_active', 'is_staff'):
            usuario.is_active = campo != 'is_active'
            usuario.is_staff = campo == 'is_staff'
            usuario.save()
            self.assertContains(self.entrar(), 'El correo o la contraseña no son correctos.')
            self.assertNotIn('_auth_user_id', self.client.session)

    def test_proteccion_roles(self):
        for pagina in ('inicio', 'menu', 'historial'):
            self.assertRedirects(self.client.get(reverse(f'alumnos:{pagina}')), reverse('alumnos:login'))
        self.client.force_login(get_user_model().objects.get(username='comedor'))
        self.assertRedirects(self.client.get(reverse('alumnos:inicio')), reverse('alumnos:login'))
        self.client.logout()
        self.registrar()
        self.entrar()
        response = self.client.get(reverse('comedor:lista'))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse('comedor:login'), response.url)

    def test_menu_conectado_comedor(self):
        self.registrar()
        self.entrar()
        self.assertContains(self.client.get(reverse('alumnos:menu')), 'El menú está por llegar')
        comida = Comida.objects.create(nombre='Enchiladas', ingredientes='Tortilla\nPollo', precio='45.00', imagen=foto())
        response = self.client.get(reverse('alumnos:menu'))
        self.assertContains(response, 'Enchiladas')
        self.assertContains(response, 'Pollo')
        self.assertNotContains(response, reverse('comedor:editar', args=[comida.pk]))

    def test_logout_y_cache(self):
        self.registrar()
        self.entrar()
        self.assertIn('no-store', self.client.get(reverse('alumnos:inicio'))['Cache-Control'])
        self.assertEqual(self.client.get(reverse('alumnos:salir')).status_code, 405)
        self.assertRedirects(self.client.post(reverse('alumnos:salir')), reverse('alumnos:login'))
        self.assertNotIn('_auth_user_id', self.client.session)

    def test_csrf(self):
        client = Client(enforce_csrf_checks=True)
        for pagina in ('registro', 'login'):
            self.assertEqual(client.post(reverse(f'alumnos:{pagina}'), self.datos()).status_code, 403)

    def test_password_permite_comunes_y_similares(self):
        for password in ('password', 'alumna@example.com'):
            with self.subTest(password=password):
                form = RegistroAlumnoForm(self.datos(password=password, confirmar_password=password))
                self.assertTrue(form.is_valid(), form.errors)

    def test_password_rechaza_corta_y_solo_numeros(self):
        for password in ('Abc123!', '1234567890'):
            with self.subTest(password=password):
                form = RegistroAlumnoForm(self.datos(password=password, confirmar_password=password))
                self.assertFalse(form.is_valid())
                self.assertIn('password', form.errors)
        response = self.client.get(reverse('alumnos:registro'))
        self.assertNotContains(response, 'información personal')
        self.assertNotContains(response, 'uso común')
        self.assertContains(response, '8 caracteres')
        self.assertContains(response, 'completamente numérica')


    def preparar_carrito(self):
        self.registrar()
        self.entrar()
        return Comida.objects.create(nombre='Tacos', ingredientes='Tortilla, pollo', precio='25.50', imagen=foto())

    def test_carrito_agrega_repetidos_y_cuenta_unidades(self):
        comida = self.preparar_carrito()
        url = reverse('alumnos:agregar_carrito', args=[comida.pk])
        self.assertEqual(self.client.get(url).status_code, 405)
        self.client.post(url, {'precio': '0.01', 'alumno': '999'})
        response = self.client.post(url, HTTP_ACCEPT='application/json')
        self.assertEqual(response.json()['cantidad_carrito'], 2)
        self.assertEqual(response.json()['total'], '51.00')
        self.assertEqual(Carrito.objects.count(), 1)
        response = self.client.get(reverse('alumnos:carrito'))
        self.assertEqual(response.context['cantidad_carrito'], 2)
        self.assertContains(response, '$51.00')
        self.assertContains(self.client.get(reverse('alumnos:menu')), '2 en tu carrito')

    def test_carrito_cantidades_validas_y_limite(self):
        comida = self.preparar_carrito()
        self.client.post(reverse('alumnos:agregar_carrito', args=[comida.pk]))
        item = Carrito.objects.get()
        url = reverse('alumnos:actualizar_carrito', args=[item.pk])
        for cantidad in ('0', '-1', '100', '1.5', 'abc', ''):
            self.client.post(url, {'cantidad': cantidad})
            item.refresh_from_db()
            self.assertEqual(item.cantidad, 1)
        self.client.post(url, {'cantidad': '99'})
        response = self.client.post(reverse('alumnos:agregar_carrito', args=[comida.pk]), HTTP_ACCEPT='application/json')
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()['cantidad'], 99)
        self.client.post(url, {'cantidad': '3'})
        item.refresh_from_db()
        self.assertEqual(item.cantidad, 3)

    def test_carrito_aislado_y_persistente(self):
        comida = self.preparar_carrito()
        self.client.post(reverse('alumnos:agregar_carrito', args=[comida.pk]))
        item = Carrito.objects.get()
        self.client.post(reverse('alumnos:salir'))
        self.registrar(correo='otro@example.com', matricula='98765432')
        otro = Alumno.objects.get(correo='otro@example.com')
        self.client.force_login(otro.usuario)
        self.assertContains(self.client.get(reverse('alumnos:carrito')), 'Aún no tienes alimentos')
        for accion in ('actualizar_carrito', 'quitar_carrito'):
            self.assertEqual(self.client.post(reverse(f'alumnos:{accion}', args=[item.pk]), {'cantidad': 9}).status_code, 404)
        self.client.logout()
        self.entrar()
        self.assertEqual(self.client.get(reverse('alumnos:carrito')).context['cantidad_carrito'], 1)

    def test_carrito_precio_actual_y_comida_eliminada(self):
        comida = self.preparar_carrito()
        self.client.post(reverse('alumnos:agregar_carrito', args=[comida.pk]))
        comida.precio = '30.00'
        comida.save()
        self.assertContains(self.client.get(reverse('alumnos:carrito')), '$30.00')
        pk = comida.pk
        comida.delete()
        self.assertFalse(Carrito.objects.exists())
        self.assertEqual(self.client.post(reverse('alumnos:agregar_carrito', args=[pk])).status_code, 404)
        self.assertContains(self.client.get(reverse('alumnos:carrito')), 'Aún no tienes alimentos')

    def test_carrito_quitar_post_y_csrf(self):
        comida = self.preparar_carrito()
        url = reverse('alumnos:agregar_carrito', args=[comida.pk])
        self.client.post(url)
        item = Carrito.objects.get()
        quitar = reverse('alumnos:quitar_carrito', args=[item.pk])
        self.assertEqual(self.client.get(quitar).status_code, 405)
        client = Client(enforce_csrf_checks=True)
        client.force_login(Alumno.objects.get().usuario)
        self.assertEqual(client.post(url).status_code, 403)
        self.assertRedirects(self.client.post(quitar), reverse('alumnos:carrito'))
        self.assertFalse(Carrito.objects.exists())

    def test_carrito_requiere_alumno(self):
        comida = Comida.objects.create(nombre='Tacos', ingredientes='Pollo', precio='25.00', imagen=foto())
        self.assertRedirects(self.client.get(reverse('alumnos:carrito')), reverse('alumnos:login'))
        self.client.force_login(get_user_model().objects.get(username='comedor'))
        self.assertRedirects(self.client.post(reverse('alumnos:agregar_carrito', args=[comida.pk])), reverse('alumnos:login'))
        self.assertFalse(Carrito.objects.exists())

    def preparar_confirmacion(self):
        comida = self.preparar_carrito()
        self.client.post(reverse('alumnos:agregar_carrito', args=[comida.pk]))
        form = self.client.get(reverse('alumnos:confirmar_compra')).context['form']
        return comida, {'numero': str(form.initial['numero']), 'resumen': form.initial['resumen']}

    def test_confirmar_guarda_snapshot_comprobante_y_no_duplica(self):
        comida, datos = self.preparar_confirmacion()
        url = reverse('alumnos:confirmar_compra')
        response = self.client.post(url, {**datos, 'comprobante': foto(), 'total': '0.01'})
        compra = Compra.objects.get()
        self.assertRedirects(response, reverse('alumnos:compra_realizada', args=[compra.numero]))
        self.assertEqual(str(compra.total), '25.50')
        self.assertEqual(compra.estado_aceptacion, 'pendiente')
        self.assertTrue(compra.comprobante.storage.exists(compra.comprobante.name))
        self.assertFalse(Carrito.objects.exists())
        self.assertRedirects(self.client.post(url, {**datos, 'comprobante': foto()}), response.url)
        self.assertEqual(Compra.objects.count(), 1)
        comida.nombre = 'Otro nombre'
        comida.precio = '99.00'
        comida.save()
        self.assertContains(self.client.get(response.url), 'Tacos')
        self.assertContains(self.client.get(reverse('alumnos:historial')), compra.folio)
        self.assertEqual(self.client.get(f'/alumnos/compra/{compra.numero}/comprobante/').status_code, 404)

    def test_confirmar_fuera_del_horario_conserva_carrito(self):
        _, datos = self.preparar_confirmacion()
        with patch('comedor.models.HorarioPedidos.permite_registro', return_value=False):
            pagina = self.client.get(reverse('alumnos:confirmar_compra'))
            self.assertContains(pagina, 'data-abierto="false"')
            self.assertContains(pagina, 'regresa durante el horario de pedidos')
            self.assertRegex(
                pagina.content.decode(),
                r'<button[^>]*form="confirmar-compra"[^>]*disabled',
            )
            with patch.object(Compra._meta.get_field('comprobante').storage, 'save') as guardar:
                respuesta = self.client.post(reverse('alumnos:confirmar_compra'), {**datos, 'comprobante': foto()})
                self.assertContains(respuesta, 'El registro de pedidos está cerrado.', count=1)
                self.assertRegex(
                    respuesta.content.decode(),
                    r'<button[^>]*form="confirmar-compra"[^>]*disabled',
                )
                self.assertFalse(Compra.objects.exists())
                self.assertTrue(Carrito.objects.exists())
                guardar.assert_not_called()

    def test_confirmar_dentro_del_horario_deja_habilitar_el_boton(self):
        self.preparar_confirmacion()
        respuesta = self.client.get(reverse('alumnos:confirmar_compra'))
        self.assertContains(respuesta, 'data-abierto="true"')
        self.assertNotRegex(
            respuesta.content.decode(),
            r'<button[^>]*form="confirmar-compra"[^>]*disabled',
        )

    def test_confirmar_pdf_y_privacidad(self):
        from reportlab.pdfgen import canvas
        _, datos = self.preparar_confirmacion()
        buffer = BytesIO()
        pdf = canvas.Canvas(buffer)
        pdf.drawString(20, 20, 'Comprobante de prueba')
        pdf.save()
        archivo = SimpleUploadedFile('pago.pdf', buffer.getvalue(), content_type='application/pdf')
        self.client.post(reverse('alumnos:confirmar_compra'), {**datos, 'comprobante': archivo})
        compra = Compra.objects.get()
        # Crear otro perfil sin una sesión de alumno activa.
        self.client.logout()
        self.registrar(correo='otro@example.com', matricula='98765432')
        self.client.force_login(Alumno.objects.get(correo='otro@example.com').usuario)
        self.assertEqual(self.client.get(reverse('alumnos:compra_realizada', args=[compra.numero])).status_code, 404)
        self.assertNotContains(self.client.get(reverse('alumnos:historial')), compra.folio)

    def test_confirmar_rechaza_archivos_invalidos_y_sin_archivo(self):
        _, datos = self.preparar_confirmacion()
        for archivo in (None, SimpleUploadedFile('falso.png', b'no imagen'), SimpleUploadedFile('falso.pdf', b'no pdf'), SimpleUploadedFile('pago.html', b'<html>')):
            payload = {**datos}
            if archivo:
                payload['comprobante'] = archivo
            response = self.client.post(reverse('alumnos:confirmar_compra'), payload)
            self.assertIn('comprobante', response.context['form'].errors)
            self.assertFalse(Compra.objects.exists())
            self.assertTrue(Carrito.objects.exists())
        from .forms import ConfirmarCompraForm
        archivo = foto()
        archivo.size = 5 * 1024 * 1024 + 1
        form = ConfirmarCompraForm(datos, {'comprobante': archivo})
        self.assertFalse(form.is_valid())
        self.assertIn('comprobante', form.errors)

    def test_confirmar_cambio_precio_y_firma_manipulada(self):
        comida, datos = self.preparar_confirmacion()
        comida.precio = '50.00'
        comida.save()
        for resumen in (datos['resumen'], 'firma-falsa'):
            response = self.client.post(reverse('alumnos:confirmar_compra'), {**datos, 'resumen': resumen, 'comprobante': foto()})
            self.assertContains(response, 'Tu selección cambió')
            self.assertFalse(Compra.objects.exists())
            self.assertTrue(Carrito.objects.exists())

    def test_confirmar_fallo_no_pierde_carrito_ni_deja_archivo(self):
        _, datos = self.preparar_confirmacion()
        storage = Compra._meta.get_field('comprobante').storage
        antes = storage.listdir('')[1]
        with patch.object(Compra, 'save', side_effect=IntegrityError):
            with self.assertRaises(IntegrityError):
                self.client.post(reverse('alumnos:confirmar_compra'), {**datos, 'comprobante': foto()})
        self.assertFalse(Compra.objects.exists())
        self.assertTrue(Carrito.objects.exists())
        self.assertEqual(storage.listdir('')[1], antes)

    def test_confirmar_vacio_protegido_y_csrf(self):
        url = reverse('alumnos:confirmar_compra')
        self.assertRedirects(self.client.get(url), reverse('alumnos:login'))
        self.registrar()
        self.entrar()
        self.assertRedirects(self.client.get(url), reverse('alumnos:carrito'))
        client = Client(enforce_csrf_checks=True)
        client.force_login(Alumno.objects.get().usuario)
        self.assertEqual(client.post(url).status_code, 403)

    def test_ajustar_limites_y_borrar_sin_confirmacion(self):
        comida = self.preparar_carrito()
        self.client.post(reverse('alumnos:agregar_carrito', args=[comida.pk]))
        item = Carrito.objects.get()
        for delta, cantidad in ((-1, 1), (1, 2), (-1, 1), (5, 1)):
            self.client.post(reverse('alumnos:ajustar_carrito', args=[item.pk, delta]))
            item.refresh_from_db()
            self.assertEqual(item.cantidad, cantidad)
        item.cantidad = 99
        item.save()
        self.client.post(reverse('alumnos:ajustar_carrito', args=[item.pk, 1]))
        item.refresh_from_db()
        self.assertEqual(item.cantidad, 99)
        self.client.post(reverse('alumnos:quitar_carrito', args=[item.pk]))
        self.assertFalse(Carrito.objects.exists())

    def test_edicion_carrito_json_y_estado_vacio(self):
        comida = self.preparar_carrito()
        self.client.post(reverse('alumnos:agregar_carrito', args=[comida.pk]))
        item = Carrito.objects.get()
        pagina = self.client.get(reverse('alumnos:carrito'))
        self.assertContains(pagina, 'data-carrito-contenido', count=1)
        self.assertContains(pagina, 'Tu selección')
        self.assertContains(pagina, 'data-editar-carrito')
        for delta, cantidad, total in ((1, 2, '51.00'), (-1, 1, '25.50'), (-1, 1, '25.50')):
            response = self.client.post(reverse('alumnos:ajustar_carrito', args=[item.pk, delta]), HTTP_ACCEPT='application/json')
            self.assertEqual(response.status_code, 200)
            data = response.json()
            self.assertEqual(data['cantidad_carrito'], cantidad)
            self.assertEqual(data['total'], total)
            self.assertIn('data-editar-carrito', data['html'])
            self.assertIn('csrfmiddlewaretoken', data['html'])
            for contenido_pagina in ('<html', '<header', '<script', 'data-carrito-contenido', 'encabezado-pedido'):
                self.assertNotIn(contenido_pagina, data['html'])
            item.refresh_from_db()
            self.assertEqual(item.cantidad, cantidad)
        response = self.client.post(reverse('alumnos:quitar_carrito', args=[item.pk]), HTTP_ACCEPT='application/json')
        self.assertEqual(response.json()['cantidad_carrito'], 0)
        self.assertEqual(response.json()['total'], '0.00')
        self.assertIn('Aún no tienes alimentos', response.json()['html'])
        self.assertNotIn(reverse('alumnos:confirmar_compra'), response.json()['html'])
        self.assertFalse(Carrito.objects.exists())
        pagina = self.client.get(reverse('alumnos:carrito'))
        self.assertContains(pagina, 'Aún no tienes alimentos')
        self.assertNotContains(pagina, 'data-editar-carrito')

    def test_detalle_rechazado_y_razones_privadas(self):
        _, datos = self.preparar_confirmacion()
        self.client.post(reverse('alumnos:confirmar_compra'), {**datos, 'comprobante': foto()})
        compra = Compra.objects.get()
        detalle = reverse('alumnos:compra_realizada', args=[compra.numero])
        razones = reverse('alumnos:razones_rechazo', args=[compra.numero])
        self.assertEqual(compra.get_estado_aceptacion_display(), 'Pendiente')
        for estado, titulo in (('pendiente', 'Tu pedido está pendiente'), ('aceptado', '¡Aceptamos tu pedido!')):
            compra.estado_aceptacion = estado
            compra.save(update_fields=['estado_aceptacion'])
            response = self.client.get(detalle)
            self.assertContains(response, titulo)
            self.assertContains(response, f'detalle-{estado}')
            self.assertContains(response, 'Tacos')
            self.assertContains(response, '$25.50')
            self.assertNotContains(response, 'Estado:')
            self.assertNotContains(response, 'Ver por qué')
            self.assertEqual(self.client.get(razones).status_code, 404)
        compra.estado_aceptacion = 'rechazado'
        compra.save(update_fields=['estado_aceptacion'])
        response = self.client.get(detalle)
        self.assertContains(response, '¡Rechazamos tu pedido!')
        self.assertContains(response, razones)
        self.assertContains(response, 'Tacos')
        self.assertContains(response, '$25.50')
        self.assertNotContains(response, 'Estado:')
        self.assertNotContains(response, '¡Recibimos tu pedido!')
        response = self.client.get(razones)
        self.assertContains(response, 'Aún no hay razones disponibles')
        self.assertContains(response, detalle)
        self.client.logout()
        self.assertRedirects(self.client.get(razones), reverse('alumnos:login'))
        self.registrar(correo='otra@example.com', matricula='87654321')
        self.client.force_login(Alumno.objects.get(correo='otra@example.com').usuario)
        self.assertEqual(self.client.get(razones).status_code, 404)

class CuentaRegresivaTests(TestCase):
    def test_limites_y_cambio_de_dia(self):
        from datetime import datetime, time
        from zoneinfo import ZoneInfo
        from comedor.models import HorarioPedidos
        from alumnos.views import obtener_estado_horario
        horario = HorarioPedidos()
        casos = [
            ('2026-11-30T14:59:59', False, '00:00:00', '2026-11-30'),
            ('2026-11-30T15:00:00', True, '12:00:00', '2026-12-01'),
            ('2026-12-01T00:00:00', True, '03:00:00', '2026-12-01'),
            ('2026-12-01T02:59:59', True, '00:00:01', '2026-12-01'),
            ('2026-12-01T03:00:00', False, '00:00:00', '2026-12-01'),
        ]
        for fecha, abierto, reloj, dia in casos:
            with self.subTest(fecha=fecha):
                ahora = datetime.fromisoformat(fecha).replace(tzinfo=ZoneInfo('America/Mexico_City'))
                with patch('alumnos.views.timezone.localtime', return_value=ahora):
                    estado = obtener_estado_horario(horario)
                self.assertEqual(estado['abierto'], abierto)
                self.assertEqual(estado['reloj'], reloj)
                self.assertTrue(estado['cambio'].startswith(dia))
        horario.hora_inicio, horario.hora_fin = time(8), time(14)
        with patch('alumnos.views.timezone.localtime', return_value=datetime(2026, 11, 12, 14, tzinfo=ZoneInfo('America/Mexico_City'))):
            estado = obtener_estado_horario(horario)
        self.assertFalse(estado['abierto'])
        self.assertEqual(estado['reloj'], '00:00:00')

    def test_de_tres_a_cinco_solo_cuenta_dentro_del_horario(self):
        from datetime import datetime, time
        from zoneinfo import ZoneInfo
        from comedor.models import HorarioPedidos
        from alumnos.views import obtener_estado_horario
        horario = HorarioPedidos(hora_inicio=time(15), hora_fin=time(17))
        for fecha, abierto, reloj in (
            ('2026-11-12T14:59:59', False, '00:00:00'),
            ('2026-11-12T15:00:00', True, '02:00:00'),
            ('2026-11-12T16:00:00', True, '01:00:00'),
            ('2026-11-12T16:59:59', True, '00:00:01'),
            ('2026-11-12T17:00:00', False, '00:00:00'),
            ('2026-11-12T18:00:00', False, '00:00:00'),
            ('2026-11-13T00:00:00', False, '00:00:00'),
            ('2026-11-13T15:00:00', True, '02:00:00'),
        ):
            with self.subTest(fecha=fecha):
                ahora = datetime.fromisoformat(fecha).replace(tzinfo=ZoneInfo('America/Mexico_City'))
                with patch('alumnos.views.timezone.localtime', return_value=ahora):
                    estado = obtener_estado_horario(horario)
                self.assertEqual(estado['abierto'], abierto)
                self.assertEqual(estado['reloj'], reloj)
                self.assertEqual(horario.permite_registro(ahora.time()), abierto)

    def test_consulta_protegida_y_horario_actualizado(self):
        from comedor.models import HorarioPedidos
        url = reverse('alumnos:horario_pedidos')
        self.assertRedirects(self.client.get(url), reverse('alumnos:login'))
        usuario = get_user_model().objects.create_user('cuenta-alumno')
        Alumno.objects.create(usuario=usuario, nombre='Cuenta', apellido_paterno='Prueba', correo='cuenta@example.test', matricula='12345678')
        self.client.force_login(usuario)
        horario = HorarioPedidos.objects.create()
        respuesta = self.client.get(url)
        self.assertEqual(respuesta.status_code, 200)
        self.assertIn('no-store', respuesta['Cache-Control'])
        self.assertIn('cambio', respuesta.json())
        horario.hora_fin = '04:15'
        horario.save()
        self.assertIn('04:15', self.client.get(reverse('alumnos:inicio')).context['horario'].hora_fin.isoformat())
        usuario.is_staff = True
        usuario.save()
        self.assertRedirects(self.client.get(url), reverse('alumnos:login'), fetch_redirect_response=False)

    def test_contador_integrado_en_horario_antes_del_menu(self):
        usuario = get_user_model().objects.create_user('cuenta-inicio')
        Alumno.objects.create(usuario=usuario, nombre='Cuenta', apellido_paterno='Prueba', correo='inicio@example.test', matricula='12345678')
        self.client.force_login(usuario)
        respuesta = self.client.get(reverse('alumnos:inicio'))
        self.assertContains(respuesta, 'data-cuenta-pedidos', count=1)
        contenido = respuesta.content.decode()
        self.assertContains(respuesta, 'inicio-horario-unificado', count=1)
        self.assertLess(contenido.index('Horario de pedidos'), contenido.index('data-cuenta-pedidos'))
        self.assertLess(contenido.index('data-cuenta-pedidos'), contenido.index('Ver Menú'))
