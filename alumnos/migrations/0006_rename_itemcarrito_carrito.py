from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ('alumnos', '0005_alter_compra_estado_aceptacion'),
    ]

    operations = [
        migrations.RenameModel(
            old_name='ItemCarrito',
            new_name='Carrito',
        ),
    ]
