import os

from django.contrib.auth.hashers import make_password
from django.db import migrations


def crear_usuario_comedor(apps, schema_editor):
    """Crea la cuenta única del comedor para que se pueda entrar sin configurar nada.

    Usuario y contraseña se pueden cambiar con las variables de entorno
    COMEDOR_USUARIO y COMEDOR_PASSWORD antes de correr `migrate`.
    """
    User = apps.get_model('auth', 'User')
    username = os.environ.get('COMEDOR_USUARIO', 'comedor')
    password = os.environ.get('COMEDOR_PASSWORD', 'comedor123')
    User.objects.get_or_create(
        username=username,
        defaults={
            'password': make_password(password),
            'is_staff': True,
            'first_name': 'Comedor',
        },
    )


def borrar_usuario_comedor(apps, schema_editor):
    User = apps.get_model('auth', 'User')
    username = os.environ.get('COMEDOR_USUARIO', 'comedor')
    User.objects.filter(username=username, is_staff=True).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('comedor', '0001_initial'),
        ('auth', '__latest__'),
    ]

    operations = [
        migrations.RunPython(crear_usuario_comedor, borrar_usuario_comedor),
    ]
