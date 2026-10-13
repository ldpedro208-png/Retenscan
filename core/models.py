# core/models.py

from django.db import models
from django.contrib.auth.models import AbstractUser
from django.utils import timezone
from django.core.validators import MinValueValidator, MaxValueValidator
from django.conf import settings
from django.db.models import Q


# ============================================
# 1. CATÁLOGOS (Tablas Maestras)
# ============================================

class CatalogoUniversidad(models.Model):
    TIPO_CHOICES = [
        ('Publica', 'Pública'),
        ('Privada', 'Privada'),
        ('Mixta', 'Mixta'),
    ]
    idUniversidad = models.AutoField(primary_key=True, db_column='id')
    nombre = models.CharField(max_length=150, unique=True, db_column='nombre')
    pais = models.CharField(max_length=100, blank=True, null=True, db_column='pais')
    ciudad = models.CharField(max_length=100, blank=True, null=True, db_column='ciudad')
    tipo = models.CharField(max_length=20, choices=TIPO_CHOICES, default='Privada', db_column='tipo')
    created_at = models.DateTimeField(auto_now_add=True, db_column='created_at')
    updated_at = models.DateTimeField(auto_now=True, db_column='updated_at')

    def __str__(self):
        return self.nombre

    class Meta:
        db_table = 'catalogo_universidad'


class CatalogoCarrera(models.Model):
    idCarrera = models.AutoField(primary_key=True, db_column='id')
    idUniversidad = models.ForeignKey(
        CatalogoUniversidad,
        on_delete=models.CASCADE,
        db_column='universidad_id',
        related_name='carreras_catalogo'
    )
    nombre = models.CharField(max_length=150, db_column='nombre')
    codigo = models.CharField(max_length=20, unique=True, blank=True, null=True, db_column='codigo')
    descripcion = models.TextField(blank=True, null=True, db_column='descripcion')
    duracion = models.IntegerField(default=4, db_column='duracion', help_text='Duración en años')
    duracion_semestres = models.IntegerField(default=10, db_column='duracion_semestres')
    created_at = models.DateTimeField(auto_now_add=True, db_column='created_at')
    updated_at = models.DateTimeField(auto_now=True, db_column='updated_at')

    def __str__(self):
        return f"{self.nombre} ({self.idUniversidad.nombre})"

    class Meta:
        db_table = 'catalogo_carrera'
        unique_together = ['idUniversidad', 'nombre']


class CatalogoMateria(models.Model):
    idMateria = models.AutoField(primary_key=True, db_column='id')
    idCarrera = models.ForeignKey(
        CatalogoCarrera,
        on_delete=models.CASCADE,
        db_column='carrera_id',
        related_name='materias_catalogo'
    )
    nombre = models.CharField(max_length=150, db_column='nombre')
    codigo = models.CharField(max_length=20, unique=True, blank=True, null=True, db_column='codigo')
    creditos = models.IntegerField(default=3, db_column='creditos')
    semestre_curricular = models.IntegerField(blank=True, null=True, db_column='semestre_curricular')
    created_at = models.DateTimeField(auto_now_add=True, db_column='created_at')
    updated_at = models.DateTimeField(auto_now=True, db_column='updated_at')

    def __str__(self):
        return self.nombre

    class Meta:
        db_table = 'catalogo_materia'


class CatalogoAula(models.Model):
    TIPO_CHOICES = [
        ('Teoria', 'Teoría'),
        ('Laboratorio', 'Laboratorio'),
        ('Taller', 'Taller'),
        ('Virtual', 'Virtual'),
    ]
    ESTADO_CHOICES = [
        ('Disponible', 'Disponible'),
        ('Ocupada', 'Ocupada'),
        ('Mantenimiento', 'Mantenimiento'),
        ('Inactiva', 'Inactiva'),
    ]
    idAula = models.AutoField(primary_key=True, db_column='id')
    codigo = models.CharField(max_length=20, unique=True, db_column='codigo')
    nombre = models.CharField(max_length=100, db_column='nombre')
    capacidad = models.IntegerField(default=30, db_column='capacidad')
    tipo = models.CharField(max_length=20, choices=TIPO_CHOICES, default='Teoria', db_column='tipo')
    ubicacion = models.CharField(max_length=200, blank=True, null=True, db_column='ubicacion')
    tiene_proyector = models.BooleanField(default=False, db_column='tiene_proyector')
    tiene_pizarra = models.BooleanField(default=True, db_column='tiene_pizarra')
    tiene_aire_acondicionado = models.BooleanField(default=False, db_column='tiene_aire_acondicionado')
    estado = models.CharField(max_length=20, choices=ESTADO_CHOICES, default='Disponible', db_column='estado')
    idUniversidad = models.ForeignKey(
        CatalogoUniversidad,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        db_column='universidad_id',
        related_name='aulas_catalogo'
    )
    created_at = models.DateTimeField(auto_now_add=True, db_column='created_at')
    updated_at = models.DateTimeField(auto_now=True, db_column='updated_at')

    def __str__(self):
        return f"{self.codigo} - {self.nombre}"

    class Meta:
        db_table = 'catalogo_aula'


class CatalogoTipoBeca(models.Model):
    idTipoBeca = models.AutoField(primary_key=True, db_column='id')
    nombre = models.CharField(max_length=100, unique=True, db_column='nombre')
    descripcion = models.TextField(blank=True, null=True, db_column='descripcion')
    created_at = models.DateTimeField(auto_now_add=True, db_column='created_at')

    def __str__(self):
        return self.nombre

    class Meta:
        db_table = 'catalogo_tipobeca'
        verbose_name = 'Tipo de Beca'
        verbose_name_plural = 'Tipos de Beca'
        ordering = ['nombre']


class CatalogoPregunta(models.Model):
    TIPO_RESPUESTA_CHOICES = [
        ('texto', 'Texto Libre'),
        ('escala', 'Escala (1-5)'),
        ('si_no', 'Sí/No'),
        ('opcion_unica', 'Opción Única'),
        ('opcion_multiple', 'Opción Múltiple'),
    ]
    CATEGORIA_CHOICES = [
        ('Academico', 'Académico'),
        ('Financiero', 'Financiero'),
        ('Emocional', 'Emocional'),
        ('Social', 'Social'),
        ('Salud', 'Salud'),
    ]
    idPregunta = models.AutoField(primary_key=True, db_column='id')
    pregunta = models.TextField(db_column='pregunta')
    tipo_respuesta = models.CharField(max_length=20, choices=TIPO_RESPUESTA_CHOICES, default='escala', db_column='tipo_respuesta')
    categoria = models.CharField(max_length=20, choices=CATEGORIA_CHOICES, default='Academico', db_column='categoria')
    activo = models.BooleanField(default=True, db_column='activo')
    created_at = models.DateTimeField(auto_now_add=True, db_column='created_at')
    updated_at = models.DateTimeField(auto_now=True, db_column='updated_at')

    def __str__(self):
        return self.pregunta[:50]

    class Meta:
        db_table = 'catalogo_pregunta'


class CatalogoFactorRiesgo(models.Model):
    """Catálogo de factores de riesgo (UNIFICADO)"""
    idFactor = models.AutoField(primary_key=True, db_column='id')
    nombre = models.CharField(max_length=100, unique=True, db_column='nombre')
    peso = models.DecimalField(max_digits=3, decimal_places=2, default=1.00, db_column='peso')
    descripcion = models.TextField(blank=True, null=True, db_column='descripcion')
    activo = models.BooleanField(default=True, db_column='activo')
    created_at = models.DateTimeField(auto_now_add=True, db_column='created_at')
    updated_at = models.DateTimeField(auto_now=True, db_column='updated_at')

    def __str__(self):
        return self.nombre

    class Meta:
        db_table = 'catalogo_factorriesgo'


# ============================================
# 2. USUARIO PERSONALIZADO
# ============================================

class Usuario(AbstractUser):
    ROL_CHOICES = [
        ('admin', 'Administrador'),
        ('tutor', 'Tutor'),
        ('profesor', 'Profesor'),
        ('estudiante', 'Estudiante'),
    ]
    GENERO_CHOICES = [
        ('M', 'Masculino'),
        ('F', 'Femenino'),
        ('Otro', 'Otro'),
    ]

    carnet = models.CharField(max_length=20, unique=True, db_column='carnet')
    genero = models.CharField(max_length=10, choices=GENERO_CHOICES, blank=True, null=True, db_column='genero')
    telefono = models.CharField(max_length=20, blank=True, null=True, db_column='telefono')
    foto = models.ImageField(upload_to='usuarios/fotos/', blank=True, null=True, db_column='foto')
    fecha_nacimiento = models.DateField(blank=True, null=True, db_column='fecha_nacimiento')
    rol = models.CharField(max_length=20, choices=ROL_CHOICES, default='estudiante', db_column='rol')
    idUniversidad = models.ForeignKey(
        CatalogoUniversidad,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        db_column='universidad_id',
        related_name='usuarios'
    )
    es_admin_universidad = models.BooleanField(
        default=False,
        db_column='es_admin_universidad',
        help_text='Indica si el usuario es administrador de su universidad'
    )
    notificaciones_email = models.BooleanField(default=True, db_column='notificaciones_email')
    notificaciones_whatsapp = models.BooleanField(default=False, db_column='notificaciones_whatsapp')
    whatsapp_telefono = models.CharField(max_length=20, blank=True, null=True, db_column='whatsapp_telefono')
    cambiar_password = models.BooleanField(default=True, db_column='cambiar_password')
    created_at = models.DateTimeField(auto_now_add=True, db_column='created_at')
    updated_at = models.DateTimeField(auto_now=True, db_column='updated_at')

    groups = models.ManyToManyField(
        'auth.Group',
        related_name='usuario_set',
        blank=True
    )
    user_permissions = models.ManyToManyField(
        'auth.Permission',
        related_name='usuario_perm_set',
        blank=True
    )

    class Meta:
        db_table = 'core_usuario'
        indexes = [
            models.Index(fields=['idUniversidad', 'rol']),
            models.Index(fields=['es_admin_universidad']),
        ]

    def __str__(self):
        return f"{self.username} ({self.get_rol_display()}) - {self.carnet}"

    def get_universidad(self):
        if self.idUniversidad:
            return self.idUniversidad.nombre
        return "Sin universidad asignada"

    @property
    def nombre_completo(self):
        return f"{self.first_name} {self.last_name}".strip() or self.username

    @property
    def foto_url(self):
        if self.foto:
            return self.foto.url
        return None


# ============================================
# 3. ESTUDIANTE
# ============================================

class Estudiante(models.Model):
    ESTADO_CHOICES = [
        ('Activo', 'Activo'),
        ('Inactivo', 'Inactivo'),
        ('Suspendido', 'Suspendido'),
        ('Egresado', 'Egresado'),
        ('Abandonado', 'Abandonado'),
    ]

    idEstudiante = models.AutoField(primary_key=True, db_column='id')
    idUsuario = models.OneToOneField(
        Usuario,
        on_delete=models.CASCADE,
        db_column='usuario_id',
        related_name='estudiante'
    )
    idCarrera = models.ForeignKey(
        CatalogoCarrera,
        on_delete=models.SET_NULL,
        null=True,
        db_column='carrera_id',
        related_name='estudiantes'
    )
    idUniversidad = models.ForeignKey(
        CatalogoUniversidad,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        db_column='universidad_id',
        related_name='estudiantes'
    )
    ano_ingreso = models.IntegerField(db_column='ano_ingreso')
    semestre_actual = models.IntegerField(default=1, db_column='semestre_actual')
    estado_academico = models.CharField(
        max_length=20,
        choices=ESTADO_CHOICES,
        default='Activo',
        db_column='estado_academico'
    )
    promedio_general = models.DecimalField(max_digits=5, decimal_places=2, default=0, null=True, blank=True)
    porcentaje_asistencia = models.DecimalField(max_digits=5, decimal_places=2, default=0, null=True, blank=True)
    indice_compromiso = models.DecimalField(max_digits=5, decimal_places=2, default=0, null=True, blank=True)
    indice_bienestar = models.DecimalField(max_digits=5, decimal_places=2, default=0, null=True, blank=True)
    direccion = models.CharField(max_length=200, blank=True, null=True, db_column='direccion')
    telefono_emergencia = models.CharField(max_length=20, blank=True, null=True, db_column='telefono_emergencia')
    contacto_emergencia_nombre = models.CharField(max_length=100, blank=True, null=True, db_column='contacto_emergencia_nombre')
    nacionalidad = models.CharField(max_length=50, default='Nacional', db_column='nacionalidad')
    created_at = models.DateTimeField(auto_now_add=True, db_column='created_at')
    updated_at = models.DateTimeField(auto_now=True, db_column='updated_at')

    class Meta:
        db_table = 'estudiante'

    def __str__(self):
        return f"{self.nombre_completo} ({self.idUsuario.carnet if self.idUsuario else 'Sin usuario'})"

    @property
    def nombre_completo(self):
        if self.idUsuario:
            return f"{self.idUsuario.first_name} {self.idUsuario.last_name}".strip()
        return f"Estudiante {self.idEstudiante}"

    @property
    def nombre(self):
        return self.idUsuario.first_name if self.idUsuario else ''

    @property
    def apellido_paterno(self):
        if self.idUsuario and self.idUsuario.last_name:
            return self.idUsuario.last_name.split()[0]
        return ''

    @property
    def apellido_materno(self):
        if self.idUsuario and self.idUsuario.last_name:
            partes = self.idUsuario.last_name.split()
            return partes[1] if len(partes) > 1 else ''
        return ''

    @property
    def carnet(self):
        return self.idUsuario.carnet if self.idUsuario else ''

    @property
    def email(self):
        return self.idUsuario.email if self.idUsuario else ''

    @property
    def telefono(self):
        return self.idUsuario.telefono if self.idUsuario else ''

    @property
    def genero(self):
        return self.idUsuario.genero if self.idUsuario else None


# ============================================
# 4. RELACIÓN TUTOR-ESTUDIANTE
# ============================================

class UsuarioEstudiantes(models.Model):
    """Relación entre usuarios (tutores/profesores) y estudiantes."""
    id = models.AutoField(primary_key=True, db_column='id')
    usuario = models.ForeignKey(
        'Usuario',
        on_delete=models.CASCADE,
        db_column='usuario_id',
        related_name='estudiantes_asignados'
    )
    estudiante = models.ForeignKey(
        'Estudiante',
        on_delete=models.CASCADE,
        db_column='estudiante_id',
        related_name='tutores_asignados'
    )
    fecha_asignacion = models.DateTimeField(auto_now_add=True, db_column='fecha_asignacion')

    class Meta:
        db_table = 'usuario_estudiantes'
        unique_together = ['usuario', 'estudiante']

    def __str__(self):
        return f"{self.usuario.username} → {self.estudiante.idUsuario.carnet if self.estudiante.idUsuario else 'Sin carnet'}"


# ============================================
# 5. TUTOR
# ============================================

class Tutor(models.Model):
    id = models.AutoField(primary_key=True)
    usuario = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='tutor'
    )
    especialidad = models.CharField(max_length=200)
    max_estudiantes = models.IntegerField(
        default=10,
        validators=[MinValueValidator(1), MaxValueValidator(50)]
    )
    estudiantes_asignados = models.IntegerField(default=0)
    activo = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'tutor'
        ordering = ['usuario__first_name']
        verbose_name = 'Tutor'
        verbose_name_plural = 'Tutores'

    def __str__(self):
        return f"Tutor: {self.usuario.get_full_name()} - {self.especialidad}"

    def tiene_cupo(self):
        return self.estudiantes_asignados < self.max_estudiantes

    def cupos_disponibles(self):
        return self.max_estudiantes - self.estudiantes_asignados


# ============================================
# 6. ASIGNACIÓN TUTOR
# ============================================

class AsignacionTutor(models.Model):
    ESTADO_CHOICES = [
        ('pendiente', 'Pendiente'),
        ('confirmada', 'Confirmada'),
        ('rechazada', 'Rechazada'),
        ('cancelada', 'Cancelada'),
    ]

    id = models.AutoField(primary_key=True)
    estudiante = models.ForeignKey(
        'Estudiante',
        on_delete=models.CASCADE,
        related_name='asignaciones_tutor'
    )
    tutor = models.ForeignKey(
        'Tutor',
        on_delete=models.CASCADE,
        related_name='asignaciones'
    )
    profesor_asignador = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='asignaciones_realizadas'
    )
    estado = models.CharField(max_length=20, choices=ESTADO_CHOICES, default='pendiente')
    fecha_asignacion = models.DateTimeField(auto_now_add=True)
    fecha_confirmacion = models.DateTimeField(null=True, blank=True)
    observaciones = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'asignacion_tutor'
        unique_together = ['estudiante', 'tutor']
        ordering = ['-fecha_asignacion']
        verbose_name = 'Asignación de Tutor'
        verbose_name_plural = 'Asignaciones de Tutores'

    def __str__(self):
        return f"{self.estudiante} → {self.tutor.usuario.get_full_name()} ({self.get_estado_display()})"

    def confirmar(self):
        """Confirma la asignación y actualiza el contador del tutor de forma atómica."""
        from django.db import transaction

        if self.estado == 'confirmada':
            return

        with transaction.atomic():
            self.estado = 'confirmada'
            self.fecha_confirmacion = timezone.now()
            self.save(update_fields=['estado', 'fecha_confirmacion', 'updated_at'])

            Tutor.objects.filter(pk=self.tutor_id).update(
                estudiantes_asignados=models.F('estudiantes_asignados') + 1
            )

    def cancelar(self):
        """Cancela una asignación previamente confirmada y libera cupo."""
        from django.db import transaction

        era_confirmada = self.estado == 'confirmada'

        with transaction.atomic():
            self.estado = 'cancelada'
            self.save(update_fields=['estado', 'updated_at'])

            if era_confirmada:
                Tutor.objects.filter(
                    pk=self.tutor_id,
                    estudiantes_asignados__gt=0
                ).update(estudiantes_asignados=models.F('estudiantes_asignados') - 1)


# ============================================
# 7. PROFESOR
# ============================================

class Profesor(models.Model):
    ESPECIALIDAD_CHOICES = [
        ('Matemáticas', 'Matemáticas'),
        ('Física', 'Física'),
        ('Química', 'Química'),
        ('Biología', 'Biología'),
        ('Literatura', 'Literatura'),
        ('Historia', 'Historia'),
        ('Geografía', 'Geografía'),
        ('Inglés', 'Inglés'),
        ('Programación', 'Programación'),
        ('Diseño', 'Diseño'),
        ('Economía', 'Economía'),
        ('Administración', 'Administración'),
        ('Derecho', 'Derecho'),
        ('Psicología', 'Psicología'),
        ('Sociología', 'Sociología'),
        ('Filosofía', 'Filosofía'),
        ('Educación Física', 'Educación Física'),
        ('Artes', 'Artes'),
        ('Música', 'Música'),
        ('Otra', 'Otra'),
    ]
    TIPO_CONTRATO_CHOICES = [
        ('Tiempo Completo', 'Tiempo Completo'),
        ('Medio Tiempo', 'Medio Tiempo'),
        ('Por Horas', 'Por Horas'),
        ('Visitante', 'Visitante'),
        ('Adjunto', 'Adjunto'),
        ('Titular', 'Titular'),
    ]
    ESTADO_CHOICES = [
        ('Activo', 'Activo'),
        ('Inactivo', 'Inactivo'),
        ('Suspendido', 'Suspendido'),
        ('Retirado', 'Retirado'),
        ('Licencia', 'Licencia'),
    ]

    id = models.AutoField(primary_key=True, db_column='id')
    usuario = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='profesor',
        db_column='usuario_id'
    )
    idUniversidad = models.ForeignKey(
        CatalogoUniversidad,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        db_column='universidad_id',
        related_name='profesores'
    )
    especialidad = models.CharField(
        max_length=100,
        choices=ESPECIALIDAD_CHOICES,
        default='Otra',
        db_column='especialidad'
    )
    especialidad_otra = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        db_column='especialidad_otra',
        help_text='Especificar si la especialidad es "Otra"'
    )
    grado_academico = models.CharField(max_length=100, blank=True, null=True, db_column='grado_academico')
    titulo_profesional = models.CharField(max_length=200, blank=True, null=True, db_column='titulo_profesional')
    universidad_egreso = models.CharField(max_length=200, blank=True, null=True, db_column='universidad_egreso')
    ano_egreso = models.IntegerField(blank=True, null=True, db_column='ano_egreso')
    tipo_contrato = models.CharField(
        max_length=20,
        choices=TIPO_CONTRATO_CHOICES,
        default='Tiempo Completo',
        db_column='tipo_contrato'
    )
    fecha_ingreso = models.DateField(db_column='fecha_ingreso', help_text='Fecha de ingreso a la institución')
    fecha_termino = models.DateField(blank=True, null=True, db_column='fecha_termino')
    estado = models.CharField(max_length=20, choices=ESTADO_CHOICES, default='Activo', db_column='estado')

    # ✅ M2M vía MateriaProfesor → CatalogoMateria
    materias_impartidas = models.ManyToManyField(
        'CatalogoMateria',
        through='MateriaProfesor',
        through_fields=('profesor', 'materia'),
        related_name='profesores',
        blank=True
    )

    observaciones = models.TextField(blank=True, null=True, db_column='observaciones')
    created_at = models.DateTimeField(auto_now_add=True, db_column='created_at')
    updated_at = models.DateTimeField(auto_now=True, db_column='updated_at')

    class Meta:
        db_table = 'profesor'
        ordering = ['usuario__first_name', 'usuario__last_name']
        verbose_name = 'Profesor'
        verbose_name_plural = 'Profesores'
        indexes = [
            models.Index(fields=['idUniversidad', 'estado']),
            models.Index(fields=['estado']),
            models.Index(fields=['especialidad']),
        ]

    def __str__(self):
        nombre = self.usuario.get_full_name() if self.usuario else f"Profesor {self.id}"
        return f"{nombre} - {self.get_especialidad_display()}"

    @property
    def nombre_completo(self):
        if self.usuario:
            return self.usuario.get_full_name().strip() or self.usuario.username
        return f"Profesor {self.id}"

    @property
    def email(self):
        return self.usuario.email if self.usuario else ''

    @property
    def telefono(self):
        return self.usuario.telefono if self.usuario else ''

    @property
    def especialidad_display(self):
        if self.especialidad == 'Otra' and self.especialidad_otra:
            return self.especialidad_otra
        return self.get_especialidad_display()

    def esta_activo(self):
        return self.estado == 'Activo'

    def get_materias_count(self):
        return self.materias_impartidas.count()

    def get_materias_list(self):
        return self.materias_impartidas.all()

    def get_carreras_list(self):
        """Obtiene las carreras donde imparte materias (vía CatalogoMateria.idCarrera)."""
        return CatalogoCarrera.objects.filter(
            materias_catalogo__profesores=self
        ).distinct()

    def get_universidad_nombre(self):
        if self.idUniversidad:
            return self.idUniversidad.nombre
        return "Sin universidad asignada"


# ============================================
# 8. MATERIA PROFESOR (Relación Materia-Profesor)
# ============================================

class MateriaProfesor(models.Model):
    """Relación entre profesores y materias del catálogo."""
    id = models.AutoField(primary_key=True, db_column='id')
    profesor = models.ForeignKey(
        'Profesor',
        on_delete=models.CASCADE,
        db_column='profesor_id',
        related_name='materias_asignadas'
    )
    materia = models.ForeignKey(
        'CatalogoMateria',
        on_delete=models.CASCADE,
        db_column='materia_id',
        related_name='profesores_asignados'
    )
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        db_column='usuario_id',
        related_name='materias_profesor',
        null=True,
        blank=True
    )
    fecha_asignacion = models.DateTimeField(auto_now_add=True, db_column='fecha_asignacion')
    es_principal = models.BooleanField(
        default=False,
        db_column='es_principal',
        help_text='Indica si es el profesor principal de la materia'
    )
    observaciones = models.TextField(blank=True, null=True, db_column='observaciones')
    created_at = models.DateTimeField(auto_now_add=True, db_column='created_at')
    updated_at = models.DateTimeField(auto_now=True, db_column='updated_at')

    class Meta:
        db_table = 'materia_profesor'
        unique_together = ['profesor', 'materia']
        verbose_name = 'Asignación de Materia a Profesor'
        verbose_name_plural = 'Asignaciones de Materias a Profesores'
        ordering = ['profesor__usuario__first_name', 'materia__nombre']
        indexes = [
            models.Index(fields=['profesor', 'materia']),
            models.Index(fields=['usuario']),
        ]

    def __str__(self):
        nombre_profesor = self.profesor.nombre_completo if self.profesor else 'Sin profesor'
        nombre_materia = self.materia.nombre if self.materia else 'Sin materia'
        return f"{nombre_profesor} → {nombre_materia}"

    @property
    def profesor_nombre(self):
        return self.profesor.nombre_completo if self.profesor else ''

    @property
    def materia_nombre(self):
        return self.materia.nombre if self.materia else ''

    @property
    def usuario_nombre(self):
        return self.usuario.get_full_name() if self.usuario else ''


# ============================================
# 9. PROFESOR CARRERA
# ============================================

class ProfesorCarrera(models.Model):
    """Relación entre profesores y carreras del catálogo."""
    id = models.AutoField(primary_key=True, db_column='id')
    profesor = models.ForeignKey(
        Profesor,
        on_delete=models.CASCADE,
        db_column='profesor_id',
        related_name='carreras_asignadas'
    )
    carrera = models.ForeignKey(
        'CatalogoCarrera',
        on_delete=models.CASCADE,
        db_column='carrera_id',
        related_name='profesores_asignados'
    )
    es_coordinador = models.BooleanField(
        default=False,
        db_column='es_coordinador',
        help_text='Indica si el profesor es coordinador de la carrera'
    )
    fecha_asignacion = models.DateTimeField(auto_now_add=True, db_column='fecha_asignacion')
    observaciones = models.TextField(blank=True, null=True, db_column='observaciones')
    created_at = models.DateTimeField(auto_now_add=True, db_column='created_at')
    updated_at = models.DateTimeField(auto_now=True, db_column='updated_at')

    class Meta:
        db_table = 'profesor_carrera'
        unique_together = ['profesor', 'carrera']
        verbose_name = 'Asignación de Profesor a Carrera'
        verbose_name_plural = 'Asignaciones de Profesores a Carreras'
        ordering = ['profesor__usuario__first_name', 'carrera__nombre']

    def __str__(self):
        return f"{self.profesor.nombre_completo} → {self.carrera.nombre}"


# ============================================
# 10. BECAS (Sistema unificado)
# ============================================

class Beca(models.Model):
    """
    Beca institucional. El tipo se referencia desde CatalogoTipoBeca.
    """
    ESTADO_CHOICES = [
        ('Activa', 'Activa'),
        ('Inactiva', 'Inactiva'),
        ('Completa', 'Completa'),
        ('Cancelada', 'Cancelada'),
    ]

    id = models.AutoField(primary_key=True)
    nombre = models.CharField(max_length=200)
    codigo = models.CharField(max_length=50, unique=True)
    descripcion = models.TextField(blank=True, null=True)

    # ✅ CAMBIO: tipo ahora es FK a CatalogoTipoBeca
    tipo = models.ForeignKey(
        CatalogoTipoBeca,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='becas',
        db_column='tipo_id'
    )

    monto = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    porcentaje_cobertura = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    duracion_meses = models.IntegerField(default=12)
    requisitos = models.TextField(blank=True, null=True)
    beneficios = models.TextField(blank=True, null=True)
    fecha_inicio = models.DateField(null=True, blank=True)
    fecha_fin = models.DateField(null=True, blank=True)
    cupos_disponibles = models.IntegerField(default=0)
    estado = models.CharField(max_length=20, choices=ESTADO_CHOICES, default='Activa')
    idUniversidad = models.ForeignKey(
        CatalogoUniversidad,
        on_delete=models.CASCADE,
        related_name='becas'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        tipo_str = self.tipo.nombre if self.tipo else 'Sin tipo'
        return f"{self.codigo} - {self.nombre} ({tipo_str})"

    def cupos_disponibles_actuales(self):
        asignados = self.asignaciones.filter(estado='Activa').count()
        return max(self.cupos_disponibles - asignados, 0)

    @property
    def cupos_ocupados(self):
        return self.asignaciones.filter(estado='Activa').count()

    @property
    def tipo_nombre(self):
        return self.tipo.nombre if self.tipo else 'Sin tipo'

    class Meta:
        verbose_name = 'Beca'
        verbose_name_plural = 'Becas'
        ordering = ['-created_at', 'nombre']
        indexes = [
            models.Index(fields=['idUniversidad', 'estado']),
            models.Index(fields=['tipo']),
        ]


class BecaAsignacion(models.Model):
    """
    Asignación de una beca a un estudiante.
    Incluye montos personalizados opcionales que sobreescriben los de la Beca.
    """
    ESTADO_CHOICES = [
        ('Activa', 'Activa'),
        ('Finalizada', 'Finalizada'),
        ('Cancelada', 'Cancelada'),
        ('Pendiente', 'Pendiente'),
    ]

    id = models.AutoField(primary_key=True)

    # ✅ CAMBIO: related_name='asignaciones'
    idBeca = models.ForeignKey(
        Beca,
        on_delete=models.CASCADE,
        related_name='asignaciones'
    )
    # ✅ CAMBIO: related_name='becas_asignadas'
    idEstudiante = models.ForeignKey(
        Estudiante,
        on_delete=models.CASCADE,
        related_name='becas_asignadas'
    )

    # ➕ NUEVOS: campos absorbidos de BecaEstudiante
    monto_personalizado = models.DecimalField(
        max_digits=10, decimal_places=2,
        null=True, blank=True,
        help_text='Si se especifica, sobreescribe el monto de la Beca'
    )
    porcentaje_personalizado = models.DecimalField(
        max_digits=5, decimal_places=2,
        null=True, blank=True,
        help_text='Si se especifica, sobreescribe el porcentaje de la Beca'
    )

    fecha_asignacion = models.DateTimeField(auto_now_add=True)
    fecha_inicio = models.DateField()
    fecha_fin = models.DateField()
    estado = models.CharField(max_length=20, choices=ESTADO_CHOICES, default='Pendiente')
    observaciones = models.TextField(blank=True, null=True)
    renovable = models.BooleanField(default=False)
    ultima_renovacion = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Asignación de Beca'
        verbose_name_plural = 'Asignaciones de Becas'
        unique_together = ['idBeca', 'idEstudiante']
        ordering = ['-fecha_asignacion']
        indexes = [
            models.Index(fields=['idEstudiante', 'estado']),
            models.Index(fields=['idBeca', 'estado']),
        ]

    def __str__(self):
        return f"{self.idEstudiante.nombre_completo} - {self.idBeca.nombre} ({self.estado})"

    def esta_activa(self):
        return self.estado == 'Activa'

    @property
    def monto_efectivo(self):
        """Monto efectivo: personalizado si existe, si no el de la Beca."""
        if self.monto_personalizado is not None:
            return self.monto_personalizado
        return self.idBeca.monto

    @property
    def porcentaje_efectivo(self):
        """Porcentaje efectivo: personalizado si existe, si no el de la Beca."""
        if self.porcentaje_personalizado is not None:
            return self.porcentaje_personalizado
        return self.idBeca.porcentaje_cobertura


# ============================================
# 11. RIESGO ESTUDIANTE
# ============================================

class RiesgoEstudiante(models.Model):
    NIVEL_CHOICES = [
        ('Bajo', 'Bajo'),
        ('Medio', 'Medio'),
        ('Alto', 'Alto'),
        ('Critico', 'Crítico'),
    ]
    ESTADO_CHOICES = [
        ('Activo', 'Activo'),
        ('En seguimiento', 'En seguimiento'),
        ('Resuelto', 'Resuelto'),
        ('Derivado', 'Derivado'),
    ]

    idRiesgo = models.AutoField(primary_key=True, db_column='id')
    idEstudiante = models.ForeignKey(
        Estudiante,
        on_delete=models.CASCADE,
        db_column='estudiante_id',
        related_name='riesgos'
    )
    idFactor = models.ForeignKey(
        CatalogoFactorRiesgo,
        on_delete=models.CASCADE,
        db_column='factor_id',
        related_name='riesgos'
    )
    nivel = models.CharField(max_length=20, choices=NIVEL_CHOICES, default='Medio', db_column='nivel')
    puntaje = models.DecimalField(max_digits=5, decimal_places=2, blank=True, null=True, db_column='puntaje')
    fecha_deteccion = models.DateField(db_column='fecha_deteccion')
    fecha_resolucion = models.DateField(blank=True, null=True, db_column='fecha_resolucion')
    estado = models.CharField(max_length=20, choices=ESTADO_CHOICES, default='Activo', db_column='estado')
    observaciones = models.TextField(blank=True, null=True, db_column='observaciones')
    created_at = models.DateTimeField(auto_now_add=True, db_column='created_at')
    updated_at = models.DateTimeField(auto_now=True, db_column='updated_at')

    def __str__(self):
        return f"{self.idEstudiante.nombre_completo} - {self.nivel} - {self.estado}"

    class Meta:
        db_table = 'riesgo_estudiante'
        verbose_name = 'Riesgo de Estudiante'
        verbose_name_plural = 'Riesgos de Estudiantes'
        ordering = ['-fecha_deteccion']


# ============================================
# 12. ALERTA
# ============================================

class Alerta(models.Model):
    NIVEL_CHOICES = [
        ('Crítico', 'Crítico'),
        ('Alto', 'Alto'),
        ('Medio', 'Medio'),
        ('Bajo', 'Bajo'),
    ]
    ESTADO_CHOICES = [
        ('Activa', 'Activa'),
        ('Atendida', 'Atendida'),
        ('Resuelta', 'Resuelta'),
        ('Cerrada', 'Cerrada'),
    ]

    id = models.AutoField(primary_key=True)
    idEstudiante = models.ForeignKey(Estudiante, on_delete=models.CASCADE, related_name='alertas')
    idFactor = models.ForeignKey(
        CatalogoFactorRiesgo,
        on_delete=models.CASCADE,
        related_name='alertas',
        null=True,
        blank=True
    )
    nivel = models.CharField(max_length=20, choices=NIVEL_CHOICES, default='Medio')
    estado = models.CharField(max_length=20, choices=ESTADO_CHOICES, default='Activa')
    descripcion = models.TextField()
    fecha_deteccion = models.DateTimeField(auto_now_add=True)
    fecha_atencion = models.DateTimeField(null=True, blank=True)
    fecha_resolucion = models.DateTimeField(null=True, blank=True)
    usuario_responsable = models.ForeignKey(
        Usuario,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='alertas_atendidas'
    )
    observaciones = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.idEstudiante.nombre_completo} - {self.nivel} - {self.estado}"

    class Meta:
        verbose_name = 'Alerta'
        verbose_name_plural = 'Alertas'
        ordering = ['-fecha_deteccion']


# ============================================
# 13. INTERVENCIÓN
# ============================================

class Intervencion(models.Model):
    TIPO_CHOICES = [
        ('Tutoría', 'Tutoría'),
        ('Consejería', 'Consejería'),
        ('Académica', 'Académica'),
        ('Psicológica', 'Psicológica'),
        ('Social', 'Social'),
        ('Otra', 'Otra'),
    ]
    ESTADO_CHOICES = [
        ('Pendiente', 'Pendiente'),
        ('En Progreso', 'En Progreso'),
        ('Completada', 'Completada'),
        ('Cancelada', 'Cancelada'),
    ]

    id = models.AutoField(primary_key=True)
    idEstudiante = models.ForeignKey(Estudiante, on_delete=models.CASCADE, related_name='intervenciones')
    idAlerta = models.ForeignKey(Alerta, on_delete=models.SET_NULL, null=True, blank=True, related_name='intervenciones')
    tipo_intervencion = models.CharField(max_length=50, choices=TIPO_CHOICES, default='Tutoría')
    estado = models.CharField(max_length=20, choices=ESTADO_CHOICES, default='Pendiente')
    descripcion = models.TextField()
    fecha_programada = models.DateTimeField(null=True, blank=True)
    fecha_realizada = models.DateTimeField(null=True, blank=True)
    efectiva = models.BooleanField(default=False)
    responsable = models.ForeignKey(Usuario, on_delete=models.SET_NULL, null=True, blank=True, related_name='intervenciones_realizadas')
    observaciones = models.TextField(blank=True, null=True)
    resultados = models.TextField(blank=True, null=True)
    seguimiento = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.idEstudiante.nombre_completo} - {self.tipo_intervencion} - {self.estado}"

    def completar(self):
        self.estado = 'Completada'
        self.fecha_realizada = timezone.now()
        self.save()

    class Meta:
        verbose_name = 'Intervención'
        verbose_name_plural = 'Intervenciones'
        ordering = ['-fecha_programada', '-created_at']


# ============================================
# 14. ASISTENCIA
# ============================================

class Asistencia(models.Model):
    idAsistencia = models.AutoField(primary_key=True, db_column='id')
    idEstudiante = models.ForeignKey(
        Estudiante,
        on_delete=models.CASCADE,
        db_column='estudiante_id',
        related_name='asistencias'
    )
    idMateria = models.ForeignKey(
        CatalogoMateria,
        on_delete=models.CASCADE,
        db_column='materia_id',
        null=True,
        blank=True,
        related_name='asistencias'
    )
    idAula = models.ForeignKey(
        CatalogoAula,
        on_delete=models.CASCADE,
        db_column='aula_id',
        related_name='asistencias'
    )
    fecha = models.DateField(db_column='fecha')
    hora_entrada = models.TimeField(blank=True, null=True, db_column='hora_entrada')
    hora_salida = models.TimeField(blank=True, null=True, db_column='hora_salida')
    presente = models.BooleanField(default=True, db_column='presente')
    justificacion = models.TextField(blank=True, null=True, db_column='justificacion')
    observaciones = models.TextField(blank=True, null=True, db_column='observaciones')
    created_at = models.DateTimeField(auto_now_add=True, db_column='created_at')
    updated_at = models.DateTimeField(auto_now=True, db_column='updated_at')

    def __str__(self):
        return f"{self.idEstudiante.nombre_completo} - {self.fecha} - {'Presente' if self.presente else 'Ausente'}"

    class Meta:
        db_table = 'asistencia'
        verbose_name = 'Asistencia'
        verbose_name_plural = 'Asistencias'
        ordering = ['-fecha']
        unique_together = ['idEstudiante', 'idMateria', 'fecha']


# ============================================
# 15. HISTORIAL ACADÉMICO
# ============================================

class HistorialAcademico(models.Model):
    ESTADO_CHOICES = [
        ('Aprobada', 'Aprobada'),
        ('Reprobada', 'Reprobada'),
        ('Cursando', 'Cursando'),
        ('Retirada', 'Retirada'),
        ('Pendiente', 'Pendiente'),
    ]

    idHistorial = models.AutoField(primary_key=True, db_column='id')
    idEstudiante = models.ForeignKey(
        Estudiante,
        on_delete=models.CASCADE,
        db_column='estudiante_id',
        related_name='historial_academico'
    )
    idMateria = models.ForeignKey(
        CatalogoMateria,
        on_delete=models.CASCADE,
        db_column='materia_id',
        related_name='historial_academico'
    )
    semestre = models.CharField(max_length=10, db_column='semestre', help_text="Ej: 2024-1")
    nota_final = models.DecimalField(max_digits=4, decimal_places=2, blank=True, null=True, db_column='nota_final')
    estado_materia = models.CharField(max_length=20, choices=ESTADO_CHOICES, default='Cursando', db_column='estado_materia')
    intentos = models.IntegerField(default=1, db_column='intentos')
    fecha_registro = models.DateField(blank=True, null=True, db_column='fecha_registro')
    fecha_inscripcion = models.DateField(auto_now_add=True, db_column='fecha_inscripcion')
    fecha_aprobacion = models.DateField(null=True, blank=True, db_column='fecha_aprobacion')
    observaciones = models.TextField(blank=True, null=True, db_column='observaciones')
    created_at = models.DateTimeField(auto_now_add=True, db_column='created_at')
    updated_at = models.DateTimeField(auto_now=True, db_column='updated_at')

    def __str__(self):
        return f"{self.idEstudiante.nombre_completo} - {self.idMateria.nombre} - {self.estado_materia}"

    def esta_aprobada(self):
        return self.estado_materia == 'Aprobada'

    class Meta:
        db_table = 'historial_academico'
        verbose_name = 'Historial Académico'
        verbose_name_plural = 'Historiales Académicos'
        ordering = ['-semestre', 'idMateria__nombre']
        unique_together = ['idEstudiante', 'idMateria', 'semestre']


# ============================================
# 16. ENCUESTAS
# ============================================

class Encuesta(models.Model):
    ESTADO_CHOICES = [
        ('borrador', 'Borrador'),
        ('activa', 'Activa'),
        ('cerrada', 'Cerrada'),
    ]

    idEncuesta = models.AutoField(primary_key=True, db_column='id')
    titulo = models.CharField(max_length=200, db_column='titulo')
    descripcion = models.TextField(blank=True, null=True, db_column='descripcion')
    creador = models.ForeignKey(Usuario, on_delete=models.CASCADE, related_name='encuestas_creadas', db_column='creador_id')
    idUniversidad = models.ForeignKey(CatalogoUniversidad, on_delete=models.CASCADE, db_column='universidad_id', related_name='encuestas')
    fecha_inicio = models.DateTimeField(db_column='fecha_inicio')
    fecha_fin = models.DateTimeField(db_column='fecha_fin')
    es_obligatoria = models.BooleanField(default=False, db_column='es_obligatoria')
    anonima = models.BooleanField(default=False, db_column='anonima')
    tiempo_estimado = models.PositiveIntegerField(default=5, db_column='tiempo_estimado')
    estado = models.CharField(max_length=20, choices=ESTADO_CHOICES, default='borrador', db_column='estado')
    created_at = models.DateTimeField(auto_now_add=True, db_column='created_at')
    updated_at = models.DateTimeField(auto_now=True, db_column='updated_at')

    class Meta:
        db_table = 'encuesta'
        ordering = ['-created_at']

    def __str__(self):
        return self.titulo

    def esta_activa(self):
        ahora = timezone.now()
        return self.estado == 'activa' and self.fecha_inicio <= ahora <= self.fecha_fin


class EncuestaAsignacion(models.Model):
    idAsignacion = models.AutoField(primary_key=True, db_column='id')
    encuesta = models.ForeignKey(Encuesta, on_delete=models.CASCADE, related_name='asignaciones', db_column='encuesta_id')
    estudiante = models.ForeignKey(Estudiante, on_delete=models.CASCADE, related_name='encuestas_asignadas', db_column='estudiante_id')
    fecha_asignacion = models.DateTimeField(auto_now_add=True, db_column='fecha_asignacion')
    fecha_respuesta = models.DateTimeField(null=True, blank=True, db_column='fecha_respuesta')
    completada = models.BooleanField(default=False, db_column='completada')
    fecha_recordatorio = models.DateTimeField(null=True, blank=True, db_column='fecha_recordatorio')
    recordatorios_enviados = models.PositiveIntegerField(default=0, db_column='recordatorios_enviados')

    class Meta:
        db_table = 'encuesta_asignacion'
        unique_together = ['encuesta', 'estudiante']

    def __str__(self):
        return f"{self.estudiante.nombre_completo} - {self.encuesta.titulo} - {'Completada' if self.completada else 'Pendiente'}"


class EncuestaPregunta(models.Model):
    TIPO_CHOICES = [
        ('opcion_unica', 'Opción Única'),
        ('opcion_multiple', 'Opción Múltiple'),
        ('escala', 'Escala (1-5)'),
        ('texto', 'Texto Libre'),
        ('si_no', 'Sí/No'),
    ]

    idPreguntaEncuesta = models.AutoField(primary_key=True, db_column='id')
    encuesta = models.ForeignKey(Encuesta, on_delete=models.CASCADE, related_name='preguntas', db_column='encuesta_id')
    pregunta = models.TextField(db_column='pregunta')
    tipo = models.CharField(max_length=20, choices=TIPO_CHOICES, default='opcion_unica', db_column='tipo')
    es_obligatoria = models.BooleanField(default=True, db_column='es_obligatoria')
    orden = models.IntegerField(default=0, db_column='orden')
    created_at = models.DateTimeField(auto_now_add=True, db_column='created_at')

    def __str__(self):
        return self.pregunta[:60]

    class Meta:
        db_table = 'encuesta_pregunta'
        ordering = ['orden']


class EncuestaOpcion(models.Model):
    idOpcion = models.AutoField(primary_key=True, db_column='id')
    pregunta = models.ForeignKey(EncuestaPregunta, on_delete=models.CASCADE, related_name='opciones', db_column='pregunta_id')
    texto = models.CharField(max_length=200, db_column='texto')
    valor = models.IntegerField(default=0, db_column='valor')
    orden = models.IntegerField(default=0, db_column='orden')

    def __str__(self):
        return self.texto

    class Meta:
        db_table = 'encuesta_opcion'
        ordering = ['orden']


class EncuestaRespuesta(models.Model):
    idRespuestaEncuesta = models.AutoField(primary_key=True, db_column='id')
    asignacion = models.ForeignKey(EncuestaAsignacion, on_delete=models.CASCADE, related_name='respuestas', db_column='asignacion_id')
    pregunta = models.ForeignKey(EncuestaPregunta, on_delete=models.CASCADE, db_column='pregunta_id')
    opcion = models.ForeignKey(EncuestaOpcion, on_delete=models.CASCADE, blank=True, null=True, db_column='opcion_id')
    respuesta_texto = models.TextField(blank=True, null=True, db_column='respuesta_texto')
    respuesta_escala = models.IntegerField(blank=True, null=True, db_column='respuesta_escala')
    respuesta_booleana = models.BooleanField(blank=True, null=True, db_column='respuesta_booleana')
    fecha_respuesta = models.DateTimeField(auto_now_add=True, db_column='fecha_respuesta')

    class Meta:
        db_table = 'encuesta_respuesta'
        unique_together = ['asignacion', 'pregunta']


# ============================================
# 17. TAREAS
# ============================================

class Tarea(models.Model):
    ESTADO_CHOICES = [
        ('borrador', 'Borrador'),
        ('publicada', 'Publicada'),
        ('cerrada', 'Cerrada'),
        ('archivada', 'Archivada'),
    ]

    idTarea = models.AutoField(primary_key=True, db_column='id')
    titulo = models.CharField(max_length=200, db_column='titulo')
    descripcion = models.TextField(blank=True, null=True, db_column='descripcion')
    instrucciones = models.TextField(blank=True, null=True, db_column='instrucciones')
    puntaje_maximo = models.DecimalField(max_digits=5, decimal_places=2, default=100, db_column='puntaje_maximo')
    creador = models.ForeignKey(Usuario, on_delete=models.CASCADE, related_name='tareas_creadas', db_column='creador_id')
    idUniversidad = models.ForeignKey(CatalogoUniversidad, on_delete=models.CASCADE, db_column='universidad_id', related_name='tareas')
    fecha_publicacion = models.DateTimeField(db_column='fecha_publicacion')
    fecha_limite = models.DateTimeField(db_column='fecha_limite')
    estado = models.CharField(max_length=20, choices=ESTADO_CHOICES, default='borrador', db_column='estado')
    created_at = models.DateTimeField(auto_now_add=True, db_column='created_at')
    updated_at = models.DateTimeField(auto_now=True, db_column='updated_at')

    class Meta:
        db_table = 'tarea'
        ordering = ['-created_at']

    def __str__(self):
        return self.titulo

    def esta_activa(self):
        ahora = timezone.now()
        return self.estado == 'publicada' and self.fecha_publicacion <= ahora <= self.fecha_limite


class TareaAsignacion(models.Model):
    idAsignacion = models.AutoField(primary_key=True, db_column='id')
    tarea = models.ForeignKey(Tarea, on_delete=models.CASCADE, db_column='tarea_id', related_name='asignaciones')
    estudiante = models.ForeignKey(Estudiante, on_delete=models.CASCADE, db_column='estudiante_id', related_name='tareas_asignadas')
    fecha_asignacion = models.DateTimeField(auto_now_add=True, db_column='fecha_asignacion')
    fecha_entrega = models.DateTimeField(blank=True, null=True, db_column='fecha_entrega')
    entregada = models.BooleanField(default=False, db_column='entregada')
    calificada = models.BooleanField(default=False, db_column='calificada')
    puntaje_obtenido = models.DecimalField(max_digits=5, decimal_places=2, blank=True, null=True, db_column='puntaje_obtenido')
    retroalimentacion = models.TextField(blank=True, null=True, db_column='retroalimentacion')

    class Meta:
        db_table = 'tarea_asignacion'
        unique_together = ['tarea', 'estudiante']


class TareaPregunta(models.Model):
    TIPO_CHOICES = [
        ('texto', 'Texto Libre'),
        ('opcion_unica', 'Opción Única'),
        ('opcion_multiple', 'Opción Múltiple'),
        ('archivo', 'Subir Archivo'),
    ]

    idPreguntaTarea = models.AutoField(primary_key=True, db_column='id')
    tarea = models.ForeignKey(Tarea, on_delete=models.CASCADE, related_name='preguntas', db_column='tarea_id')
    pregunta = models.TextField(db_column='pregunta')
    tipo = models.CharField(max_length=20, choices=TIPO_CHOICES, default='texto', db_column='tipo')
    puntaje = models.DecimalField(max_digits=5, decimal_places=2, default=10, db_column='puntaje')
    orden = models.IntegerField(default=0, db_column='orden')
    created_at = models.DateTimeField(auto_now_add=True, db_column='created_at')

    def __str__(self):
        return self.pregunta[:60]

    class Meta:
        db_table = 'tarea_pregunta'
        ordering = ['orden']


class TareaOpcion(models.Model):
    idOpcion = models.AutoField(primary_key=True, db_column='id')
    pregunta = models.ForeignKey(TareaPregunta, on_delete=models.CASCADE, related_name='opciones', db_column='pregunta_id')
    texto = models.CharField(max_length=200, db_column='texto')
    es_correcta = models.BooleanField(default=False, db_column='es_correcta')
    orden = models.IntegerField(default=0, db_column='orden')

    def __str__(self):
        return self.texto

    class Meta:
        db_table = 'tarea_opcion'
        ordering = ['orden']


class TareaRespuesta(models.Model):
    idRespuestaTarea = models.AutoField(primary_key=True, db_column='id')
    asignacion = models.ForeignKey(TareaAsignacion, on_delete=models.CASCADE, related_name='respuestas', db_column='asignacion_id')
    pregunta = models.ForeignKey(TareaPregunta, on_delete=models.CASCADE, db_column='pregunta_id')
    opcion = models.ForeignKey(TareaOpcion, on_delete=models.CASCADE, blank=True, null=True, db_column='opcion_id')
    respuesta_texto = models.TextField(blank=True, null=True, db_column='respuesta_texto')
    archivo = models.CharField(max_length=255, blank=True, null=True, db_column='archivo')
    calificacion = models.DecimalField(max_digits=5, decimal_places=2, blank=True, null=True, db_column='calificacion')
    retroalimentacion_pregunta = models.TextField(blank=True, null=True, db_column='retroalimentacion_pregunta')
    fecha_respuesta = models.DateTimeField(auto_now_add=True, db_column='fecha_respuesta')

    class Meta:
        db_table = 'tarea_respuesta'
        unique_together = ['asignacion', 'pregunta']


# ============================================
# 18. MENSAJERÍA
# ============================================

class Mensaje(models.Model):
    CARPETA_CHOICES = [
        ('inbox', 'Bandeja de entrada'),
        ('enviados', 'Enviados'),
        ('archivados', 'Archivados'),
        ('importante', 'Importante'),
        ('trabajo', 'Trabajo'),
        ('personal', 'Personal'),
    ]

    id = models.AutoField(primary_key=True, db_column='id')
    remitente = models.ForeignKey(Usuario, on_delete=models.CASCADE, related_name='mensajes_enviados', db_column='remitente_id')
    destinatario = models.ForeignKey(Usuario, on_delete=models.CASCADE, related_name='mensajes_recibidos', db_column='destinatario_id')
    asunto = models.CharField(max_length=200, db_column='asunto')
    contenido = models.TextField(db_column='contenido')
    leido = models.BooleanField(default=False, db_column='leido')
    archivado = models.BooleanField(default=False, db_column='archivado')
    carpeta = models.CharField(max_length=20, choices=CARPETA_CHOICES, default='inbox', db_column='carpeta')
    fecha_envio = models.DateTimeField(auto_now_add=True, db_column='fecha_envio')
    fecha_lectura = models.DateTimeField(blank=True, null=True, db_column='fecha_lectura')
    adjuntos_count = models.IntegerField(default=0, db_column='adjuntos_count')
    eliminado_por_remitente = models.BooleanField(default=False, db_column='eliminado_por_remitente')
    eliminado_por_destinatario = models.BooleanField(default=False, db_column='eliminado_por_destinatario')
    fecha_eliminacion_remitente = models.DateTimeField(null=True, blank=True, db_column='fecha_eliminacion_remitente')
    fecha_eliminacion_destinatario = models.DateTimeField(null=True, blank=True, db_column='fecha_eliminacion_destinatario')

    class Meta:
        db_table = 'mensaje'
        ordering = ['-fecha_envio']
        indexes = [
            models.Index(fields=['remitente', 'eliminado_por_remitente']),
            models.Index(fields=['destinatario', 'eliminado_por_destinatario']),
        ]

    def __str__(self):
        return f"{self.asunto} - {self.remitente.username} → {self.destinatario.username}"

    def eliminar_para_usuario(self, usuario):
        if usuario == self.remitente:
            self.eliminado_por_remitente = True
            self.fecha_eliminacion_remitente = timezone.now()
        elif usuario == self.destinatario:
            self.eliminado_por_destinatario = True
            self.fecha_eliminacion_destinatario = timezone.now()
        else:
            raise ValueError("El usuario no es parte de esta conversación")
        self.save()

    def restaurar_para_usuario(self, usuario):
        if usuario == self.remitente:
            self.eliminado_por_remitente = False
            self.fecha_eliminacion_remitente = None
        elif usuario == self.destinatario:
            self.eliminado_por_destinatario = False
            self.fecha_eliminacion_destinatario = None
        else:
            raise ValueError("El usuario no es parte de esta conversación")
        self.save()

    def esta_eliminado_para(self, usuario):
        if usuario == self.remitente:
            return self.eliminado_por_remitente
        elif usuario == self.destinatario:
            return self.eliminado_por_destinatario
        return True

    @classmethod
    def get_visibles_para_usuario(cls, usuario):
        return cls.objects.filter(
            Q(remitente=usuario, eliminado_por_remitente=False) |
            Q(destinatario=usuario, eliminado_por_destinatario=False)
        ).distinct()


# ============================================
# 19. REUNIONES
# ============================================

class Reunion(models.Model):
    ESTADO_CHOICES = [
        ('programada', 'Programada'),
        ('completada', 'Completada'),
        ('cancelada', 'Cancelada'),
    ]

    idReunion = models.AutoField(primary_key=True, db_column='id')
    tutor = models.ForeignKey(Usuario, on_delete=models.CASCADE, related_name='reuniones_tutor', db_column='tutor_id')
    estudiante = models.ForeignKey(Estudiante, on_delete=models.CASCADE, db_column='estudiante_id', related_name='reuniones')
    titulo = models.CharField(max_length=200, db_column='titulo')
    descripcion = models.TextField(blank=True, null=True, db_column='descripcion')
    fecha_programada = models.DateTimeField(db_column='fecha_programada')
    duracion = models.IntegerField(default=60, db_column='duracion')
    estado = models.CharField(max_length=20, choices=ESTADO_CHOICES, default='programada', db_column='estado')
    ubicacion = models.CharField(max_length=200, blank=True, null=True, db_column='ubicacion')
    notas = models.TextField(blank=True, null=True, db_column='notas')
    idUniversidad = models.ForeignKey(CatalogoUniversidad, on_delete=models.CASCADE, db_column='universidad_id', related_name='reuniones')
    created_at = models.DateTimeField(auto_now_add=True, db_column='created_at')
    updated_at = models.DateTimeField(auto_now=True, db_column='updated_at')

    class Meta:
        db_table = 'reunion'
        ordering = ['fecha_programada']


# ============================================
# 20. NOTIFICACIONES
# ============================================

class Notificacion(models.Model):
    TIPO_CHOICES = [
        ('alerta', 'Alerta'),
        ('recordatorio', 'Recordatorio'),
        ('mensaje', 'Mensaje'),
        ('sistema', 'Sistema'),
    ]

    idNotificacion = models.AutoField(primary_key=True, db_column='id')
    usuario = models.ForeignKey(Usuario, on_delete=models.CASCADE, related_name='notificaciones', db_column='usuario_id')
    titulo = models.CharField(max_length=200, db_column='titulo')
    mensaje = models.TextField(db_column='mensaje')
    tipo = models.CharField(max_length=20, choices=TIPO_CHOICES, default='sistema', db_column='tipo')
    leido = models.BooleanField(default=False, db_column='leido')
    url = models.CharField(max_length=500, blank=True, null=True, db_column='url')
    created_at = models.DateTimeField(auto_now_add=True, db_column='created_at')
    fecha_lectura = models.DateTimeField(blank=True, null=True, db_column='fecha_lectura')

    class Meta:
        db_table = 'notificacion'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.usuario.username} - {self.titulo[:30]}"


# ============================================
# 21. DOCUMENTOS ESTUDIANTE
# ============================================

class DocumentoEstudiante(models.Model):
    TIPO_CHOICES = [
        ('Foto', 'Foto'),
        ('Expediente', 'Expediente'),
        ('Certificado', 'Certificado'),
        ('Otro', 'Otro'),
    ]

    idDocumento = models.AutoField(primary_key=True, db_column='id')
    idEstudiante = models.ForeignKey(Estudiante, on_delete=models.CASCADE, db_column='estudiante_id', related_name='documentos')
    tipo_documento = models.CharField(max_length=20, choices=TIPO_CHOICES, db_column='tipo_documento')
    nombre_archivo = models.CharField(max_length=200, db_column='nombre_archivo')
    archivo = models.BinaryField(blank=True, null=True, db_column='archivo')
    ruta_archivo = models.CharField(max_length=500, blank=True, null=True, db_column='ruta_archivo')
    tamano_bytes = models.BigIntegerField(blank=True, null=True, db_column='tamano_bytes')
    formato = models.CharField(max_length=20, blank=True, null=True, db_column='formato')
    fecha_subida = models.DateTimeField(auto_now_add=True, db_column='fecha_subida')
    descripcion = models.TextField(blank=True, null=True, db_column='descripcion')

    class Meta:
        db_table = 'documento_estudiante'
        ordering = ['-fecha_subida']


# ============================================
# 22. SITUACIÓN LABORAL
# ============================================

class SituacionLaboral(models.Model):
    idSituacion = models.AutoField(primary_key=True, db_column='id')
    idEstudiante = models.ForeignKey(Estudiante, on_delete=models.CASCADE, db_column='estudiante_id', related_name='situaciones_laborales')
    trabaja = models.BooleanField(default=False, db_column='trabaja')
    tipo_trabajo = models.CharField(max_length=100, blank=True, null=True, db_column='tipo_trabajo')
    horas_semanales = models.IntegerField(default=0, db_column='horas_semanales')
    ingreso_mensual = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True, db_column='ingreso_mensual')
    fecha_actualizacion = models.DateField(auto_now=True, db_column='fecha_actualizacion')
    created_at = models.DateTimeField(auto_now_add=True, db_column='created_at')

    class Meta:
        db_table = 'situacion_laboral'


# ============================================
# 23. ESTADO DE SALUD
# ============================================

class EstadoSalud(models.Model):
    idSalud = models.AutoField(primary_key=True, db_column='id')
    idEstudiante = models.ForeignKey(Estudiante, on_delete=models.CASCADE, db_column='estudiante_id', related_name='estados_salud')
    fecha = models.DateField(auto_now_add=True, db_column='fecha')
    salud_fisica = models.IntegerField(choices=[(1, 'Muy mala'), (2, 'Mala'), (3, 'Regular'), (4, 'Buena'), (5, 'Muy buena')], default=3, db_column='salud_fisica')
    salud_mental = models.IntegerField(choices=[(1, 'Muy mala'), (2, 'Mala'), (3, 'Regular'), (4, 'Buena'), (5, 'Muy buena')], default=3, db_column='salud_mental')
    estres = models.IntegerField(choices=[(1, 'Muy bajo'), (2, 'Bajo'), (3, 'Moderado'), (4, 'Alto'), (5, 'Muy alto')], default=3, db_column='estres')
    observaciones = models.TextField(blank=True, null=True, db_column='observaciones')
    created_at = models.DateTimeField(auto_now_add=True, db_column='created_at')

    class Meta:
        db_table = 'estado_salud'


# ============================================
# 24. CONEXIONES LMS
# ============================================

class ConexionLMS(models.Model):
    idConexion = models.AutoField(primary_key=True, db_column='id')
    idEstudiante = models.ForeignKey(Estudiante, on_delete=models.CASCADE, db_column='estudiante_id', related_name='conexiones_lms')
    fecha = models.DateTimeField(db_column='fecha')
    duracion_minutos = models.IntegerField(db_column='duracion_minutos')
    paginas_vistas = models.IntegerField(default=0, db_column='paginas_vistas')
    recursos_descargados = models.IntegerField(default=0, db_column='recursos_descargados')
    foros_participacion = models.IntegerField(default=0, db_column='foros_participacion')
    entregas_realizadas = models.IntegerField(default=0, db_column='entregas_realizadas')
    created_at = models.DateTimeField(auto_now_add=True, db_column='created_at')

    class Meta:
        db_table = 'conexion_lms'
        indexes = [
            models.Index(fields=['idEstudiante', 'fecha']),
        ]


# ============================================
# 25. AUDITORÍA
# ============================================

class Auditoria(models.Model):
    TIPO_CHOICES = [
        ('creacion', 'Creación'),
        ('actualizacion', 'Actualización'),
        ('eliminacion', 'Eliminación'),
        ('login', 'Inicio de Sesión'),
        ('logout', 'Cierre de Sesión'),
        ('exportacion', 'Exportación'),
        ('importacion', 'Importación'),
        ('consulta', 'Consulta'),
        ('cambio_estado', 'Cambio de Estado'),
        ('asignacion', 'Asignación'),
    ]

    id = models.AutoField(primary_key=True, db_column='id')
    usuario = models.ForeignKey(Usuario, on_delete=models.SET_NULL, null=True, db_column='usuario_id', related_name='auditorias')
    accion = models.CharField(max_length=100, db_column='accion')
    tipo = models.CharField(max_length=20, choices=TIPO_CHOICES, default='consulta', db_column='tipo')
    tabla_afectada = models.CharField(max_length=50, blank=True, null=True, db_column='tabla_afectada')
    registro_afectado = models.IntegerField(blank=True, null=True, db_column='registro_afectado')
    detalles = models.JSONField(blank=True, null=True, db_column='detalles')
    ip = models.GenericIPAddressField(blank=True, null=True, db_column='ip')
    user_agent = models.TextField(blank=True, null=True, db_column='user_agent')
    fecha = models.DateTimeField(auto_now_add=True, db_column='fecha')
    created_at = models.DateTimeField(auto_now_add=True, db_column='created_at')
    updated_at = models.DateTimeField(auto_now=True, db_column='updated_at')

    class Meta:
        db_table = 'auditoria'
        ordering = ['-fecha']
        verbose_name = 'Auditoría'
        verbose_name_plural = 'Auditorías'
        indexes = [
            models.Index(fields=['usuario', 'fecha']),
            models.Index(fields=['tipo']),
            models.Index(fields=['tabla_afectada']),
        ]

    def __str__(self):
        return f"{self.usuario.username if self.usuario else 'Sistema'} - {self.accion} - {self.fecha.strftime('%Y-%m-%d %H:%M')}"


# ============================================
# 26. CONFIGURACIÓN DEL SISTEMA
# ============================================

class ConfiguracionSistema(models.Model):
    id = models.AutoField(primary_key=True, db_column='id')
    idUniversidad = models.OneToOneField(
        CatalogoUniversidad,
        on_delete=models.CASCADE,
        db_column='universidad_id',
        related_name='configuracion',
        null=True,
        blank=True
    )

    # Red y sitio
    sitio_nombre = models.CharField(max_length=100, default='RetenScan', db_column='sitio_nombre')
    sitio_url = models.CharField(max_length=200, default='http://localhost:8000', db_column='sitio_url')
    sitio_descripcion = models.TextField(blank=True, null=True, db_column='sitio_descripcion')
    sitio_logo = models.ImageField(upload_to='config/logo/', blank=True, null=True, db_column='sitio_logo')
    sitio_favicon = models.ImageField(upload_to='config/favicon/', blank=True, null=True, db_column='sitio_favicon')

    # Universidad
    nombre_completo = models.CharField(max_length=200, blank=True, null=True, db_column='nombre_completo')
    siglas = models.CharField(max_length=20, blank=True, null=True, db_column='siglas')
    telefono = models.CharField(max_length=50, blank=True, null=True, db_column='telefono')
    email_contacto = models.EmailField(blank=True, null=True, db_column='email_contacto')
    direccion = models.TextField(blank=True, null=True, db_column='direccion')
    sitio_web = models.URLField(blank=True, null=True, db_column='sitio_web')
    fecha_fundacion = models.DateField(blank=True, null=True, db_column='fecha_fundacion')
    rector = models.CharField(max_length=200, blank=True, null=True, db_column='rector')
    mision = models.TextField(blank=True, null=True, db_column='mision')
    vision = models.TextField(blank=True, null=True, db_column='vision')
    valores = models.TextField(blank=True, null=True, db_column='valores')

    # Email
    email_backend = models.CharField(max_length=50, default='smtp', db_column='email_backend')
    email_host = models.CharField(max_length=200, default='smtp.gmail.com', db_column='email_host')
    email_port = models.IntegerField(default=587, db_column='email_port')
    email_use_tls = models.BooleanField(default=True, db_column='email_use_tls')
    email_host_user = models.CharField(max_length=200, blank=True, null=True, db_column='email_host_user')
    email_host_password = models.CharField(max_length=200, blank=True, null=True, db_column='email_host_password')
    email_from = models.CharField(max_length=200, blank=True, null=True, db_column='email_from')
    email_test_recipient = models.EmailField(blank=True, null=True, db_column='email_test_recipient')

    # Twilio / WhatsApp
    twilio_enabled = models.BooleanField(default=False, db_column='twilio_enabled')
    twilio_account_sid = models.CharField(max_length=200, blank=True, null=True, db_column='twilio_account_sid')
    twilio_auth_token = models.CharField(max_length=200, blank=True, null=True, db_column='twilio_auth_token')
    twilio_whatsapp_number = models.CharField(max_length=50, default='whatsapp:+14155238886', db_column='twilio_whatsapp_number')

    # Sesión
    session_timeout_minutes = models.IntegerField(default=240, db_column='session_timeout_minutes')
    session_expire_at_browser_close = models.BooleanField(default=False, db_column='session_expire_at_browser_close')
    limite_intentos_login = models.IntegerField(default=5, db_column='limite_intentos_login')

    # Seguridad
    require_https = models.BooleanField(default=False, db_column='require_https')
    allowed_hosts = models.TextField(default='localhost,127.0.0.1', db_column='allowed_hosts', help_text='Separar por comas')
    mante_sistema = models.BooleanField(default=True, db_column='mante_sistema')
    permite_registro = models.BooleanField(default=True, db_column='permite_registro')

    # Notificaciones
    notificaciones_email = models.BooleanField(default=True, db_column='notificaciones_email')
    notificaciones_whatsapp = models.BooleanField(default=False, db_column='notificaciones_whatsapp')

    # Apariencia
    color_primario = models.CharField(max_length=20, default='#4e73df', db_column='color_primario')
    color_secundario = models.CharField(max_length=20, default='#1cc88a', db_column='color_secundario')
    color_fondo = models.CharField(max_length=20, default='#f8f9fc', db_column='color_fondo')
    mostrar_estadisticas = models.BooleanField(default=True, db_column='mostrar_estadisticas')

    # Caché
    cache_timeout = models.IntegerField(default=300, db_column='cache_timeout')
    cache_max_entries = models.IntegerField(default=1000, db_column='cache_max_entries')

    # Metadatos
    actualizado_por = models.ForeignKey('Usuario', on_delete=models.SET_NULL, null=True, blank=True, db_column='actualizado_por')
    fecha_actualizacion = models.DateTimeField(auto_now=True, db_column='fecha_actualizacion')
    created_at = models.DateTimeField(auto_now_add=True, db_column='created_at')

    class Meta:
        db_table = 'configuracion_sistema'
        verbose_name = 'Configuración del Sistema'
        verbose_name_plural = 'Configuraciones del Sistema'

    def __str__(self):
        if self.idUniversidad:
            return f"Configuración - {self.idUniversidad.nombre}"
        return f"Configuración Global - {self.sitio_nombre}"

    def get_allowed_hosts_list(self):
        return [h.strip() for h in self.allowed_hosts.split(',') if h.strip()]

    @classmethod
    def get_config(cls, universidad_id=None):
        if universidad_id:
            config, created = cls.objects.get_or_create(idUniversidad_id=universidad_id)
        else:
            config, created = cls.objects.get_or_create(idUniversidad__isnull=True)
        return config