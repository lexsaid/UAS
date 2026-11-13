from pathlib import Path
from uuid import uuid4

from django.conf import settings
from django.core.files.storage import FileSystemStorage
from django.db import models
from django.db.models.functions import Lower


def foto_alumno(instance, filename):
    return f'alumnos/{uuid4().hex}{Path(filename).suffix.lower()}'


class Alumno(models.Model):
    usuario = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='alumno')
    nombre = models.CharField(max_length=100)
    apellido_paterno = models.CharField(max_length=100)
    apellido_materno = models.CharField(max_length=100, blank=True)
    correo = models.EmailField(max_length=254, unique=True)
    matricula = models.CharField('matrícula', max_length=30, unique=True)
    foto = models.ImageField(upload_to=foto_alumno, blank=True)
    creado = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['apellido_paterno', 'nombre']
        constraints = [
            models.UniqueConstraint(Lower('correo'), name='alumno_correo_sin_mayusculas'),
            models.UniqueConstraint(Lower('matricula'), name='alumno_matricula_sin_mayusculas'),
        ]

    @property
    def nombre_completo(self):
        return ' '.join(filter(None, [self.nombre, self.apellido_paterno, self.apellido_materno]))

    def __str__(self):
        return f'{self.matricula} · {self.nombre_completo}'


class Carrito(models.Model):
    alumno = models.ForeignKey(Alumno, on_delete=models.CASCADE, related_name='carrito')
    comida = models.ForeignKey('comedor.Comida', on_delete=models.CASCADE)
    cantidad = models.PositiveSmallIntegerField(default=1)

    class Meta:
        ordering = ['comida__nombre']
        constraints = [
            models.UniqueConstraint(fields=['alumno', 'comida'], name='carrito_alumno_comida_unica'),
            models.CheckConstraint(condition=models.Q(cantidad__gte=1, cantidad__lte=99), name='carrito_cantidad_1_99'),
        ]

    @property
    def subtotal(self):
        return self.comida.precio * self.cantidad


def almacenamiento_comprobantes():
    return FileSystemStorage(location=settings.BASE_DIR / 'comprobantes_privados')


def archivo_comprobante(instance, filename):
    return f'{uuid4().hex}{Path(filename).suffix.lower()}'


class Compra(models.Model):
    numero = models.UUIDField(default=uuid4, unique=True, editable=False)
    alumno = models.ForeignKey(Alumno, on_delete=models.PROTECT, related_name='compras')
    # Copia de nombres, precios y cantidades: el historial no cambia al editar el menú.
    alimentos = models.JSONField()
    total = models.DecimalField(max_digits=14, decimal_places=2)
    comprobante = models.FileField(upload_to=archivo_comprobante, storage=almacenamiento_comprobantes)
    creada = models.DateTimeField(auto_now_add=True)
    estado_aceptacion = models.CharField(max_length=20, default='pendiente', choices=[('pendiente', 'Pendiente'), ('aceptado', 'Aceptado'), ('rechazado', 'Rechazado')])

    class Meta:
        ordering = ['-creada']

    @property
    def folio(self):
        return f'UAS-{self.numero.hex[:12].upper()}'
