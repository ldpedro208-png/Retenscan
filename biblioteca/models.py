# biblioteca/models.py
from django.db import models
from django.conf import settings
from django.utils import timezone
from .utils.sanitizer import sanitizar_html 

# ============================================
# 1. CATÁLOGOS DE BIBLIOTECA
# ============================================

class CategoriaRecurso(models.Model):
    """Categoría temática del material."""
    TIPO_CHOICES = [
        ('academico', 'Académico'),
        ('apoyo', 'Apoyo a la Retención'),
    ]

    idCategoria = models.AutoField(primary_key=True, db_column='id')
    nombre = models.CharField(max_length=100, unique=True, db_column='nombre')
    descripcion = models.TextField(blank=True, null=True, db_column='descripcion')
    tipo = models.CharField(max_length=20, choices=TIPO_CHOICES, default='academico', db_column='tipo')
    icono = models.CharField(max_length=50, blank=True, null=True, db_column='icono',
                             help_text="Ej: fa-book, fa-heart")
    orden = models.IntegerField(default=0, db_column='orden')
    activo = models.BooleanField(default=True, db_column='activo')
    created_at = models.DateTimeField(auto_now_add=True, db_column='created_at')
    updated_at = models.DateTimeField(auto_now=True, db_column='updated_at')

    class Meta:
        db_table = 'biblioteca_categoria'
        ordering = ['orden', 'nombre']
        verbose_name = 'Categoría de Recurso'
        verbose_name_plural = 'Categorías de Recursos'

    def __str__(self):
        return self.nombre


# ============================================
# 2. RECURSO BIBLIOTECARIO
# ============================================

class RecursoBiblioteca(models.Model):
    """Recurso digital de la biblioteca."""
    TIPO_CHOICES = [
        ('libro', 'Libro'),
        ('apunte', 'Apunte'),
        ('paper', 'Paper Científico'),
        ('video', 'Video'),
        ('ejercicio', 'Ejercicios/Prácticas'),
        ('guia', 'Guía de Estudio'),
        ('presentacion', 'Presentación'),
        ('otro', 'Otro'),
    ]
    ESTADO_CHOICES = [
        ('borrador', 'Borrador'),
        ('publicado', 'Publicado'),
        ('archivado', 'Archivado'),
    ]
    NIVEL_CHOICES = [
        ('basico', 'Básico'),
        ('intermedio', 'Intermedio'),
        ('avanzado', 'Avanzado'),
    ]

    idRecurso = models.AutoField(primary_key=True, db_column='id')

    # Relaciones con RetenScan
    idUniversidad = models.ForeignKey(
        'core.CatalogoUniversidad',
        on_delete=models.CASCADE,
        db_column='universidad_id',
        related_name='recursos_biblioteca'
    )
    idMateria = models.ForeignKey(
        'core.CatalogoMateria',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        db_column='materia_id',
        related_name='recursos_biblioteca',
        help_text='Vacío si es contenido transversal'
    )
    idCategoria = models.ForeignKey(
        CategoriaRecurso,
        on_delete=models.SET_NULL,
        null=True,
        db_column='categoria_id',
        related_name='recursos'
    )
    subido_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        db_column='subido_por_id',
        related_name='recursos_subidos'
    )

    # Metadatos bibliográficos (Dublin Core simplificado)
    titulo = models.CharField(max_length=300, db_column='titulo')
    autor = models.CharField(max_length=200, blank=True, null=True, db_column='autor')
    editorial = models.CharField(max_length=150, blank=True, null=True, db_column='editorial')
    anio_publicacion = models.IntegerField(blank=True, null=True, db_column='anio_publicacion')
    isbn = models.CharField(max_length=20, blank=True, null=True, db_column='isbn')
    descripcion = models.TextField(blank=True, null=True, db_column='descripcion')
    palabras_clave = models.CharField(max_length=500, blank=True, null=True, db_column='palabras_clave',
                                      help_text="Separadas por coma")
    idioma = models.CharField(max_length=10, default='es', db_column='idioma')

    # Archivo y tipo
    tipo = models.CharField(max_length=20, choices=TIPO_CHOICES, default='apunte', db_column='tipo')
    archivo = models.FileField(upload_to='biblioteca/recursos/%Y/%m/', blank=True, null=True, db_column='archivo')
    url_externa = models.URLField(blank=True, null=True, db_column='url_externa')
    portada = models.ImageField(upload_to='biblioteca/portadas/', blank=True, null=True, db_column='portada')

    # Control
    estado = models.CharField(max_length=20, choices=ESTADO_CHOICES, default='borrador', db_column='estado')
    destacado = models.BooleanField(default=False, db_column='destacado')
    es_obligatorio = models.BooleanField(default=False, db_column='es_obligatorio')
    nivel_dificultad = models.CharField(max_length=20, choices=NIVEL_CHOICES, default='intermedio',
                                        db_column='nivel_dificultad')

    # Métricas
    total_vistas = models.IntegerField(default=0, db_column='total_vistas')
    total_descargas = models.IntegerField(default=0, db_column='total_descargas')
    promedio_calificacion = models.DecimalField(max_digits=3, decimal_places=2, default=0,
                                                 db_column='promedio_calificacion')

    created_at = models.DateTimeField(auto_now_add=True, db_column='created_at')
    updated_at = models.DateTimeField(auto_now=True, db_column='updated_at')

    class Meta:
        db_table = 'biblioteca_recurso'
        ordering = ['-created_at']
        verbose_name = 'Recurso de Biblioteca'
        verbose_name_plural = 'Recursos de Biblioteca'
        indexes = [
            models.Index(fields=['idUniversidad', 'estado']),
            models.Index(fields=['idMateria', 'estado']),
            models.Index(fields=['tipo']),
            models.Index(fields=['subido_por']),
        ]

    def __str__(self):
        return self.titulo

    @property
    def tiene_archivo(self):
        return bool(self.archivo)

    @property
    def tiene_url(self):
        return bool(self.url_externa)

    def get_extension(self):
        if self.archivo:
            import os
            return os.path.splitext(self.archivo.name)[1].lower().replace('.', '')
        return ''


# ============================================
# 3. ACCESO A RECURSO (para scoring)
# ============================================

class AccesoRecurso(models.Model):
    """
    Registra cada interacción del estudiante con un recurso.
    Esta tabla es CLAVE para el sistema de retención.
    """
    ACCION_CHOICES = [
        ('vista', 'Vista'),
        ('descarga', 'Descarga'),
        ('lectura_completa', 'Lectura Completa'),
        ('favorito', 'Marcado como Favorito'),
        ('calificacion', 'Calificación'),
    ]

    idAcceso = models.AutoField(primary_key=True, db_column='id')
    idEstudiante = models.ForeignKey(
        'core.Estudiante',
        on_delete=models.CASCADE,
        db_column='estudiante_id',
        related_name='accesos_biblioteca'
    )
    idRecurso = models.ForeignKey(
        RecursoBiblioteca,
        on_delete=models.CASCADE,
        db_column='recurso_id',
        related_name='accesos'
    )
    accion = models.CharField(max_length=20, choices=ACCION_CHOICES, db_column='accion')
    calificacion = models.PositiveSmallIntegerField(blank=True, null=True, db_column='calificacion')
    comentario = models.TextField(blank=True, null=True, db_column='comentario')
    tiempo_lectura_minutos = models.IntegerField(default=0, db_column='tiempo_lectura_minutos')
    ip_address = models.GenericIPAddressField(blank=True, null=True, db_column='ip_address')
    created_at = models.DateTimeField(auto_now_add=True, db_column='created_at')

    class Meta:
        db_table = 'biblioteca_acceso_recurso'
        ordering = ['-created_at']
        verbose_name = 'Acceso a Recurso'
        verbose_name_plural = 'Accesos a Recursos'
        indexes = [
            models.Index(fields=['idEstudiante', 'created_at']),
            models.Index(fields=['idRecurso', 'accion']),
            models.Index(fields=['accion']),
        ]

    def __str__(self):
        return f"{self.idEstudiante.nombre_completo} → {self.idRecurso.titulo} ({self.accion})"


# ============================================
# 4. MATERIAL DE APOYO (Retención)
# ============================================

class MaterialApoyo(models.Model):
    """
    Material NO académico orientado a retención emocional.
    Se sugiere automáticamente a estudiantes en riesgo.
    """
    TIPO_CHOICES = [
        ('motivacional', 'Motivacional'),
        ('habitos', 'Hábitos de Estudio'),
        ('salud_mental', 'Salud Mental'),
        ('financiero', 'Educación Financiera'),
        ('tutorias', 'Guías de Tutoría'),
        ('tiempo', 'Gestión del Tiempo'),
        ('otro', 'Otro'),
    ]

    idMaterial = models.AutoField(primary_key=True, db_column='id')
    idUniversidad = models.ForeignKey(
        'core.CatalogoUniversidad',
        on_delete=models.CASCADE,
        db_column='universidad_id',
        related_name='materiales_apoyo'
    )
    # Conexión con el sistema de riesgo
    idFactorRiesgo = models.ForeignKey(
        'core.CatalogoFactorRiesgo',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        db_column='factor_riesgo_id',
        related_name='materiales_apoyo',
        help_text='Factor de riesgo que ayuda a mitigar'
    )

    titulo = models.CharField(max_length=300, db_column='titulo')
    tipo = models.CharField(max_length=30, choices=TIPO_CHOICES, db_column='tipo')
    descripcion = models.TextField(db_column='descripcion')
    contenido = models.TextField(blank=True, null=True, db_column='contenido',
                                  help_text="Contenido HTML o texto")
    archivo = models.FileField(upload_to='biblioteca/apoyo/', blank=True, null=True, db_column='archivo')
    url_externa = models.URLField(blank=True, null=True, db_column='url_externa')

    activo = models.BooleanField(default=True, db_column='activo')
    creado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        db_column='creado_por_id'
    )
    created_at = models.DateTimeField(auto_now_add=True, db_column='created_at')
    updated_at = models.DateTimeField(auto_now=True, db_column='updated_at')

    class Meta:
        db_table = 'biblioteca_material_apoyo'
        ordering = ['tipo', 'titulo']
        verbose_name = 'Material de Apoyo'
        verbose_name_plural = 'Materiales de Apoyo'

    def __str__(self):
        return f"[{self.get_tipo_display()}] {self.titulo}"

    
    def save(self, *args, **kwargs):
        """
        Sanitiza el campo `contenido` antes de guardar.
        Defensa principal contra XSS almacenado.
        """
        if self.contenido:
            self.contenido = sanitizar_html(self.contenido)
        super().save(*args, **kwargs)

    def contenido_plano(self):
        """
        Devuelve el contenido como texto plano (para búsquedas y previews).
        """
        from .utils.sanitizer import extraer_texto_plano
        return extraer_texto_plano(self.contenido or '')
