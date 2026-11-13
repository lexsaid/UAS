from django.contrib import admin

from .models import Alumno


@admin.register(Alumno)
class AlumnoAdmin(admin.ModelAdmin):
    list_display = ('matricula', 'nombre', 'apellido_paterno', 'correo')
    search_fields = ('matricula', 'nombre', 'apellido_paterno', 'correo')
    readonly_fields = ('creado',)
