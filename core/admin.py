# core/admin.py

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.forms import UserChangeForm, UserCreationForm
from django.utils.translation import gettext_lazy as _
from django import forms
from django.utils.html import format_html
from django.http import HttpResponse
import csv

# ✅ CAMBIO: Eliminado BecaEstudiante. Agregado Beca, BecaAsignacion
from .models import (
    Usuario, Estudiante, UsuarioEstudiantes,
    CatalogoUniversidad, CatalogoCarrera, CatalogoMateria,
    CatalogoAula, CatalogoTipoBeca, CatalogoPregunta,
    CatalogoFactorRiesgo,
    HistorialAcademico, Asistencia,
    Beca, BecaAsignacion,
    RiesgoEstudiante, Intervencion, DocumentoEstudiante,
    Encuesta, EncuestaAsignacion, EncuestaPregunta,
    EncuestaOpcion, EncuestaRespuesta
)


# ============================================
# 1. USUARIO ADMIN
# ============================================

class UsuarioCreationForm(UserCreationForm):
    """Formulario para crear usuarios con validación de duplicados"""

    class Meta:
        model = Usuario
        fields = ('username', 'email', 'first_name', 'last_name', 'rol', 'carnet', 'genero', 'telefono')

    def clean_username(self):
        username = self.cleaned_data.get('username')
        if username and Usuario.objects.filter(username=username).exists():
            raise forms.ValidationError(
                f'❌ El usuario "{username}" ya existe. Por favor, elige otro.'
            )
        return username

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if email and Usuario.objects.filter(email=email).exists():
            raise forms.ValidationError(
                f'❌ El email "{email}" ya está registrado. Por favor, usa otro.'
            )
        return email

    def clean_carnet(self):
        carnet = self.cleaned_data.get('carnet')
        if carnet and Usuario.objects.filter(carnet=carnet).exists():
            raise forms.ValidationError(
                f'❌ El carnet "{carnet}" ya está registrado. Por favor, usa otro.'
            )
        return carnet


class UsuarioChangeForm(UserChangeForm):
    class Meta:
        model = Usuario
        fields = '__all__'

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if email:
            if Usuario.objects.filter(email=email).exclude(pk=self.instance.pk).exists():
                raise forms.ValidationError(
                    f'❌ El email "{email}" ya está registrado por otro usuario.'
                )
        return email

    def clean_carnet(self):
        carnet = self.cleaned_data.get('carnet')
        if carnet:
            if Usuario.objects.filter(carnet=carnet).exclude(pk=self.instance.pk).exists():
                raise forms.ValidationError(
                    f'❌ El carnet "{carnet}" ya está registrado por otro usuario.'
                )
        return carnet


@admin.register(Usuario)
class UsuarioAdmin(UserAdmin):
    form = UsuarioChangeForm
    add_form = UsuarioCreationForm

    list_display = (
        'username',
        'carnet',
        'email',
        'first_name',
        'last_name',
        'rol',
        'genero',
        'idUniversidad',
        'es_admin_universidad',
        'is_active'
    )

    list_filter = (
        'rol',
        'genero',
        'is_active',
        'is_staff',
        'is_superuser',
        'es_admin_universidad',
        'idUniversidad'
    )

    search_fields = ('username', 'email', 'first_name', 'last_name', 'carnet')
    ordering = ('username',)
    filter_horizontal = ()

    readonly_fields = ('last_login', 'date_joined', 'created_at', 'updated_at')
    raw_id_fields = ('idUniversidad',)

    fieldsets = (
        (None, {'fields': ('username', 'password')}),
        (_('Información Personal'), {
            'fields': ('first_name', 'last_name', 'email', 'carnet', 'genero', 'fecha_nacimiento', 'telefono', 'foto')
        }),
        (_('Roles y Permisos'), {
            'fields': ('rol', 'is_active', 'is_staff', 'is_superuser', 'es_admin_universidad')
        }),
        (_('Universidad'), {
            'fields': ('idUniversidad',)
        }),
        (_('Preferencias'), {
            'fields': ('notificaciones_email', 'notificaciones_whatsapp', 'whatsapp_telefono', 'cambiar_password')
        }),
        (_('Fechas importantes'), {
            'fields': ('last_login', 'date_joined', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('username', 'email', 'carnet', 'password1', 'password2', 'first_name', 'last_name', 'rol', 'genero', 'telefono')
        }),
    )


# ============================================
# 2. ESTUDIANTE ADMIN
# ============================================

@admin.register(Estudiante)
class EstudianteAdmin(admin.ModelAdmin):
    list_display = (
        '__str__',
        'idUsuario',
        'idCarrera',
        'ano_ingreso',
        'semestre_actual',
        'estado_academico'
    )

    list_filter = (
        'estado_academico',
        'idCarrera',
        'ano_ingreso',
    )

    search_fields = (
        'idUsuario__username',
        'idUsuario__email',
        'idUsuario__carnet',
        'idUsuario__first_name',
        'idUsuario__last_name',
    )

    readonly_fields = ('created_at', 'updated_at')
    raw_id_fields = ('idUsuario', 'idCarrera')

    fieldsets = (
        ('Relaciones', {
            'fields': ('idUsuario', 'idCarrera')
        }),
        ('Datos Académicos', {
            'fields': (
                'ano_ingreso',
                'semestre_actual',
                'estado_academico'
            )
        }),
        ('Contacto Adicional', {
            'fields': (
                'direccion',
                'telefono_emergencia',
                'contacto_emergencia_nombre',
                'nacionalidad'
            )
        }),
        ('Auditoría', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    list_per_page = 20
    ordering = ('-created_at',)

    actions = ['marcar_activo', 'marcar_inactivo', 'exportar_seleccionados']

    def marcar_activo(self, request, queryset):
        actualizados = queryset.update(estado_academico='Activo')
        self.message_user(request, f'{actualizados} estudiantes marcados como Activos.')
    marcar_activo.short_description = 'Marcar como Activos'

    def marcar_inactivo(self, request, queryset):
        actualizados = queryset.update(estado_academico='Inactivo')
        self.message_user(request, f'{actualizados} estudiantes marcados como Inactivos.')
    marcar_inactivo.short_description = 'Marcar como Inactivos'

    def exportar_seleccionados(self, request, queryset):
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="estudiantes_exportados.csv"'

        writer = csv.writer(response)
        writer.writerow([
            'Carnet', 'Nombre', 'Apellidos', 'Email', 'Carrera',
            'Estado', 'Semestre', 'Año Ingreso'
        ])

        for estudiante in queryset.select_related('idUsuario', 'idCarrera'):
            writer.writerow([
                estudiante.idUsuario.carnet,
                estudiante.idUsuario.first_name,
                estudiante.idUsuario.last_name,
                estudiante.idUsuario.email,
                estudiante.idCarrera.nombre if estudiante.idCarrera else '',
                estudiante.estado_academico,
                estudiante.semestre_actual,
                estudiante.ano_ingreso,
            ])

        return response
    exportar_seleccionados.short_description = 'Exportar seleccionados a CSV'


@admin.register(UsuarioEstudiantes)
class UsuarioEstudiantesAdmin(admin.ModelAdmin):
    list_display = ('usuario', 'estudiante', 'fecha_asignacion')
    search_fields = ('usuario__username', 'usuario__carnet', 'estudiante__idUsuario__carnet')
    list_filter = ('fecha_asignacion',)
    raw_id_fields = ('usuario', 'estudiante')


# ============================================
# 3. CATÁLOGOS
# ============================================

@admin.register(CatalogoUniversidad)
class CatalogoUniversidadAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'pais', 'ciudad', 'tipo')
    search_fields = ('nombre', 'pais', 'ciudad')
    list_filter = ('tipo', 'pais')


@admin.register(CatalogoCarrera)
class CatalogoCarreraAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'codigo', 'idUniversidad', 'duracion_semestres')
    search_fields = ('nombre', 'codigo')
    list_filter = ('idUniversidad',)
    list_per_page = 20
    ordering = ('nombre',)
    raw_id_fields = ('idUniversidad',)


@admin.register(CatalogoMateria)
class CatalogoMateriaAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'codigo', 'idCarrera', 'creditos', 'semestre_curricular')
    search_fields = ('nombre', 'codigo')
    list_filter = ('idCarrera', 'semestre_curricular')
    list_per_page = 20
    ordering = ('nombre',)
    raw_id_fields = ('idCarrera',)


@admin.register(CatalogoAula)
class CatalogoAulaAdmin(admin.ModelAdmin):
    list_display = ('codigo', 'nombre', 'capacidad', 'tipo', 'estado', 'idUniversidad')
    search_fields = ('codigo', 'nombre')
    list_filter = ('tipo', 'estado', 'idUniversidad')
    raw_id_fields = ('idUniversidad',)


@admin.register(CatalogoTipoBeca)
class CatalogoTipoBecaAdmin(admin.ModelAdmin):
    list_display = ('idTipoBeca', 'nombre', 'descripcion', 'created_at')
    search_fields = ('nombre', 'descripcion')
    ordering = ('nombre',)


@admin.register(CatalogoPregunta)
class CatalogoPreguntaAdmin(admin.ModelAdmin):
    list_display = ('pregunta_corta', 'tipo_respuesta', 'categoria', 'activo')
    list_filter = ('tipo_respuesta', 'categoria', 'activo')
    search_fields = ('pregunta',)

    def pregunta_corta(self, obj):
        return obj.pregunta[:50] + "..." if len(obj.pregunta) > 50 else obj.pregunta
    pregunta_corta.short_description = 'Pregunta'


@admin.register(CatalogoFactorRiesgo)
class CatalogoFactorRiesgoAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'peso', 'activo')
    list_filter = ('activo',)
    search_fields = ('nombre', 'descripcion')


# ============================================
# 4. TRANSACCIONES
# ============================================

@admin.register(HistorialAcademico)
class HistorialAcademicoAdmin(admin.ModelAdmin):
    list_display = ('idEstudiante', 'idMateria', 'semestre', 'nota_final', 'estado_materia')
    list_filter = ('estado_materia', 'semestre')
    search_fields = ('idEstudiante__idUsuario__carnet', 'idEstudiante__idUsuario__first_name', 'idMateria__nombre')
    readonly_fields = ('created_at', 'updated_at')
    raw_id_fields = ('idEstudiante', 'idMateria')


@admin.register(Asistencia)
class AsistenciaAdmin(admin.ModelAdmin):
    list_display = ('idEstudiante', 'fecha', 'presente', 'justificacion')
    list_filter = ('presente', 'justificacion', 'fecha')
    search_fields = ('idEstudiante__idUsuario__carnet', 'idEstudiante__idUsuario__first_name')
    date_hierarchy = 'fecha'
    readonly_fields = ('created_at', 'updated_at')
    raw_id_fields = ('idEstudiante', 'idAula')


# ============================================
# 5. BECAS (Sistema unificado)
# ============================================

class BecaAsignacionInline(admin.TabularInline):
    """Inline para ver asignaciones directamente desde el admin de Beca."""
    model = BecaAsignacion
    extra = 0
    fields = [
        'idEstudiante', 'estado', 'fecha_inicio', 'fecha_fin',
        'monto_personalizado', 'porcentaje_personalizado', 'renovable'
    ]
    autocomplete_fields = ['idEstudiante']
    show_change_link = True


@admin.register(Beca)
class BecaAdmin(admin.ModelAdmin):
    list_display = (
        'codigo', 'nombre', 'tipo', 'monto',
        'porcentaje_cobertura', 'estado', 'idUniversidad',
        'cupos_disponibles', 'cupos_ocupados'
    )
    list_filter = ('tipo', 'estado', 'idUniversidad', 'created_at')
    search_fields = ('codigo', 'nombre', 'descripcion')
    readonly_fields = ('created_at', 'updated_at', 'cupos_ocupados')
    autocomplete_fields = ['idUniversidad', 'tipo']
    inlines = [BecaAsignacionInline]
    list_per_page = 20

    fieldsets = (
        ('Información Básica', {
            'fields': ('codigo', 'nombre', 'tipo', 'descripcion')
        }),
        ('Detalles Económicos', {
            'fields': ('monto', 'porcentaje_cobertura', 'duracion_meses')
        }),
        ('Vigencia y Cupos', {
            'fields': ('fecha_inicio', 'fecha_fin', 'cupos_disponibles', 'cupos_ocupados', 'estado')
        }),
        ('Requisitos', {
            'fields': ('requisitos', 'beneficios'),
            'classes': ('collapse',)
        }),
        ('Metadatos', {
            'fields': ('idUniversidad', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(BecaAsignacion)
class BecaAsignacionAdmin(admin.ModelAdmin):
    list_display = (
        'idEstudiante', 'idBeca', 'estado',
        'fecha_inicio', 'fecha_fin', 'monto_efectivo_display', 'renovable'
    )
    list_filter = ('estado', 'renovable', 'idBeca__tipo', 'fecha_asignacion')
    search_fields = (
        'idEstudiante__idUsuario__first_name',
        'idEstudiante__idUsuario__last_name',
        'idEstudiante__idUsuario__carnet',
        'idBeca__nombre',
        'idBeca__codigo',
    )
    date_hierarchy = 'fecha_asignacion'
    autocomplete_fields = ['idBeca', 'idEstudiante']
    readonly_fields = (
        'fecha_asignacion', 'created_at', 'updated_at',
        'monto_efectivo_display', 'porcentaje_efectivo_display'
    )
    list_per_page = 20

    fieldsets = (
        ('Asignación', {
            'fields': ('idBeca', 'idEstudiante', 'estado')
        }),
        ('Vigencia', {
            'fields': ('fecha_inicio', 'fecha_fin', 'renovable', 'ultima_renovacion')
        }),
        ('Montos Personalizados (opcional)', {
            'fields': (
                'monto_personalizado', 'porcentaje_personalizado',
                'monto_efectivo_display', 'porcentaje_efectivo_display'
            ),
            'classes': ('collapse',),
            'description': 'Deja vacío para usar los valores definidos en la Beca.'
        }),
        ('Observaciones', {
            'fields': ('observaciones',)
        }),
        ('Metadatos', {
            'fields': ('fecha_asignacion', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    def monto_efectivo_display(self, obj):
        """Muestra el monto efectivo con formato."""
        if obj.monto_efectivo:
            return f"${obj.monto_efectivo:,.2f}"
        return "-"
    monto_efectivo_display.short_description = 'Monto efectivo'

    def porcentaje_efectivo_display(self, obj):
        """Muestra el porcentaje efectivo."""
        if obj.porcentaje_efectivo:
            return f"{obj.porcentaje_efectivo}%"
        return "-"
    porcentaje_efectivo_display.short_description = 'Porcentaje efectivo'


# ============================================
# 6. RIESGO E INTERVENCIONES
# ============================================

@admin.register(RiesgoEstudiante)
class RiesgoEstudianteAdmin(admin.ModelAdmin):
    list_display = ('idEstudiante', 'idFactor', 'nivel', 'puntaje', 'estado')
    list_filter = ('nivel', 'estado', 'fecha_deteccion')
    search_fields = ('idEstudiante__idUsuario__carnet', 'idEstudiante__idUsuario__first_name')
    readonly_fields = ('created_at', 'updated_at')
    raw_id_fields = ('idEstudiante',)


@admin.register(Intervencion)
class IntervencionAdmin(admin.ModelAdmin):
    list_display = ('idEstudiante', 'tipo_intervencion', 'fecha_programada', 'fecha_realizada', 'efectiva')
    list_filter = ('tipo_intervencion', 'efectiva')
    search_fields = ('idEstudiante__idUsuario__carnet', 'idEstudiante__idUsuario__first_name')
    readonly_fields = ('created_at', 'updated_at')
    raw_id_fields = ('idEstudiante',)


# ============================================
# 7. DOCUMENTOS
# ============================================

@admin.register(DocumentoEstudiante)
class DocumentoEstudianteAdmin(admin.ModelAdmin):
    list_display = ('idEstudiante', 'tipo_documento', 'nombre_archivo', 'formato', 'fecha_subida')
    list_filter = ('tipo_documento', 'formato')
    search_fields = ('idEstudiante__idUsuario__carnet', 'nombre_archivo')
    readonly_fields = ('fecha_subida', 'tamano_bytes')
    raw_id_fields = ('idEstudiante',)

    fieldsets = (
        ('Información del Documento', {
            'fields': ('idEstudiante', 'tipo_documento', 'nombre_archivo', 'descripcion')
        }),
        ('Archivo', {
            'fields': ('archivo', 'ruta_archivo', 'tamano_bytes', 'formato')
        }),
        ('Auditoría', {
            'fields': ('fecha_subida',),
            'classes': ('collapse',)
        }),
    )


# ============================================
# 8. ENCUESTAS
# ============================================

@admin.register(Encuesta)
class EncuestaAdmin(admin.ModelAdmin):
    list_display = (
        'titulo',
        'creador',
        'fecha_inicio',
        'fecha_fin',
        'estado',
        'progreso_display',
        'total_asignaciones'
    )
    list_filter = ('estado', 'fecha_inicio', 'fecha_fin', 'es_obligatoria')
    search_fields = ('titulo', 'descripcion', 'creador__username')
    date_hierarchy = 'created_at'
    readonly_fields = ('created_at', 'updated_at')
    raw_id_fields = ('creador', 'idUniversidad')

    fieldsets = (
        ('Información Básica', {
            'fields': ('titulo', 'descripcion', 'creador', 'idUniversidad')
        }),
        ('Configuración', {
            'fields': ('fecha_inicio', 'fecha_fin', 'es_obligatoria', 'anonima', 'tiempo_estimado', 'estado')
        }),
        ('Auditoría', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    def progreso_display(self, obj):
        """Calcula y muestra el progreso de la encuesta."""
        total = obj.asignaciones.count()
        if total == 0:
            return "0%"
        completadas = obj.asignaciones.filter(completada=True).count()
        porcentaje = round((completadas / total) * 100)

        colors = {
            'low': '#dc3545',     # Rojo - 0-25%
            'medium': '#fd7e14',  # Naranja - 26-50%
            'high': '#ffc107',    # Amarillo - 51-75%
            'complete': '#198754' # Verde - 76-100%
        }

        if porcentaje < 25:
            color = colors['low']
        elif porcentaje < 50:
            color = colors['medium']
        elif porcentaje < 75:
            color = colors['high']
        else:
            color = colors['complete']

        return format_html(
            '<span style="color: {}; font-weight: bold;">{}%</span>',
            color, porcentaje
        )
    progreso_display.short_description = 'Progreso'

    def total_asignaciones(self, obj):
        return obj.asignaciones.count()
    total_asignaciones.short_description = 'Asignaciones'


@admin.register(EncuestaAsignacion)
class EncuestaAsignacionAdmin(admin.ModelAdmin):
    list_display = ('encuesta', 'estudiante', 'completada', 'fecha_asignacion', 'fecha_respuesta')
    list_filter = ('completada', 'fecha_asignacion')
    search_fields = ('encuesta__titulo', 'estudiante__idUsuario__first_name', 'estudiante__idUsuario__last_name')
    date_hierarchy = 'fecha_asignacion'
    readonly_fields = ('fecha_asignacion', 'fecha_respuesta')
    raw_id_fields = ('encuesta', 'estudiante')


@admin.register(EncuestaPregunta)
class EncuestaPreguntaAdmin(admin.ModelAdmin):
    list_display = ('pregunta_corta', 'encuesta', 'tipo', 'orden', 'es_obligatoria')
    list_filter = ('tipo', 'es_obligatoria', 'encuesta')
    search_fields = ('pregunta',)
    ordering = ('encuesta', 'orden')
    readonly_fields = ('created_at',)
    raw_id_fields = ('encuesta',)

    def pregunta_corta(self, obj):
        return obj.pregunta[:50] + "..." if len(obj.pregunta) > 50 else obj.pregunta
    pregunta_corta.short_description = 'Pregunta'


@admin.register(EncuestaOpcion)
class EncuestaOpcionAdmin(admin.ModelAdmin):
    list_display = ('texto', 'pregunta', 'valor', 'orden')
    list_filter = ('pregunta__tipo',)
    search_fields = ('texto', 'pregunta__pregunta')
    ordering = ('pregunta', 'orden')
    raw_id_fields = ('pregunta',)


@admin.register(EncuestaRespuesta)
class EncuestaRespuestaAdmin(admin.ModelAdmin):
    list_display = ('asignacion', 'pregunta', 'respuesta_corta', 'fecha_respuesta')
    list_filter = ('fecha_respuesta',)
    search_fields = ('asignacion__estudiante__idUsuario__first_name', 'pregunta__pregunta')
    date_hierarchy = 'fecha_respuesta'
    readonly_fields = ('fecha_respuesta',)
    raw_id_fields = ('asignacion', 'pregunta')

    def respuesta_corta(self, obj):
        if obj.respuesta_texto:
            return obj.respuesta_texto[:50] + "..." if len(obj.respuesta_texto) > 50 else obj.respuesta_texto
        elif obj.respuesta_escala is not None:
            return f"Escala: {obj.respuesta_escala}"
        elif obj.respuesta_booleana is not None:
            return "Sí" if obj.respuesta_booleana else "No"
        elif obj.opcion:
            return obj.opcion.texto
        return "-"
    respuesta_corta.short_description = 'Respuesta'