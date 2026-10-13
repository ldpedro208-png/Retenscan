# core/management/commands/seed_data.py
from django.core.management.base import BaseCommand
from django.contrib.auth.hashers import make_password
from django.utils import timezone
from datetime import datetime, timedelta
import random

from core.models import (
    Usuario, Estudiante, CatalogoUniversidad, CatalogoCarrera,
    CatalogoMateria, CatalogoAula, CatalogoTipoBeca,
    CatalogoFactorRiesgo, HistorialAcademico, Asistencia,
    Beca, BecaAsignacion,
    RiesgoEstudiante, Intervencion,
    UsuarioEstudiantes, Encuesta, EncuestaAsignacion,
    EncuestaPregunta, Tarea, TareaPregunta, TareaAsignacion
)


class Command(BaseCommand):
    help = 'Genera datos de prueba multi-tenant para el sistema de retención estudiantil'

    # ============================================
    # CONFIGURACIÓN MULTI-TENANT
    # ============================================
    UNIVERSIDADES_CONFIG = [
        {
            'nombre': 'Universidad Tecnológica del Sur',
            'pais': 'Bolivia',
            'ciudad': 'Santa Cruz',
            'tipo': 'Privada',
            'siglas': 'UTS',
            'admin_username': 'admin_uts',
            'admin_email': 'admin@uts.edu.bo',
            'admin_nombre': 'Admin',
            'admin_apellido': 'UTS',
            'num_estudiantes': 18,
            'num_tutores': 2,
            'num_profesores': 4,
            'carreras': [
                ('Ingeniería de Sistemas', 'ING-SIS', 10),
                ('Ingeniería Civil', 'ING-CIV', 10),
                ('Administración de Empresas', 'ADM', 8),
                ('Psicología', 'PSI', 9),
            ],
        },
        {
            'nombre': 'Universidad de Ciencias Aplicadas',
            'pais': 'Bolivia',
            'ciudad': 'Cochabamba',
            'tipo': 'Privada',
            'siglas': 'UCA',
            'admin_username': 'admin_uca',
            'admin_email': 'admin@uca.edu.bo',
            'admin_nombre': 'Admin',
            'admin_apellido': 'UCA',
            'num_estudiantes': 12,
            'num_tutores': 2,
            'num_profesores': 3,
            'carreras': [
                ('Arquitectura', 'ARQ', 10),
                ('Medicina', 'MED', 12),
                ('Derecho', 'DER', 10),
                ('Biología', 'BIO', 8),
            ],
        },
    ]

    def add_arguments(self, parser):
        parser.add_argument(
            '--seed',
            type=int,
            default=42,
            help='Semilla aleatoria para reproducibilidad (default: 42)'
        )

    def handle(self, *args, **kwargs):
        # ✅ Semilla para reproducibilidad
        random.seed(kwargs.get('seed', 42))

        self.stdout.write('🚀 Generando datos de prueba multi-tenant...')

        # ============================================
        # 1. Catálogos globales
        # ============================================
        self._crear_tipos_beca()
        self._crear_factores_riesgo()
        self._crear_categorias_biblioteca()

        # ============================================
        # 2. Por cada universidad
        # ============================================
        for config in self.UNIVERSIDADES_CONFIG:
            self.stdout.write(f"\n{'=' * 60}")
            self.stdout.write(f"🏫 Procesando: {config['nombre']} ({config['siglas']})")
            self.stdout.write(f"{'=' * 60}")
            self._procesar_universidad(config)

        # ============================================
        # 3. Resumen
        # ============================================
        self._mostrar_resumen()

    # ============================================
    # CATÁLOGOS GLOBALES
    # ============================================

    def _crear_tipos_beca(self):
        """Crea tipos de beca (compartidos por todas las universidades)."""
        tipos = [
            ('Excelencia Académica', 'Para estudiantes con promedio sobresaliente'),
            ('Apoyo Socioeconómico', 'Para estudiantes con necesidad económica'),
            ('Deportiva', 'Para estudiantes destacados en deportes'),
            ('Investigación', 'Para estudiantes en proyectos de investigación'),
            ('Alimentación', 'Apoyo alimenticio para estudiantes'),
            ('Transporte', 'Apoyo en transporte para estudiantes'),
        ]
        for nombre, descripcion in tipos:
            CatalogoTipoBeca.objects.get_or_create(
                nombre=nombre,
                defaults={'descripcion': descripcion}
            )
        self.stdout.write('✅ Tipos de beca globales creados')

    def _crear_factores_riesgo(self):
        """Crea factores de riesgo (compartidos)."""
        factores = [
            ('Bajo rendimiento académico', 1.50, 'Promedio por debajo del mínimo'),
            ('Inasistencia recurrente', 1.30, 'Faltas injustificadas constantes'),
            ('Problemas financieros', 1.40, 'Morosidad o falta de recursos'),
            ('Desmotivación vocacional', 1.20, 'Insatisfacción con la carrera'),
            ('Problemas de salud mental', 1.35, 'Ansiedad o estrés'),
            ('Aislamiento social', 1.10, 'Falta de integración'),
            ('Problemas familiares', 1.25, 'Situaciones familiares adversas'),
            ('Dificultad en materias', 1.45, 'Problemas con materias del semestre'),
        ]
        for nombre, peso, descripcion in factores:
            CatalogoFactorRiesgo.objects.get_or_create(
                nombre=nombre,
                defaults={'peso': peso, 'descripcion': descripcion}
            )
        self.stdout.write('✅ Factores de riesgo globales creados')

    def _crear_categorias_biblioteca(self):
        """Crea categorías de biblioteca (globales)."""
        try:
            from biblioteca.models import CategoriaRecurso
        except ImportError:
            self.stdout.write('   ⚠️ App biblioteca no disponible')
            return

        categorias = [
            ('Libros de Texto', 'Libros académicos principales', 'academico', 'fa-book', 1),
            ('Apuntes y Notas', 'Apuntes de clase y resúmenes', 'academico', 'fa-file-alt', 2),
            ('Papers Científicos', 'Artículos de investigación', 'academico', 'fa-scroll', 3),
            ('Videos Educativos', 'Contenido audiovisual', 'academico', 'fa-video', 4),
            ('Ejercicios Prácticos', 'Prácticas y problemas resueltos', 'academico', 'fa-pencil-ruler', 5),
            ('Motivación', 'Contenido para mantener la motivación', 'apoyo', 'fa-fire', 10),
            ('Hábitos de Estudio', 'Guías para mejorar el estudio', 'apoyo', 'fa-clock', 11),
            ('Salud Mental', 'Recursos de bienestar emocional', 'apoyo', 'fa-heart', 12),
            ('Educación Financiera', 'Manejo de finanzas personales', 'apoyo', 'fa-coins', 13),
            ('Gestión del Tiempo', 'Organización y productividad', 'apoyo', 'fa-calendar-check', 14),
        ]

        total = 0
        for nombre, descripcion, tipo, icono, orden in categorias:
            _, created = CategoriaRecurso.objects.get_or_create(
                nombre=nombre,
                defaults={
                    'descripcion': descripcion,
                    'tipo': tipo,
                    'icono': icono,
                    'orden': orden,
                    'activo': True,
                }
            )
            if created:
                total += 1
        self.stdout.write(f'✅ {total} categorías de biblioteca creadas')

    # ============================================
    # PROCESAR UNA UNIVERSIDAD
    # ============================================

    def _procesar_universidad(self, config):
        """Crea todos los datos de una universidad específica."""

        # --- 1. Universidad ---
        universidad, _ = CatalogoUniversidad.objects.get_or_create(
            nombre=config['nombre'],
            defaults={
                'pais': config['pais'],
                'ciudad': config['ciudad'],
                'tipo': config['tipo'],
            }
        )
        self.stdout.write(f'✅ Universidad: {universidad.nombre}')

        # --- 2. Admin ---
        admin = self._crear_admin_universidad(config, universidad)

        # --- 3. Carreras ---
        carreras = self._crear_carreras(config, universidad)

        # --- 4. Materias ---
        self._crear_materias(carreras)

        # --- 5. Aulas ---
        aulas = self._crear_aulas(config, universidad)

        # --- 6. Tutores ---
        tutores = self._crear_tutores(config, universidad)

        # --- 7. Profesores ---
        profesores = self._crear_profesores(config, universidad)

        # --- 8. Estudiantes ---
        estudiantes = self._crear_estudiantes(config, universidad, carreras)

        # --- 9. Asignar tutores ---
        self._asignar_tutores(estudiantes, tutores)

        # --- 10. Historial ---
        self._crear_historial(estudiantes)

        # --- 11. Asistencias ---
        self._crear_asistencias(estudiantes, aulas)

        # --- 12. Riesgos ---
        estudiantes_riesgo = self._crear_riesgos(estudiantes)

        # --- 13. Intervenciones ---
        self._crear_intervenciones(estudiantes_riesgo, tutores)

        # --- 14. Becas ---
        self._crear_becas(config, universidad, estudiantes)

        # --- 15. Tareas ---
        self._crear_tareas(universidad, carreras, profesores, estudiantes)

        # --- 16. Encuestas ---
        self._crear_encuestas(universidad, admin, estudiantes)

        # --- 17. Recursos de Biblioteca ---
        self._crear_recursos_biblioteca(config, universidad, carreras, profesores)

        # --- 18. Materiales de Apoyo ---
        self._crear_materiales_apoyo(config, universidad)

        # --- 19. Accesos de Biblioteca ---
        self._crear_accesos_biblioteca(estudiantes)

        return {
            'universidad': universidad,
            'estudiantes': estudiantes,
            'tutores': tutores,
            'profesores': profesores,
            'carreras': carreras,
        }

    # ============================================
    # USUARIOS POR UNIVERSIDAD
    # ============================================

    def _crear_admin_universidad(self, config, universidad):
        """Crea el admin de la universidad."""
        admin, created = Usuario.objects.get_or_create(
            username=config['admin_username'],
            defaults={
                'email': config['admin_email'],
                'first_name': config['admin_nombre'],
                'last_name': config['admin_apellido'],
                'password': make_password('admin123'),
                'rol': 'admin',
                'is_active': True,
                'is_staff': True,
                'is_superuser': False,
                'es_admin_universidad': True,
                'idUniversidad': universidad,
                'carnet': f'ADMIN-{config["siglas"]}',
            }
        )
        accion = 'creado' if created else 'ya existe'
        self.stdout.write(f'✅ Admin {accion}: {admin.username} ({universidad.nombre})')
        return admin

    def _crear_tutores(self, config, universidad):
        """Crea tutores para la universidad."""
        nombres_tutores = [
            ('Ana', 'Rojas'), ('Luis', 'Vargas'), ('Elena', 'Díaz'),
            ('Jorge', 'Paredes'), ('Silvia', 'Castro'),
        ]
        siglas_lower = config['siglas'].lower()
        tutores = []
        for i in range(config['num_tutores']):
            nombre, apellido = nombres_tutores[i % len(nombres_tutores)]
            username = f'tutor{siglas_lower}{i+1}'
            email = f'{username}@{siglas_lower}.edu.bo'
            tutor, _ = Usuario.objects.get_or_create(
                username=username,
                defaults={
                    'email': email,
                    'first_name': nombre,
                    'last_name': apellido,
                    'password': make_password('password123'),
                    'rol': 'tutor',
                    'is_active': True,
                    'idUniversidad': universidad,
                    'carnet': f'TUT-{config["siglas"]}-{i+1:03d}',
                }
            )
            tutores.append(tutor)
        self.stdout.write(f'✅ {len(tutores)} tutores creados para {universidad.nombre}')
        return tutores

    def _crear_profesores(self, config, universidad):
        """Crea profesores para la universidad."""
        nombres_profesores = [
            ('Carlos', 'García'), ('Marta', 'López'), ('Juan', 'Martínez'),
            ('Elena', 'Rodríguez'), ('Roberto', 'Sánchez'), ('Patricia', 'Flores'),
        ]
        siglas_lower = config['siglas'].lower()
        profesores = []
        for i in range(config['num_profesores']):
            nombre, apellido = nombres_profesores[i % len(nombres_profesores)]
            username = f'prof{siglas_lower}{i+1}'
            email = f'{username}@{siglas_lower}.edu.bo'
            profesor, _ = Usuario.objects.get_or_create(
                username=username,
                defaults={
                    'email': email,
                    'first_name': nombre,
                    'last_name': apellido,
                    'password': make_password('password123'),
                    'rol': 'profesor',
                    'is_active': True,
                    'idUniversidad': universidad,
                    'carnet': f'PROF-{config["siglas"]}-{i+1:03d}',
                }
            )
            profesores.append(profesor)
        self.stdout.write(f'✅ {len(profesores)} profesores creados para {universidad.nombre}')
        return profesores

    # ============================================
    # CARRERAS Y MATERIAS
    # ============================================

    def _crear_carreras(self, config, universidad):
        """Crea las carreras de la universidad con código prefijado por siglas."""
        carreras = []
        for nombre, codigo_base, duracion in config['carreras']:
            codigo = f"{config['siglas']}-{codigo_base}"
            carrera, _ = CatalogoCarrera.objects.get_or_create(
                idUniversidad=universidad,
                nombre=nombre,
                defaults={
                    'codigo': codigo,
                    'duracion_semestres': duracion,
                }
            )
            carreras.append(carrera)
        self.stdout.write(f'✅ {len(carreras)} carreras creadas para {universidad.nombre}')
        return carreras

    def _crear_materias(self, carreras):
        """Crea materias por carrera."""
        materias_por_carrera = {
            'Ingeniería de Sistemas': [
                ('Programación I', 4, 1), ('Programación II', 4, 2),
                ('Matemáticas I', 4, 1), ('Matemáticas II', 4, 2),
                ('Bases de Datos', 4, 3), ('Redes', 3, 4),
                ('Inteligencia Artificial', 4, 5), ('Proyecto Final', 6, 10),
            ],
            'Ingeniería Civil': [
                ('Cálculo I', 4, 1), ('Física I', 4, 2),
                ('Mecánica de Materiales', 4, 3), ('Hidráulica', 3, 4),
                ('Suelos', 4, 5), ('Estructuras', 4, 6),
            ],
            'Administración de Empresas': [
                ('Contabilidad I', 4, 1), ('Contabilidad II', 4, 2),
                ('Economía', 3, 1), ('Marketing', 4, 3),
                ('Finanzas', 4, 4), ('Recursos Humanos', 3, 5),
            ],
            'Psicología': [
                ('Psicología General', 4, 1), ('Neurociencia', 4, 2),
                ('Psicología Social', 3, 3), ('Psicología Clínica', 4, 4),
            ],
            'Arquitectura': [
                ('Dibujo Técnico', 4, 1), ('Historia de la Arquitectura', 3, 2),
                ('Diseño Arquitectónico I', 4, 3), ('Estructuras I', 4, 4),
                ('Urbanismo', 3, 5),
            ],
            'Medicina': [
                ('Anatomía I', 6, 1), ('Fisiología', 6, 2),
                ('Bioquímica', 5, 2), ('Histología', 5, 3),
                ('Farmacología', 5, 4), ('Patología', 5, 5),
            ],
            'Derecho': [
                ('Introducción al Derecho', 4, 1), ('Derecho Civil I', 4, 2),
                ('Derecho Penal I', 4, 3), ('Derecho Constitucional', 4, 4),
                ('Derecho Laboral', 3, 5),
            ],
            'Biología': [
                ('Biología Celular', 4, 1), ('Genética', 4, 2),
                ('Ecología', 3, 3), ('Microbiología', 4, 4),
                ('Biología Molecular', 4, 5),
            ],
        }

        total = 0
        for carrera in carreras:
            materias = materias_por_carrera.get(carrera.nombre, [])
            for i, (nombre, creditos, semestre) in enumerate(materias, start=1):
                codigo = f"{carrera.codigo}-{semestre:02d}{i:02d}"
                _, created = CatalogoMateria.objects.get_or_create(
                    codigo=codigo,
                    defaults={
                        'idCarrera': carrera,
                        'nombre': nombre,
                        'creditos': creditos,
                        'semestre_curricular': semestre,
                    }
                )
                if created:
                    total += 1
        self.stdout.write(f'✅ {total} materias creadas')

    # ============================================
    # AULAS
    # ============================================

    def _crear_aulas(self, config, universidad):
        """Crea aulas con código prefijado por siglas."""
        aulas_data = [
            ('A-101', 'Aula Principal 101', 30, 'Teoria'),
            ('A-102', 'Aula Principal 102', 35, 'Teoria'),
            ('LAB-1', 'Laboratorio 1', 20, 'Laboratorio'),
            ('LAB-2', 'Laboratorio 2', 25, 'Laboratorio'),
        ]
        aulas = []
        for codigo_base, nombre, capacidad, tipo in aulas_data:
            codigo = f"{config['siglas']}-{codigo_base}"
            aula, _ = CatalogoAula.objects.get_or_create(
                codigo=codigo,
                defaults={
                    'nombre': f'{nombre} ({universidad.nombre})',
                    'capacidad': capacidad,
                    'tipo': tipo,
                    'idUniversidad': universidad,
                }
            )
            aulas.append(aula)
        self.stdout.write(f'✅ {len(aulas)} aulas creadas para {universidad.nombre}')
        return aulas

    # ============================================
    # ESTUDIANTES
    # ============================================

    def _crear_estudiantes(self, config, universidad, carreras):
        """Crea estudiantes para la universidad."""
        nombres = [
            'Juan', 'María', 'Carlos', 'Ana', 'Luis', 'Laura',
            'José', 'Elena', 'David', 'Sofía', 'Pedro', 'Isabel',
            'Diego', 'Carla', 'Javier', 'Marta', 'Daniel', 'Lucía',
        ]
        apellidos = [
            'García', 'López', 'Martínez', 'Pérez', 'Gómez', 'Rodríguez',
            'Fernández', 'Díaz', 'Torres', 'Ramírez', 'Flores', 'Rivera',
            'Ramos', 'Mendoza', 'Cruz', 'Vargas', 'Castillo', 'Vega',
        ]
        estados = ['Activo'] * 8 + ['Inactivo'] + ['Abandonado']

        siglas_lower = config['siglas'].lower()
        estudiantes = []
        for i in range(config['num_estudiantes']):
            nombre = nombres[i % len(nombres)]
            apellido = apellidos[i % len(apellidos)]

            username = f'{nombre.lower()}.{apellido.lower()}{i+1}_{siglas_lower}'
            email = f'{nombre.lower()}.{apellido.lower()}{i+1}@{siglas_lower}.edu.bo'
            carrera = carreras[i % len(carreras)]
            estado = random.choice(estados)
            año_ingreso = random.randint(2022, 2025)
            semestre = random.randint(1, 8)

            usuario, usuario_creado = Usuario.objects.get_or_create(
                username=username,
                defaults={
                    'email': email,
                    'first_name': nombre,
                    'last_name': apellido,
                    'password': make_password('password123'),
                    'rol': 'estudiante',
                    'is_active': True,
                    'idUniversidad': universidad,
                    'carnet': f'EST-{config["siglas"]}-{i+1:04d}',
                }
            )
            if not usuario_creado and not usuario.idUniversidad_id:
                usuario.idUniversidad = universidad
                usuario.save(update_fields=['idUniversidad'])

            estudiante, estudiante_creado = Estudiante.objects.get_or_create(
                idUsuario=usuario,
                defaults={
                    'idCarrera': carrera,
                    'idUniversidad': universidad,
                    'ano_ingreso': año_ingreso,
                    'semestre_actual': semestre,
                    'estado_academico': estado,
                    'nacionalidad': 'Boliviana',
                }
            )
            if not estudiante_creado and estudiante.idUniversidad_id != universidad.idUniversidad:
                estudiante.idUniversidad = universidad
                estudiante.save(update_fields=['idUniversidad'])

            estudiantes.append(estudiante)

        self.stdout.write(f'✅ {len(estudiantes)} estudiantes creados para {universidad.nombre}')
        return estudiantes

    # ============================================
    # RELACIONES Y DATOS DERIVADOS
    # ============================================

    def _asignar_tutores(self, estudiantes, tutores):
        """Asigna estudiantes a tutores en round-robin."""
        if not tutores or not estudiantes:
            return
        total = 0
        for i, estudiante in enumerate(estudiantes):
            tutor = tutores[i % len(tutores)]
            _, created = UsuarioEstudiantes.objects.get_or_create(
                usuario=tutor,
                estudiante=estudiante
            )
            if created:
                total += 1
        self.stdout.write(f'✅ {total} asignaciones tutor-estudiante creadas')

    def _crear_historial(self, estudiantes):
        """Crea historial académico para cada estudiante."""
        semestres = ['2024-1', '2024-2', '2023-1', '2023-2', '2022-1']
        total = 0
        for estudiante in estudiantes:
            materias = CatalogoMateria.objects.filter(idCarrera=estudiante.idCarrera)
            if not materias.exists():
                continue

            num_materias = min(random.randint(3, 6), materias.count())
            materias_seleccionadas = random.sample(list(materias), num_materias)

            for materia in materias_seleccionadas:
                semestre = random.choice(semestres)
                nota = random.uniform(0, 20)
                estado_materia = 'Aprobada' if nota >= 10 else 'Reprobada'

                _, created = HistorialAcademico.objects.get_or_create(
                    idEstudiante=estudiante,
                    idMateria=materia,
                    semestre=semestre,
                    defaults={
                        'nota_final': round(nota, 2),
                        'estado_materia': estado_materia,
                        'intentos': 1 if nota >= 10 else random.randint(1, 3),
                    }
                )
                if created:
                    total += 1
        self.stdout.write(f'✅ {total} registros de historial académico creados')

    def _crear_asistencias(self, estudiantes, aulas):
        """Crea asistencias aleatorias para los estudiantes."""
        if not aulas:
            return
        total = 0
        fecha_inicio = timezone.now().date() - timedelta(days=60)
        fecha_fin = timezone.now().date()

        for estudiante in estudiantes:
            fechas_unicas = set()
            num_asistencias = random.randint(5, 12)
            intentos = 0
            while len(fechas_unicas) < num_asistencias and intentos < 100:
                fecha = fecha_inicio + timedelta(days=random.randint(0, 60))
                if fecha <= fecha_fin:
                    fechas_unicas.add(fecha)
                intentos += 1

            for fecha in fechas_unicas:
                aula = random.choice(aulas)
                presente = random.random() > 0.25

                _, created = Asistencia.objects.get_or_create(
                    idEstudiante=estudiante,
                    idAula=aula,
                    fecha=fecha,
                    defaults={
                        'presente': presente,
                        'justificacion': 'Motivo personal' if not presente and random.random() > 0.5 else None,
                        'hora_entrada': datetime.strptime(f"{random.randint(8, 10)}:{random.randint(0, 59)}", "%H:%M").time(),
                        'hora_salida': datetime.strptime(f"{random.randint(11, 13)}:{random.randint(0, 59)}", "%H:%M").time(),
                    }
                )
                if created:
                    total += 1
        self.stdout.write(f'✅ {total} asistencias creadas')

    def _crear_riesgos(self, estudiantes):
        """Crea riesgos para un 30% de estudiantes."""
        factores = list(CatalogoFactorRiesgo.objects.filter(activo=True))
        if not factores or not estudiantes:
            return []

        num_con_riesgo = max(1, int(len(estudiantes) * 0.3))
        estudiantes_riesgo = random.sample(estudiantes, num_con_riesgo)

        total = 0
        for estudiante in estudiantes_riesgo:
            num_riesgos = random.randint(1, 2)
            factores_sel = random.sample(factores, min(num_riesgos, len(factores)))
            for factor in factores_sel:
                _, created = RiesgoEstudiante.objects.get_or_create(
                    idEstudiante=estudiante,
                    idFactor=factor,
                    defaults={
                        'nivel': random.choice(['Bajo', 'Medio', 'Alto', 'Critico']),
                        'fecha_deteccion': timezone.now().date() - timedelta(days=random.randint(1, 30)),
                        'estado': random.choice(['Activo', 'En seguimiento', 'Resuelto']),
                        'observaciones': f"Riesgo detectado: {factor.nombre}",
                    }
                )
                if created:
                    total += 1
        self.stdout.write(f'✅ {total} riesgos creados')
        return estudiantes_riesgo

    def _crear_intervenciones(self, estudiantes_riesgo, tutores):
        """Crea intervenciones para estudiantes con riesgo."""
        if not estudiantes_riesgo:
            return
        total = 0
        for estudiante in estudiantes_riesgo[:8]:
            for _ in range(random.randint(1, 2)):
                Intervencion.objects.create(
                    idEstudiante=estudiante,
                    idAlerta=None,
                    tipo_intervencion=random.choice(['Tutoría', 'Consejería', 'Académica', 'Psicológica']),
                    fecha_programada=timezone.now() - timedelta(days=random.randint(1, 15)),
                    fecha_realizada=timezone.now() - timedelta(days=random.randint(0, 5)),
                    responsable=random.choice(tutores) if tutores else None,
                    descripcion=f"Intervención para {estudiante.nombre_completo}",
                    efectiva=random.random() > 0.3,
                )
                total += 1
        self.stdout.write(f'✅ {total} intervenciones creadas')

    # ============================================
    # BECAS
    # ============================================

    def _crear_becas(self, config, universidad, estudiantes):
        """Crea becas institucionales y las asigna."""
        tipos_beca = list(CatalogoTipoBeca.objects.all())
        if not tipos_beca:
            return

        siglas = config['siglas']

        becas_creadas = []
        for i, tipo in enumerate(tipos_beca, start=1):
            codigo = f"BECA-{siglas}-{i:02d}"
            beca, _ = Beca.objects.get_or_create(
                codigo=codigo,
                defaults={
                    'nombre': f"Beca {tipo.nombre} - {siglas}",
                    'descripcion': tipo.descripcion,
                    'tipo': tipo,
                    'monto': random.choice([200, 300, 500, 800, 1000]),
                    'porcentaje_cobertura': random.choice([25, 50, 75, 100]),
                    'duracion_meses': random.choice([6, 12, 24]),
                    'cupos_disponibles': random.randint(10, 50),
                    'estado': 'Activa',
                    'idUniversidad': universidad,
                }
            )
            becas_creadas.append(beca)
        self.stdout.write(f'✅ {len(becas_creadas)} becas institucionales creadas para {universidad.nombre}')

        estudiantes_activos = [e for e in estudiantes if e.estado_academico == 'Activo']
        if not estudiantes_activos:
            return
        num_con_beca = max(1, int(len(estudiantes_activos) * 0.25))
        estudiantes_con_beca = random.sample(estudiantes_activos, num_con_beca)

        total_asig = 0
        for i, estudiante in enumerate(estudiantes_con_beca):
            beca = becas_creadas[i % len(becas_creadas)]
            _, created = BecaAsignacion.objects.get_or_create(
                idBeca=beca,
                idEstudiante=estudiante,
                defaults={
                    'fecha_inicio': timezone.now().date() - timedelta(days=random.randint(0, 180)),
                    'fecha_fin': timezone.now().date() + timedelta(days=random.randint(30, 365)),
                    'estado': 'Activa',
                    'renovable': random.choice([True, False]),
                }
            )
            if created:
                total_asig += 1
        self.stdout.write(f'✅ {total_asig} becas asignadas')

    # ============================================
    # TAREAS
    # ============================================

    def _crear_tareas(self, universidad, carreras, profesores, estudiantes):
        """Crea tareas para los profesores."""
        if not profesores:
            return
        total = 0
        for profesor in profesores:
            num_tareas = random.randint(1, 2)
            for i in range(num_tareas):
                carrera = random.choice(carreras)
                tarea, created = Tarea.objects.get_or_create(
                    titulo=f"Tarea {i+1} - {carrera.nombre[:20]} - {profesor.username}",
                    creador=profesor,
                    defaults={
                        'descripcion': f"Tarea de práctica sobre {carrera.nombre}",
                        'instrucciones': f"Resuelve los ejercicios relacionados con {carrera.nombre}",
                        'puntaje_maximo': 100,
                        'idUniversidad': universidad,
                        'fecha_publicacion': timezone.now() - timedelta(days=random.randint(0, 10)),
                        'fecha_limite': timezone.now() + timedelta(days=random.randint(7, 20)),
                        'estado': 'publicada',
                    }
                )
                if created:
                    total += 1
                    preguntas = [
                        ('¿Cuál es el concepto principal?', 'texto', 15),
                        ('Resuelve el siguiente problema', 'texto', 25),
                        ('Explica el proceso paso a paso', 'texto', 20),
                    ]
                    for orden, (p_texto, p_tipo, p_puntaje) in enumerate(preguntas, start=1):
                        TareaPregunta.objects.get_or_create(
                            tarea=tarea,
                            pregunta=p_texto,
                            defaults={'tipo': p_tipo, 'puntaje': p_puntaje, 'orden': orden}
                        )

                estudiantes_carrera = [e for e in estudiantes if e.idCarrera == carrera]
                if estudiantes_carrera:
                    for estudiante in random.sample(estudiantes_carrera, min(3, len(estudiantes_carrera))):
                        TareaAsignacion.objects.get_or_create(
                            tarea=tarea,
                            estudiante=estudiante,
                            defaults={
                                'entregada': random.random() > 0.3,
                                'calificada': random.random() > 0.5,
                                'puntaje_obtenido': random.randint(0, 100),
                            }
                        )
        self.stdout.write(f'✅ {total} tareas creadas')

    # ============================================
    # ENCUESTAS
    # ============================================

    def _crear_encuestas(self, universidad, admin, estudiantes):
        """Crea encuestas para la universidad."""
        encuestas_data = [
            ('Encuesta de Satisfacción', 'Evaluación general'),
            ('Encuesta de Bienestar', 'Evaluación del bienestar estudiantil'),
        ]
        total = 0
        for titulo_base, descripcion in encuestas_data:
            titulo = f"{titulo_base} - {universidad.nombre[:20]}"
            encuesta, created = Encuesta.objects.get_or_create(
                titulo=titulo,
                defaults={
                    'descripcion': descripcion,
                    'creador': admin,
                    'idUniversidad': universidad,
                    'fecha_inicio': timezone.now() - timedelta(days=15),
                    'fecha_fin': timezone.now() + timedelta(days=15),
                    'estado': 'activa',
                }
            )
            if created:
                total += 1
                preguntas = [
                    ('¿Cómo calificas tu experiencia general?', 'escala'),
                    ('¿Recomendarías esta universidad?', 'si_no'),
                    ('¿Qué mejorarías?', 'texto'),
                ]
                for pregunta_texto, tipo in preguntas:
                    EncuestaPregunta.objects.get_or_create(
                        encuesta=encuesta,
                        pregunta=pregunta_texto,
                        defaults={'tipo': tipo}
                    )

                for estudiante in random.sample(estudiantes, min(5, len(estudiantes))):
                    EncuestaAsignacion.objects.get_or_create(
                        encuesta=encuesta,
                        estudiante=estudiante,
                        defaults={'completada': random.random() > 0.3}
                    )
        self.stdout.write(f'✅ {total} encuestas creadas para {universidad.nombre}')

    # ============================================
    # BIBLIOTECA
    # ============================================

    def _crear_recursos_biblioteca(self, config, universidad, carreras, profesores):
        """Crea recursos de biblioteca para la universidad."""
        try:
            from biblioteca.models import RecursoBiblioteca, CategoriaRecurso
        except ImportError:
            self.stdout.write('   ⚠️ App biblioteca no disponible')
            return 0

        categorias = list(CategoriaRecurso.objects.filter(tipo='academico'))
        if not categorias:
            self.stdout.write('   ⚠️ No hay categorías de biblioteca')
            return 0

        recursos_por_carrera = {
            'Ingeniería de Sistemas': [
                ('Introducción a los Algoritmos', 'Cormen, Leiserson', 'libro', 'basico'),
                ('Clean Code', 'Robert C. Martin', 'libro', 'intermedio'),
                ('Design Patterns', 'Erich Gamma', 'libro', 'avanzado'),
                ('Apuntes de Programación I', 'Prof. García', 'apunte', 'basico'),
                ('Bases de Datos: Teoría y Práctica', 'Silberschatz', 'libro', 'intermedio'),
            ],
            'Ingeniería Civil': [
                ('Mecánica de Materiales', 'Beer & Johnston', 'libro', 'intermedio'),
                ('Cálculo de Estructuras', 'Miguel Núñez', 'libro', 'avanzado'),
                ('Hidráulica Aplicada', 'V. Streeter', 'libro', 'intermedio'),
                ('Apuntes de Física I', 'Prof. Martínez', 'apunte', 'basico'),
            ],
            'Administración de Empresas': [
                ('Principios de Marketing', 'Philip Kotler', 'libro', 'basico'),
                ('Contabilidad Financiera', 'Horngren', 'libro', 'intermedio'),
                ('Finanzas Corporativas', 'Ross, Westerfield', 'libro', 'avanzado'),
                ('Guía de Recursos Humanos', 'Prof. López', 'guia', 'basico'),
            ],
            'Psicología': [
                ('Psicología General', 'David Myers', 'libro', 'basico'),
                ('Neurociencia Cognitiva', 'Michael Gazzaniga', 'libro', 'avanzado'),
                ('Apuntes de Psicología Social', 'Prof. Rodríguez', 'apunte', 'intermedio'),
            ],
            'Arquitectura': [
                ('Historia de la Arquitectura Moderna', 'Leonardo Benevolo', 'libro', 'intermedio'),
                ('Diseño Arquitectónico Contemporáneo', 'Francis Ching', 'libro', 'avanzado'),
                ('Dibujo Técnico Arquitectónico', 'Ernst Neufert', 'libro', 'basico'),
            ],
            'Medicina': [
                ('Anatomía de Gray', 'Henry Gray', 'libro', 'intermedio'),
                ('Fisiología Médica', 'Guyton & Hall', 'libro', 'avanzado'),
                ('Bioquímica Clínica', 'Baynes & Dominiczak', 'libro', 'intermedio'),
                ('Apuntes de Histología', 'Prof. Sánchez', 'apunte', 'basico'),
            ],
            'Derecho': [
                ('Introducción al Derecho Civil', 'Luis Díez-Picazo', 'libro', 'basico'),
                ('Derecho Constitucional', 'Jorge Carpizo', 'libro', 'intermedio'),
                ('Derecho Penal Mexicano', 'Francisco Pavón', 'libro', 'avanzado'),
            ],
            'Biología': [
                ('Biología Molecular de la Célula', 'Alberts', 'libro', 'intermedio'),
                ('Genética: Un Enfoque Conceptual', 'Benjamin Pierce', 'libro', 'intermedio'),
                ('Ecología', 'Odum', 'libro', 'basico'),
            ],
        }

        total = 0
        for carrera in carreras:
            recursos = recursos_por_carrera.get(carrera.nombre, [])
            materias_carrera = list(CatalogoMateria.objects.filter(idCarrera=carrera))

            for i, (titulo, autor, tipo, nivel) in enumerate(recursos):
                materia = random.choice(materias_carrera) if materias_carrera else None
                categoria = random.choice(categorias)
                profesor = random.choice(profesores) if profesores else None

                if not profesor:
                    continue

                estado = 'publicado' if random.random() < 0.8 else 'borrador'

                try:
                    recurso, created = RecursoBiblioteca.objects.get_or_create(
                        titulo=titulo,
                        idUniversidad=universidad,
                        defaults={
                            'idMateria': materia,
                            'idCategoria': categoria,
                            'subido_por': profesor,
                            'autor': autor,
                            'anio_publicacion': random.randint(2010, 2024),
                            'descripcion': f"Recurso académico para {carrera.nombre}",
                            'tipo': tipo,
                            'estado': estado,
                            'destacado': random.random() < 0.2,
                            'es_obligatorio': random.random() < 0.3,
                            'nivel_dificultad': nivel,
                            'total_vistas': random.randint(10, 200) if estado == 'publicado' else 0,
                            'total_descargas': random.randint(5, 80) if estado == 'publicado' else 0,
                            'promedio_calificacion': round(random.uniform(3.5, 5.0), 2) if estado == 'publicado' else 0,
                        }
                    )
                    if created:
                        total += 1
                except Exception as e:
                    pass

        self.stdout.write(f'✅ {total} recursos de biblioteca creados para {universidad.nombre}')
        return total

    def _crear_materiales_apoyo(self, config, universidad):
        """Crea materiales de apoyo para la universidad."""
        try:
            from biblioteca.models import MaterialApoyo
        except ImportError:
            return 0

        factores = list(CatalogoFactorRiesgo.objects.filter(activo=True))

        # ✅ Buscar admin de la universidad como creador
        admin = Usuario.objects.filter(
            rol='admin',
            idUniversidad=universidad
        ).first()
        
        if not admin:
            self.stdout.write(f'   ⚠️ No hay admin para {universidad.nombre}, saltando materiales')
            return 0

        materiales_data = [
            ('Cómo mantener la motivación en los estudios', 'motivacional', None),
            ('Superando el miedo al fracaso académico', 'motivacional', None),
            ('Tu historia de éxito empieza hoy', 'motivacional', None),
            ('Técnicas de estudio Pomodoro', 'habitos', None),
            ('Cómo tomar apuntes efectivos', 'habitos', None),
            ('Construyendo hábitos de estudio diarios', 'habitos', None),
            ('Manejo del estrés académico', 'salud_mental', 'Problemas de salud mental'),
            ('Mindfulness para estudiantes', 'salud_mental', 'Problemas de salud mental'),
            ('Cómo combatir la ansiedad antes de exámenes', 'salud_mental', 'Problemas de salud mental'),
            ('Presupuesto para estudiantes', 'financiero', 'Problemas financieros'),
            ('Cómo ahorrar siendo estudiante', 'financiero', 'Problemas financieros'),
            ('Guía para aprovechar las tutorías', 'tutorias', 'Desmotivación vocacional'),
            ('Gestión del tiempo para estudiantes', 'tiempo', None),
            ('Cómo equilibrar estudio y trabajo', 'tiempo', 'Problemas financieros'),
            ('Cómo recuperar clases perdidas', 'habitos', 'Inasistencia recurrente'),
            ('Estrategias para mejorar tus calificaciones', 'habitos', 'Bajo rendimiento académico'),
            ('Aprendiendo a estudiar mejor', 'habitos', 'Bajo rendimiento académico'),
            ('Cómo manejar problemas familiares durante el estudio', 'salud_mental', 'Problemas familiares'),
            ('Cómo integrarte en la vida universitaria', 'motivacional', 'Aislamiento social'),
            ('Construyendo tu red de apoyo', 'motivacional', 'Aislamiento social'),
            ('Cómo superar materias difíciles', 'tutorias', 'Dificultad en materias'),
        ]

        total = 0
        for titulo, tipo, factor_nombre in materiales_data:
            factor = None
            if factor_nombre:
                factor = next((f for f in factores if f.nombre == factor_nombre), None)

            try:
                material, created = MaterialApoyo.objects.get_or_create(
                    titulo=titulo,
                    idUniversidad=universidad,
                    defaults={
                        'idFactorRiesgo': factor,
                        'tipo': tipo,
                        'descripcion': f'Recurso de {tipo} para estudiantes',
                        'contenido': f'<p>Este es un material de apoyo sobre: {titulo}</p>',
                        'activo': True,
                        'creado_por': admin,   # ✅ FIX: asignar creador
                    }
                )
                if created:
                    total += 1
            except Exception as e:
                pass

        self.stdout.write(f'✅ {total} materiales de apoyo creados para {universidad.nombre}')
        return total
    def _crear_accesos_biblioteca(self, estudiantes):
        """Crea accesos aleatorios de estudiantes a recursos (para métricas)."""
        try:
            from biblioteca.models import RecursoBiblioteca, AccesoRecurso
        except ImportError:
            return 0

        total = 0
        acciones = ['vista', 'descarga', 'lectura_completa', 'favorito']

        for estudiante in estudiantes[:10]:
            recursos = list(RecursoBiblioteca.objects.filter(
                idUniversidad=estudiante.idUniversidad,
                estado='publicado'
            ))

            if not recursos:
                continue

            num_accesos = random.randint(2, 5)
            recursos_sel = random.sample(recursos, min(num_accesos, len(recursos)))

            for recurso in recursos_sel:
                accion = random.choice(acciones)
                try:
                    AccesoRecurso.objects.create(
                        idEstudiante=estudiante,
                        idRecurso=recurso,
                        accion=accion,
                        tiempo_lectura_minutos=random.randint(5, 60) if accion == 'lectura_completa' else 0,
                    )
                    total += 1
                except Exception as e:
                    pass

        self.stdout.write(f'✅ {total} accesos de biblioteca registrados')
        return total

    # ============================================
    # RESUMEN FINAL
    # ============================================

    def _mostrar_resumen(self):
        """Muestra el resumen de todos los datos creados."""
        try:
            from biblioteca.models import RecursoBiblioteca, MaterialApoyo, CategoriaRecurso, AccesoRecurso
            biblioteca_ok = True
        except ImportError:
            biblioteca_ok = False

        try:
            from chat.models import SubjectChatRoom
            chat_ok = True
        except ImportError:
            chat_ok = False

        self.stdout.write(f"\n{'=' * 60}")
        self.stdout.write(self.style.SUCCESS('🎉 DATOS MULTI-TENANT GENERADOS EXITOSAMENTE'))
        self.stdout.write(f"{'=' * 60}")
        self.stdout.write(f"📊 Resumen global:")
        self.stdout.write(f'   - Universidades: {CatalogoUniversidad.objects.count()}')
        self.stdout.write(f'   - Carreras: {CatalogoCarrera.objects.count()}')
        self.stdout.write(f'   - Materias: {CatalogoMateria.objects.count()}')
        self.stdout.write(f'   - Aulas: {CatalogoAula.objects.count()}')
        self.stdout.write(f'   - Usuarios: {Usuario.objects.count()}')
        self.stdout.write(f'   - Estudiantes: {Estudiante.objects.count()}')
        self.stdout.write(f'   - Tutores: {Usuario.objects.filter(rol="tutor").count()}')
        self.stdout.write(f'   - Profesores: {Usuario.objects.filter(rol="profesor").count()}')
        self.stdout.write(f'   - Admins: {Usuario.objects.filter(rol="admin").count()}')
        self.stdout.write(f'   - Becas: {Beca.objects.count()}')
        self.stdout.write(f'   - Asignaciones de beca: {BecaAsignacion.objects.count()}')
        self.stdout.write(f'   - Encuestas: {Encuesta.objects.count()}')
        self.stdout.write(f'   - Tareas: {Tarea.objects.count()}')

        if chat_ok:
            self.stdout.write(f'   - Salas de chat: {SubjectChatRoom.objects.count()}')
        if biblioteca_ok:
            self.stdout.write(f'   - Categorías biblioteca: {CategoriaRecurso.objects.count()}')
            self.stdout.write(f'   - Recursos biblioteca: {RecursoBiblioteca.objects.count()}')
            self.stdout.write(f'   - Materiales de apoyo: {MaterialApoyo.objects.count()}')
            self.stdout.write(f'   - Accesos registrados: {AccesoRecurso.objects.count()}')

        self.stdout.write(f"\n📊 Detalle por universidad:")
        for uni in CatalogoUniversidad.objects.all():
            self.stdout.write(f"\n   🏫 {uni.nombre}:")
            self.stdout.write(f'      - Carreras: {CatalogoCarrera.objects.filter(idUniversidad=uni).count()}')
            self.stdout.write(f'      - Materias: {CatalogoMateria.objects.filter(idCarrera__idUniversidad=uni).count()}')
            self.stdout.write(f'      - Aulas: {CatalogoAula.objects.filter(idUniversidad=uni).count()}')
            self.stdout.write(f'      - Estudiantes: {Estudiante.objects.filter(idUniversidad=uni).count()}')
            self.stdout.write(f'      - Tutores: {Usuario.objects.filter(rol="tutor", idUniversidad=uni).count()}')
            self.stdout.write(f'      - Profesores: {Usuario.objects.filter(rol="profesor", idUniversidad=uni).count()}')
            if biblioteca_ok:
                self.stdout.write(f'      - Recursos biblioteca: {RecursoBiblioteca.objects.filter(idUniversidad=uni).count()}')
                self.stdout.write(f'      - Materiales apoyo: {MaterialApoyo.objects.filter(idUniversidad=uni).count()}')

        self.stdout.write(f"\n🔑 Credenciales de acceso:")
        self.stdout.write(f"   Admin UTS:      admin_uts / admin123")
        self.stdout.write(f"   Admin UCA:      admin_uca / admin123")
        self.stdout.write(f"   Superusuario:   (el que creaste con createsuperuser)")
        self.stdout.write(f"   Profesores UTS: profuts1 / password123, profuts2 / password123...")
        self.stdout.write(f"   Profesores UCA: profuca1 / password123, profuca2 / password123...")
        self.stdout.write(f"   Tutores UTS:    tutoruts1 / password123, tutoruts2 / password123...")
        self.stdout.write(f"   Tutores UCA:    tutoruca1 / password123, tutoruca2 / password123...")
        self.stdout.write(f"   Estudiantes UTS: juan.garcia1_uts / password123...")
        self.stdout.write(f"   Estudiantes UCA: juan.garcia1_uca / password123...")