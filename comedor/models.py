import re
from datetime import timedelta
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
