import re
from datetime import time, timedelta
from decimal import Decimal

from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone


def manana():
    """Valor usado por la migración inicial; se conserva para migrar bases existentes."""
    return timezone.localdate() + timedelta(days=1)


def separar_ingredientes(texto):
    """Convierte 'Tortilla, pollo\nCrema' en ['Tortilla', 'pollo', 'Crema'].

    Separa por comas y saltos de línea, quita espacios sobrantes y repetidos.
    """
    vistos, ingredientes = set(), []
    for crudo in re.split(r'[\n,]+', texto or ''):
        ingrediente = ' '.join(crudo.split())
        if ingrediente and ingrediente.lower() not in vistos:
            vistos.add(ingrediente.lower())
            ingredientes.append(ingrediente)
    return ingredientes


class HorarioPedidos(models.Model):
    id = models.PositiveSmallIntegerField(primary_key=True, default=1, editable=False)
    hora_inicio = models.TimeField(default=time(15, 0))
    hora_fin = models.TimeField(default=time(3, 0))

    def permite_registro(self, hora=None):
        hora = hora if hora is not None else timezone.localtime().time()
        if self.hora_inicio < self.hora_fin:
            return self.hora_inicio <= hora < self.hora_fin
        return hora >= self.hora_inicio or hora < self.hora_fin

    class Meta:
        constraints = [
            models.CheckConstraint(condition=models.Q(id=1), name='horario_pedidos_unico'),
            models.CheckConstraint(condition=~models.Q(hora_inicio=models.F('hora_fin')), name='horario_pedidos_horas_distintas'),
        ]


class Comida(models.Model):
    """Una comida guardada de forma permanente en el menú del comedor."""

    nombre = models.CharField(max_length=100)
    ingredientes = models.TextField()
    precio = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))],
    )
    imagen = models.ImageField(upload_to='comidas/')

    class Meta:
        ordering = ['nombre']

    @property
    def ingredientes_lista(self):
        """Los ingredientes como lista (el campo guarda uno por línea)."""
        return separar_ingredientes(self.ingredientes)

    def __str__(self):
        return self.nombre
