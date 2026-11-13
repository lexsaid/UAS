import shutil
import tempfile
from decimal import Decimal
from io import BytesIO

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from PIL import Image

from .models import Comida, separar_ingredientes

MEDIA_DE_PRUEBA = tempfile.mkdtemp()


def imagen_de_prueba(nombre='plato.png'):
    buffer = BytesIO()
    Image.new('RGB', (4, 4), 'red').save(buffer, 'PNG')
    return SimpleUploadedFile(nombre, buffer.getvalue(), content_type='image/png')


def crear_comida(nombre='Tacos dorados', precio='45.00'):
    return Comida.objects.create(
        nombre=nombre,
        ingredientes='Tortilla, papa, lechuga',
        precio=Decimal(precio),
        imagen=imagen_de_prueba(),
    )


@override_settings(MEDIA_ROOT=MEDIA_DE_PRUEBA)
class ComedorTests(TestCase):
    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(MEDIA_DE_PRUEBA, ignore_errors=True)

    def setUp(self):
        self.comedor = User.objects.create_user('encargado', password='clave-segura-1', is_staff=True)
        self.cliente = User.objects.create_user('alumno', password='clave-segura-2')

    def entrar(self):
        self.client.force_login(self.comedor)

    # ---------- usuario precreado y login ----------

    def test_migracion_crea_el_usuario_del_comedor(self):
        usuario = User.objects.get(username='comedor')
        self.assertTrue(usuario.is_staff)
        self.assertTrue(usuario.check_password('comedor123'))

    def test_login_del_comedor_entra_al_inicio(self):
        respuesta = self.client.post(reverse('comedor:login'), {
            'username': 'encargado', 'password': 'clave-segura-1',
        })
        self.assertRedirects(respuesta, reverse('comedor:inicio'))

    def test_login_rechaza_a_un_cliente(self):
        respuesta = self.client.post(reverse('comedor:login'), {
            'username': 'alumno', 'password': 'clave-segura-2',
        })
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, 'no tiene acceso al comedor')
        self.assertNotIn('_auth_user_id', self.client.session)

    def test_login_con_contrasena_incorrecta_muestra_error(self):
        respuesta = self.client.post(reverse('comedor:login'), {
            'username': 'encargado', 'password': 'mala',
        })
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, 'El nombre o la contraseña no son correctos.')

    def test_login_ignora_next_hacia_otro_sitio(self):
        respuesta = self.client.post(reverse('comedor:login'), {
            'username': 'encargado', 'password': 'clave-segura-1',
            'next': 'https://sitio-malo.example/',
        })
        self.assertRedirects(respuesta, reverse('comedor:inicio'))

    def test_salir_cierra_la_sesion(self):
        self.entrar()
        respuesta = self.client.post(reverse('comedor:salir'))
        self.assertRedirects(respuesta, reverse('comedor:login'))
        self.assertNotIn('_auth_user_id', self.client.session)

    # ---------- protección de vistas ----------

    def test_las_vistas_piden_login(self):
        comida = crear_comida()
        urls = [
            reverse('comedor:inicio'),
            reverse('comedor:lista'),
            reverse('comedor:agregar'),
            reverse('comedor:editar', args=[comida.pk]),
        ]
        for url in urls:
            with self.subTest(url=url):
                respuesta = self.client.get(url)
                self.assertRedirects(
                    respuesta, f"{reverse('comedor:login')}?next={url}",
                )

    def test_un_cliente_con_sesion_no_entra_al_comedor(self):
        self.client.force_login(self.cliente)
        respuesta = self.client.get(reverse('comedor:lista'))
        self.assertEqual(respuesta.status_code, 302)
        self.assertIn(reverse('comedor:login'), respuesta['Location'])

    def test_eliminar_solo_acepta_post(self):
        comida = crear_comida()
        self.entrar()
        respuesta = self.client.get(reverse('comedor:eliminar', args=[comida.pk]))
        self.assertEqual(respuesta.status_code, 405)
        self.assertTrue(Comida.objects.filter(pk=comida.pk).exists())

    # ---------- menú ----------

    def test_inicio_cuenta_todas_las_comidas_guardadas(self):
        crear_comida('Enchiladas')
        crear_comida('Pozole')
        self.entrar()
        respuesta = self.client.get(reverse('comedor:inicio'))
        self.assertEqual(respuesta.context['total_comidas'], 2)

    def test_lista_muestra_todas_las_comidas_sin_importar_fecha_de_consulta(self):
        crear_comida('Enchiladas')
        crear_comida('Pozole')
        self.entrar()

        respuesta = self.client.get(reverse('comedor:lista'), {'fecha': '2050-01-01'})
        self.assertContains(respuesta, 'Enchiladas')
        self.assertContains(respuesta, 'Pozole')

    def test_lista_vacia_invita_a_agregar(self):
        self.entrar()
        respuesta = self.client.get(reverse('comedor:lista'))
        self.assertContains(respuesta, 'Todavía no hay comidas guardadas en el menú.')

    def test_agregar_comida_con_foto(self):
        self.entrar()
        respuesta = self.client.post(reverse('comedor:agregar'), {
            'nombre': 'Tacos dorados',
            'ingredientes': 'Tortilla, papa, lechuga',
            'precio': '45.50',
            'imagen': imagen_de_prueba(),
        })
        self.assertRedirects(respuesta, reverse('comedor:lista'))
        comida = Comida.objects.get()
        self.assertEqual(comida.nombre, 'Tacos dorados')
        self.assertEqual(comida.precio, Decimal('45.50'))
        self.assertTrue(comida.imagen.name.startswith('comidas/'))

    def test_agregar_rechaza_precio_cero_y_falta_de_foto(self):
        self.entrar()
        respuesta = self.client.post(reverse('comedor:agregar'), {
            'nombre': 'Sopa', 'ingredientes': 'Fideo', 'precio': '0',
        })
        self.assertEqual(respuesta.status_code, 200)
        self.assertIn('precio', respuesta.context['form'].errors)
        self.assertIn('imagen', respuesta.context['form'].errors)
        self.assertEqual(Comida.objects.count(), 0)

    def test_formulario_no_pide_un_dia_para_agregar_comida(self):
        self.entrar()
        respuesta = self.client.get(reverse('comedor:agregar'))
        self.assertNotIn('fecha', respuesta.context['form'].fields)

    def test_editar_comida_sin_cambiar_la_foto(self):
        comida = crear_comida()
        foto = comida.imagen.name
        self.entrar()
        respuesta = self.client.post(reverse('comedor:editar', args=[comida.pk]), {
            'nombre': 'Tacos de papa',
            'ingredientes': comida.ingredientes,
            'precio': '50.00',
        })
        self.assertEqual(respuesta.status_code, 302)
        comida.refresh_from_db()
        self.assertEqual(comida.nombre, 'Tacos de papa')
        self.assertEqual(comida.precio, Decimal('50.00'))
        self.assertEqual(comida.imagen.name, foto)

    def test_eliminar_borra_la_comida_y_su_foto(self):
        comida = crear_comida()
        ruta = comida.imagen.path
        self.entrar()
        respuesta = self.client.post(reverse('comedor:eliminar', args=[comida.pk]))
        self.assertEqual(respuesta.status_code, 302)
        self.assertFalse(Comida.objects.filter(pk=comida.pk).exists())
        with self.assertRaises(FileNotFoundError):
            open(ruta, 'rb')

    # ---------- ingredientes uno por uno ----------

    def datos_de_comida(self, **cambios):
        datos = {
            'nombre': 'Tacos dorados',
            'ingredientes': 'Tortilla\nPapa',
            'precio': '45.00',
            'imagen': imagen_de_prueba(),
        }
        datos.update(cambios)
        return datos

    def test_separar_ingredientes_limpia_y_quita_repetidos(self):
        self.assertEqual(
            separar_ingredientes('Tortilla,  pollo\n\nCrema , tortilla ,, '),
            ['Tortilla', 'pollo', 'Crema'],
        )
        self.assertEqual(separar_ingredientes(''), [])
        self.assertEqual(separar_ingredientes(None), [])

    def test_ingredientes_lista_de_la_comida(self):
        comida = crear_comida()
        self.assertEqual(comida.ingredientes_lista, ['Tortilla', 'papa', 'lechuga'])

    def test_agregar_guarda_los_ingredientes_uno_por_linea(self):
        self.entrar()
        self.client.post(reverse('comedor:agregar'), self.datos_de_comida(
            ingredientes='Tortilla, pollo\n  Crema  \ntortilla',
        ))
        self.assertEqual(Comida.objects.get().ingredientes, 'Tortilla\npollo\nCrema')

    def test_agregar_exige_al_menos_un_ingrediente(self):
        self.entrar()
        for vacio in ['', ' , \n , ']:
            with self.subTest(ingredientes=vacio):
                respuesta = self.client.post(
                    reverse('comedor:agregar'), self.datos_de_comida(ingredientes=vacio),
                )
                self.assertEqual(respuesta.status_code, 200)
                self.assertEqual(
                    respuesta.context['form'].errors['ingredientes'],
                    ['Agrega al menos un ingrediente.'],
                )
        self.assertEqual(Comida.objects.count(), 0)

    def test_agregar_rechaza_ingredientes_demasiado_largos_o_muchos(self):
        self.entrar()
        largo = self.client.post(
            reverse('comedor:agregar'), self.datos_de_comida(ingredientes='a' * 61),
        )
        self.assertIn('ingredientes', largo.context['form'].errors)

        muchos = self.client.post(
            reverse('comedor:agregar'),
            self.datos_de_comida(ingredientes='\n'.join(f'ingrediente {i}' for i in range(31))),
        )
        self.assertIn('ingredientes', muchos.context['form'].errors)

    def test_lista_muestra_los_ingredientes_como_etiquetas(self):
        crear_comida()
        self.entrar()
        respuesta = self.client.get(reverse('comedor:lista'))
        self.assertContains(respuesta, '<li class="chip">Tortilla</li>', html=True)

    def test_lista_resume_cuando_hay_mas_de_cinco_ingredientes(self):
        comida = crear_comida()
        comida.ingredientes = '\n'.join(f'ing{i}' for i in range(8))
        comida.save()
        self.entrar()
        respuesta = self.client.get(reverse('comedor:lista'))
        self.assertContains(respuesta, '+3 más')
        self.assertNotContains(respuesta, 'ing5')

    def test_el_formulario_carga_los_ingredientes_al_editar(self):
        comida = crear_comida()
        self.entrar()
        respuesta = self.client.get(reverse('comedor:editar', args=[comida.pk]))
        self.assertContains(respuesta, 'Tortilla, papa, lechuga')

    def test_lista_no_muestra_selector_de_dia(self):
        self.entrar()
        respuesta = self.client.get(reverse('comedor:lista'))
        self.assertNotContains(respuesta, 'data-fecha-auto')
        self.assertNotContains(respuesta, 'Día anterior')

class ConfiguracionHorarioTests(TestCase):
    def setUp(self):
        from .models import HorarioPedidos
        self.modelo = HorarioPedidos
        self.url = reverse('comedor:configuracion')
        self.encargado = User.objects.create_user('horario-encargado', is_staff=True)
        self.alumno = User.objects.create_user('horario-alumno')

    def test_acceso_solo_comedor_y_csrf(self):
        from django.test import Client
        for usuario in (None, self.alumno):
            if usuario:
                self.client.force_login(usuario)
            for metodo in (self.client.get, self.client.post):
                self.assertEqual(metodo(self.url, {'hora_inicio': '16:00', 'hora_fin': '04:00'}).status_code, 302)
            self.assertFalse(self.modelo.objects.exists())
        cliente = Client(enforce_csrf_checks=True)
        cliente.force_login(self.encargado)
        self.assertEqual(cliente.post(self.url, {'hora_inicio': '16:00', 'hora_fin': '04:00'}).status_code, 403)

    def test_valores_iniciales_y_enlace_solo_en_menu(self):
        self.client.force_login(self.encargado)
        respuesta = self.client.get(self.url)
        self.assertContains(respuesta, 'value="15:00"')
        self.assertContains(respuesta, 'value="03:00"')
        self.assertFalse(self.modelo.objects.exists())
        self.assertContains(self.client.get(reverse('comedor:inicio')), 'href="' + self.url + '"', count=1)

    def test_guardar_actualizar_y_mostrar_en_alumnos(self):
        from datetime import time
        from alumnos.models import Alumno
        Alumno.objects.create(usuario=self.alumno, nombre='Vista', apellido_paterno='Horario', correo='horario@example.test', matricula='12345678')
        self.client.force_login(self.encargado)
        for inicio, fin in (('16:30', '02:45'), ('08:00', '14:00')):
            self.assertRedirects(self.client.post(self.url, {'hora_inicio': inicio, 'hora_fin': fin}), self.url)
            self.assertEqual(self.modelo.objects.count(), 1)
            horario = self.modelo.objects.get()
            self.assertEqual(horario.hora_inicio, time.fromisoformat(inicio))
            self.assertEqual(horario.hora_fin, time.fromisoformat(fin))
            self.client.force_login(self.alumno)
            respuesta = self.client.get(reverse('alumnos:inicio'))
            self.assertEqual(respuesta.context['horario'].hora_inicio, horario.hora_inicio)
            self.assertContains(respuesta, 'Del día siguiente' if fin < inicio else 'Del mismo día')
            self.client.force_login(self.encargado)

    def test_errores_no_modifican_horario(self):
        from datetime import time
        self.modelo.objects.create()
        self.client.force_login(self.encargado)
        for inicio, fin in (('', '03:00'), ('25:00', '03:00'), ('15:00', ''), ('15:00', '15:00'), ('15:00', 'abc')):
            respuesta = self.client.post(self.url, {'hora_inicio': inicio, 'hora_fin': fin})
            self.assertEqual(respuesta.status_code, 200)
            self.assertTrue(respuesta.context['form'].errors)
            self.assertEqual(self.modelo.objects.get().hora_inicio, time(15))
            self.assertEqual(self.modelo.objects.get().hora_fin, time(3))

    def test_limites_horario_diurno_y_cruce_medianoche(self):
        from datetime import time, datetime
        from unittest.mock import patch
        horario = self.modelo(hora_inicio=time(15), hora_fin=time(3))
        for hora, esperado in ((time(14, 59), False), (time(15), True), (time(23, 59), True), (time(0), True), (time(2, 59), True), (time(3), False)):
            with self.subTest(hora=hora):
                self.assertEqual(horario.permite_registro(hora), esperado)
        horario.hora_inicio, horario.hora_fin = time(8), time(14)
        for hora, esperado in ((time(7, 59), False), (time(8), True), (time(13, 59), True), (time(14), False), (time(0), False)):
            with self.subTest(hora=hora):
                self.assertEqual(horario.permite_registro(hora), esperado)
        with patch('comedor.models.timezone.localtime', return_value=datetime(2026, 11, 12, 9)):
            self.assertTrue(horario.permite_registro())
