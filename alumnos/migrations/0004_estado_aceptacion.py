from django.db import migrations, models


def convertir_estado(apps, schema_editor):
    Compra = apps.get_model('alumnos', 'Compra')
    Compra.objects.using(schema_editor.connection.alias).filter(estado_aceptacion='verificado').update(estado_aceptacion='aceptado')


def restaurar_estado(apps, schema_editor):
    Compra = apps.get_model('alumnos', 'Compra')
    Compra.objects.using(schema_editor.connection.alias).filter(estado_aceptacion='aceptado').update(estado_aceptacion='verificado')


class Migration(migrations.Migration):
    dependencies = [('alumnos', '0003_compra')]

    operations = [
        migrations.RenameField(model_name='compra', old_name='estado_pago', new_name='estado_aceptacion'),
        migrations.RunPython(convertir_estado, restaurar_estado),
        migrations.AlterField(
            model_name='compra', name='estado_aceptacion',
            field=models.CharField(max_length=20, default='pendiente', choices=[
                ('pendiente', 'Pendiente de revisión'), ('aceptado', 'Aceptado'), ('rechazado', 'Rechazado'),
            ]),
        ),
    ]
