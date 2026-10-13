# biblioteca/admin.py
from django.contrib import admin
from .models import CategoriaRecurso, RecursoBiblioteca, AccesoRecurso, MaterialApoyo


@admin.register(CategoriaRecurso)
class CategoriaRecursoAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'tipo', 'activo', 'orden')
    list_filter = ('tipo', 'activo')
    search_fields = ('nombre',)


@admin.register(RecursoBiblioteca)
class RecursoBibliotecaAdmin(admin.ModelAdmin):
    list_display = ('titulo', 'tipo', 'idMateria', 'estado', 'total_vistas', 'total_descargas')
    list_filter = ('estado', 'tipo', 'nivel_dificultad', 'es_obligatorio')
    search_fields = ('titulo', 'autor', 'palabras_clave')
    readonly_fields = ('total_vistas', 'total_descargas', 'promedio_calificacion')
    raw_id_fields = ('subido_por',)


@admin.register(AccesoRecurso)
class AccesoRecursoAdmin(admin.ModelAdmin):
    list_display = ('idEstudiante', 'idRecurso', 'accion', 'created_at')
    list_filter = ('accion',)
    search_fields = ('idEstudiante__idUsuario__first_name', 'idRecurso__titulo')
    date_hierarchy = 'created_at'


@admin.register(MaterialApoyo)
class MaterialApoyoAdmin(admin.ModelAdmin):
    list_display = ('titulo', 'tipo', 'idFactorRiesgo', 'activo')
    list_filter = ('tipo', 'activo')
    search_fields = ('titulo', 'descripcion')