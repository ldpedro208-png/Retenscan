# core/management/commands/crear_datos_prueba.py
from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth.hashers import make_password
from django.db import transaction, connection
from django.utils import timezone
from datetime import datetime, timedelta
import random
import logging
import sys
import codecs

# Configurar encoding para Windows
if sys.platform == 'win32':
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
    sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')

# ✅ CAMBIO: BecaEstudiante → Beca, BecaAsignacion, CatalogoTipoBeca
from core.models import (
    CatalogoUniversidad,
    CatalogoCarrera,
    CatalogoMateria,
    CatalogoAula,
    CatalogoTipoBeca,
    CatalogoFactorRiesgo,
    Usuario,
    Estudiante,
    UsuarioEstudiantes,
    HistorialAcademico,
    Asistencia,
    Beca,
    BecaAsignacion,
    Encuesta,
    EncuestaAsignacion,
    EncuestaPregunta,
    EncuestaOpcion,
    EncuestaRespuesta,
    Tarea,
    TareaAsignacion,
    TareaPregunta,
    TareaOpcion,
    TareaRespuesta,
    Intervencion,
    RiesgoEstudiante,
    Reunion,
    Mensaje,
    Notificacion,
)

logger = logging.getLogger(__name__)

# Intentar importar Faker, si no está disponible, usar datos estáticos
try:
    from faker import Faker
    fake = Faker('es_ES')
    FAKER_AVAILABLE = True
except ImportError:
    FAKER_AVAILABLE = False
    logger.warning("Faker no está instalado. Usando datos estáticos.")


class Command(BaseCommand):
    help = 'Crea datos de prueba realistas para el sistema RetenScan'

    def add_arguments(self, parser):
        parser.add_argument(
            '--students',
            type=int,
            default=50,
            help='Número de estudiantes a crear (default: 50)'
        )
        parser.add_argument(
            '--abandonment-rate',
            type=float,
            default=0.20,
            help='Porcentaje de estudiantes con estado Abandonado (default: 0.20 = 20%%)'
        )
        parser.add_argument(
            '--clean',
            action='store_true',
            help='Eliminar datos existentes antes de crear nuevos'
        )
        parser.add_argument(
            '--seed',
            type=int,
            default=42,
            help='Semilla aleatoria para reproducibilidad (default: 42)'
        )

    def handle(self, *args, **options):
        random.seed(options['seed'])
        if FAKER_AVAILABLE:
            Faker.seed(options['seed'])
        
        self.stdout.write('=' * 60)
        self.stdout.write(self.style.SUCCESS('[START] CREANDO DATOS DE PRUEBA'))
        self.stdout.write('=' * 60)
        self.stdout.write(f'📊 Configuración:')
        self.stdout.write(f'   - Estudiantes: {options["students"]}')
        self.stdout.write(f'   - Tasa de abandono: {options["abandonment_rate"] * 100:.0f}%')
        self.stdout.write('=' * 60)
        
        try:
            with transaction.atomic():
                if options['clean']:
                    self._clean_database()
                
                # Crear datos básicos
                self._create_universities()
                self._create_carreras()
                self._create_materias()
                self._create_aulas()
                self._create_tipos_beca()
                self._create_factores_riesgo()
                
                # Crear usuarios y estudiantes
                self._create_usuarios()
                self._create_estudiantes(options['students'], options['abandonment_rate'])
                
                # Crear relaciones
                self._create_asignaciones_tutor()
                self._create_historial_academico()
                self._create_asistencias()
                self._create_becas()
                self._create_encuestas()
                self._create_tareas()
                self._create_riesgos_intervenciones()
                self._create_mensajes()
                self._create_reuniones()
                self._create_notificaciones()
            
            # Estadísticas finales
            total_estudiantes = Estudiante.objects.count()
            abandonados = Estudiante.objects.filter(estado_academico='Abandonado').count()
            
            self.stdout.write('=' * 60)
            self.stdout.write(self.style.SUCCESS('[OK] DATOS DE PRUEBA CREADOS EXITOSAMENTE'))
            self.stdout.write(f'   - Carreras: {CatalogoCarrera.objects.count()}')
            self.stdout.write(f'   - Materias: {CatalogoMateria.objects.count()}')
            self.stdout.write(f'   - Estudiantes: {total_estudiantes} ({abandonados} abandonados, {abandonados/total_estudiantes*100:.1f}%)')
            self.stdout.write(f'   - Usuarios: {Usuario.objects.count()}')
            self.stdout.write(f'   - Historial Académico: {HistorialAcademico.objects.count()}')
            self.stdout.write(f'   - Asistencias: {Asistencia.objects.count()}')
            self.stdout.write('=' * 60)
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'[ERROR] {str(e)}'))
            logger.error(f"Error creando datos de prueba: {str(e)}", exc_info=True)
            raise CommandError(f'Error creando datos de prueba: {str(e)}')

    def _clean_database(self):
        """Limpia los datos existentes"""
        self.stdout.write('[CLEAN] Limpiando datos existentes...')
        
        # ✅ CAMBIO: BecaEstudiante → BecaAsignacion, Beca
        models_to_clean = [
            TareaRespuesta, TareaAsignacion, TareaPregunta, TareaOpcion, Tarea,
            EncuestaRespuesta, EncuestaAsignacion, EncuestaOpcion, EncuestaPregunta, Encuesta,
            Notificacion, Mensaje, Reunion,
            Intervencion, RiesgoEstudiante,
            BecaAsignacion, Beca,
            Asistencia, HistorialAcademico,
            UsuarioEstudiantes, Estudiante,
            Usuario,
            CatalogoFactorRiesgo, CatalogoTipoBeca, CatalogoAula,
            CatalogoMateria, CatalogoCarrera, CatalogoUniversidad,
        ]
        
        for model in models_to_clean:
            try:
                count = model.objects.count()
                if count > 0:
                    model.objects.all().delete()
                    self.stdout.write(f'   Eliminados {count} registros de {model.__name__}')
            except Exception as e:
                self.stdout.write(f'   ⚠️ Error limpiando {model.__name__}: {str(e)}')

    def _create_universities(self):
        """Crear universidades"""
        universidades_data = [
            {'nombre': 'Universidad Tecnologica del Sur', 'pais': 'Bolivia', 'ciudad': 'Sucre', 'tipo': 'Publica'},
            {'nombre': 'Universidad de Ciencias Aplicadas', 'pais': 'Bolivia', 'ciudad': 'Cochabamba', 'tipo': 'Privada'},
        ]
        
        for data in universidades_data:
            try:
                universidad, created = CatalogoUniversidad.objects.get_or_create(
                    nombre=data['nombre'],
                    defaults={
                        'pais': data['pais'],
                        'ciudad': data['ciudad'],
                        'tipo': data['tipo']
                    }
                )
                if created:
                    self.stdout.write(f'   [UNIVERSITY] Creada: {universidad.nombre}')
            except Exception as e:
                self.stdout.write(f'   ⚠️ Error creando universidad {data["nombre"]}: {str(e)}')

    def _create_carreras(self):
        """Crear carreras"""
        universidad_tec = CatalogoUniversidad.objects.filter(
            nombre='Universidad Tecnologica del Sur'
        ).first()
        universidad_cien = CatalogoUniversidad.objects.filter(
            nombre='Universidad de Ciencias Aplicadas'
        ).first()
        
        if not universidad_tec or not universidad_cien:
            self.stdout.write('   ⚠️ No se encontraron universidades')
            return
        
        carreras = [
            {'idUniversidad': universidad_tec, 'nombre': 'Ingenieria de Sistemas', 'codigo': 'ING-SIS', 'duracion_semestres': 10},
            {'idUniversidad': universidad_tec, 'nombre': 'Administracion de Empresas', 'codigo': 'ADM', 'duracion_semestres': 8},
            {'idUniversidad': universidad_tec, 'nombre': 'Ingenieria Civil', 'codigo': 'ING-CIV', 'duracion_semestres': 10},
            {'idUniversidad': universidad_cien, 'nombre': 'Biologia', 'codigo': 'BIO', 'duracion_semestres': 8},
            {'idUniversidad': universidad_cien, 'nombre': 'Quimica', 'codigo': 'QUI', 'duracion_semestres': 8},
        ]
        
        for data in carreras:
            try:
                carrera, created = CatalogoCarrera.objects.get_or_create(
                    idUniversidad=data['idUniversidad'],
                    nombre=data['nombre'],
                    defaults={
                        'codigo': data['codigo'],
                        'duracion_semestres': data['duracion_semestres']
                    }
                )
                if created:
                    self.stdout.write(f'   [CARRERA] Creada: {carrera.nombre}')
            except Exception as e:
                self.stdout.write(f'   ⚠️ Error creando carrera {data["nombre"]}: {str(e)}')

    def _create_materias(self):
        """Crear materias"""
        carreras = CatalogoCarrera.objects.all()
        materias_creadas = 0
        
        materias_por_carrera = {
            'Ingenieria de Sistemas': [
                ('Programacion I', 4, 1), ('Programacion II', 4, 2),
                ('Base de Datos', 4, 3), ('Redes', 3, 4),
                ('Sistemas Operativos', 4, 5), ('Ingenieria de Software', 4, 6),
                ('Inteligencia Artificial', 4, 7), ('Seguridad Informatica', 3, 8),
            ],
            'Administracion de Empresas': [
                ('Contabilidad I', 3, 1), ('Marketing', 3, 2),
                ('Gestion de Proyectos', 3, 3), ('Finanzas', 3, 4),
                ('Recursos Humanos', 3, 5), ('Estrategia Empresarial', 3, 6),
            ],
            'Ingenieria Civil': [
                ('Calculo I', 4, 1), ('Fisica I', 4, 2),
                ('Mecanica de Materiales', 4, 3), ('Hidraulica', 3, 4),
                ('Suelos', 4, 5), ('Estructuras', 4, 6),
            ],
            'Biologia': [
                ('Biologia Celular', 3, 1), ('Genetica', 3, 2),
                ('Ecologia', 3, 3), ('Microbiologia', 3, 4),
                ('Biologia Molecular', 3, 5), ('Zoologia', 3, 6),
            ],
            'Quimica': [
                ('Quimica General', 3, 1), ('Quimica Organica', 3, 2),
                ('Quimica Inorganica', 3, 3), ('Analisis Quimico', 3, 4),
                ('Bioquimica', 3, 5), ('Quimica Ambiental', 3, 6),
            ],
        }
        
        for carrera in carreras:
            materias_list = materias_por_carrera.get(carrera.nombre, [])
            for nombre, creditos, semestre in materias_list:
                try:
                    _, created = CatalogoMateria.objects.get_or_create(
                        idCarrera=carrera,
                        nombre=nombre,
                        defaults={
                            'creditos': creditos,
                            'semestre_curricular': semestre,
                            'codigo': f"{carrera.codigo}-{semestre}{nombre[:2].upper()}" if carrera.codigo else None
                        }
                    )
                    if created:
                        materias_creadas += 1
                except Exception as e:
                    self.stdout.write(f'   ⚠️ Error creando materia {nombre}: {str(e)}')
        
        self.stdout.write(f'   [MATERIAS] {materias_creadas} creadas')

    def _create_aulas(self):
        """Crear aulas"""
        aulas = [
            ('A-101', 'Aula Principal 101', 30, 'Teoria'),
            ('A-102', 'Aula Principal 102', 35, 'Teoria'),
            ('A-103', 'Aula Principal 103', 40, 'Teoria'),
            ('LAB-1', 'Laboratorio Sistemas', 20, 'Laboratorio'),
            ('LAB-2', 'Laboratorio Quimica', 25, 'Laboratorio'),
            ('TALLER-1', 'Taller Construccion', 15, 'Taller'),
        ]
        
        for codigo, nombre, capacidad, tipo in aulas:
            try:
                _, created = CatalogoAula.objects.get_or_create(
                    codigo=codigo,
                    defaults={
                        'nombre': nombre,
                        'capacidad': capacidad,
                        'tipo': tipo
                    }
                )
                if created:
                    self.stdout.write(f'   [AULA] Creada: {nombre}')
            except Exception as e:
                self.stdout.write(f'   ⚠️ Error creando aula {nombre}: {str(e)}')

    def _create_tipos_beca(self):
        """Crear tipos de beca"""
        tipos = [
            ('Excelencia Academica', 'Para estudiantes con promedio sobresaliente'),
            ('Apoyo Socioeconomico', 'Para estudiantes con necesidad economica'),
            ('Deportiva', 'Para estudiantes destacados en deportes'),
            ('Investigacion', 'Para estudiantes que participan en investigacion'),
            ('Intercambio', 'Para estudiantes que hacen intercambio academico'),
        ]
        
        for nombre, descripcion in tipos:
            try:
                _, created = CatalogoTipoBeca.objects.get_or_create(
                    nombre=nombre,
                    defaults={'descripcion': descripcion}
                )
                if created:
                    self.stdout.write(f'   [BECA] Tipo creado: {nombre}')
            except Exception as e:
                self.stdout.write(f'   ⚠️ Error creando tipo beca {nombre}: {str(e)}')

    def _create_factores_riesgo(self):
        """Crear factores de riesgo"""
        factores = [
            ('Bajo rendimiento academico', 1.5, 'Promedio por debajo del minimo'),
            ('Inasistencia recurrente', 1.3, 'Faltas injustificadas constantes'),
            ('Problemas financieros', 1.4, 'Morosidad en pagos'),
            ('Problemas de salud mental', 1.6, 'Ansiedad, depresion o estres'),
            ('Falta de apoyo social', 1.2, 'Aislamiento o falta de red de apoyo'),
            ('Sobrecarga laboral', 1.3, 'Trabaja mas de 30 horas semanales'),
        ]
        
        for nombre, peso, descripcion in factores:
            try:
                _, created = CatalogoFactorRiesgo.objects.get_or_create(
                    nombre=nombre,
                    defaults={
                        'peso': peso,
                        'descripcion': descripcion,
                        'activo': True
                    }
                )
                if created:
                    self.stdout.write(f'   [RIESGO] Factor creado: {nombre}')
            except Exception as e:
                self.stdout.write(f'   ⚠️ Error creando factor {nombre}: {str(e)}')

    def _create_usuarios(self):
        """Crear usuarios básicos"""
        universidad_tec = CatalogoUniversidad.objects.filter(
            nombre='Universidad Tecnologica del Sur'
        ).first()
        
        if not universidad_tec:
            self.stdout.write('   ⚠️ No se encontró universidad para usuarios')
            return
        
        usuarios_data = [
            {'username': 'admin', 'email': 'admin@test.com', 'first_name': 'Admin', 'last_name': 'Sistema', 'rol': 'admin', 'is_staff': True, 'is_superuser': True},
            {'username': 'profesor1', 'email': 'profesor1@test.com', 'first_name': 'Carlos', 'last_name': 'Perez', 'rol': 'profesor'},
            {'username': 'profesor2', 'email': 'profesor2@test.com', 'first_name': 'Maria', 'last_name': 'Lopez', 'rol': 'profesor'},
            {'username': 'profesor3', 'email': 'profesor3@test.com', 'first_name': 'Jose', 'last_name': 'Garcia', 'rol': 'profesor'},
            {'username': 'tutor1', 'email': 'tutor1@test.com', 'first_name': 'Luis', 'last_name': 'Rojas', 'rol': 'tutor'},
            {'username': 'tutor2', 'email': 'tutor2@test.com', 'first_name': 'Elena', 'last_name': 'Diaz', 'rol': 'tutor'},
            {'username': 'tutor3', 'email': 'tutor3@test.com', 'first_name': 'Ana', 'last_name': 'Torres', 'rol': 'tutor'},
        ]
        
        for data in usuarios_data:
            try:
                usuario, created = Usuario.objects.get_or_create(
                    username=data['username'],
                    defaults={
                        'email': data['email'],
                        'first_name': data['first_name'],
                        'last_name': data['last_name'],
                        'password': make_password('123456'),
                        'rol': data['rol'],
                        'idUniversidad': universidad_tec,
                        'is_active': True,
                        'is_staff': data.get('is_staff', False),
                        'is_superuser': data.get('is_superuser', False),
                        'cambiar_password': False,
                        'notificaciones_email': True,
                        'notificaciones_whatsapp': False,
                    }
                )
                if created:
                    self.stdout.write(f'   [USER] Creado: {data["username"]} ({data["rol"]})')
            except Exception as e:
                self.stdout.write(f'   ⚠️ Error creando usuario {data["username"]}: {str(e)}')

    def _create_estudiantes(self, count, abandonment_rate):
        """Crear estudiantes con una tasa específica de abandono."""
        universidad_tec = CatalogoUniversidad.objects.filter(
            nombre='Universidad Tecnologica del Sur'
        ).first()
        universidad_cien = CatalogoUniversidad.objects.filter(
            nombre='Universidad de Ciencias Aplicadas'
        ).first()
        
        if not universidad_tec or not universidad_cien:
            self.stdout.write('   ⚠️ No hay universidades para estudiantes')
            return
        
        carreras = list(CatalogoCarrera.objects.all())
        if not carreras:
            self.stdout.write('   ⚠️ No hay carreras para estudiantes')
            return
        
        estudiantes_creados = 0
        
        nombres = ['Juan', 'Maria', 'Carlos', 'Ana', 'Luis', 'Laura', 'Jose', 'Elena', 'David', 'Sofia',
                   'Pedro', 'Isabel', 'Diego', 'Carla', 'Javier', 'Marta', 'Daniel', 'Lucia', 'Pablo', 'Natalia',
                   'Carmen', 'Roberto', 'Patricia', 'Alejandro', 'Sofia', 'Manuel', 'Elena', 'Ricardo', 'Silvia', 'Antonio']
        apellidos = ['Garcia', 'Lopez', 'Martinez', 'Perez', 'Gomez', 'Rodriguez', 'Fernandez', 'Diaz', 'Torres', 'Ramirez',
                     'Flores', 'Rivera', 'Ramos', 'Mendoza', 'Cruz', 'Vargas', 'Castillo', 'Vega', 'Reyes', 'Vasquez']
        
        num_abandonados = int(count * abandonment_rate)
        num_activos = count - num_abandonados
        
        self.stdout.write(f'   📊 Creando {count} estudiantes: {num_activos} activos, {num_abandonados} abandonados')
        
        for i in range(num_activos):
            self._crear_estudiante_unico(i, nombres, apellidos, carreras, 'Activo', estudiantes_creados)
            estudiantes_creados += 1
        
        for i in range(num_abandonados):
            self._crear_estudiante_unico(i + num_activos, nombres, apellidos, carreras, 'Abandonado', estudiantes_creados, es_abandono=True)
            estudiantes_creados += 1
        
        self.stdout.write(f'   [STUDENTS] {estudiantes_creados} estudiantes creados')

    def _crear_estudiante_unico(self, idx, nombres, apellidos, carreras, estado, total_creados, es_abandono=False):
        """Crea un estudiante individual con características específicas"""
        nombre = random.choice(nombres)
        apellido = random.choice(apellidos)
        apellido2 = random.choice(apellidos)
        username = f'estudiante{idx+1}'
        email = f'estudiante{idx+1}@test.com'
        carrera = random.choice(carreras)
        
        if es_abandono:
            ano_ingreso = random.randint(2018, 2023)
            semestre_actual = random.randint(2, 8)
            semestre_actual = min(semestre_actual, (2024 - ano_ingreso) * 2)
            semestre_actual = max(1, semestre_actual)
            estado_final = 'Abandonado'
        else:
            ano_ingreso = random.randint(2022, 2026)
            semestre_actual = min(random.randint(1, 8), (2026 - ano_ingreso) * 2 + 1)
            semestre_actual = max(1, semestre_actual)
            estado_final = random.choices(['Activo', 'Activo', 'Activo', 'Activo', 'Inactivo'], weights=[80, 80, 80, 80, 20])[0]
        
        try:
            usuario, _ = Usuario.objects.get_or_create(
                username=username,
                defaults={
                    'email': email,
                    'first_name': nombre,
                    'last_name': f"{apellido} {apellido2}",
                    'password': make_password('123456'),
                    'rol': 'estudiante',
                    'idUniversidad': carrera.idUniversidad,
                    'is_active': True,
                    'cambiar_password': False,
                    'notificaciones_email': True,
                    'notificaciones_whatsapp': random.choice([True, False]),
                }
            )
            
            # ✅ Estudiante tiene FK a Usuario y a Carrera, y usa `estado_academico`
            estudiante, created = Estudiante.objects.get_or_create(
                idUsuario=usuario,
                defaults={
                    'idCarrera': carrera,
                    'idUniversidad': carrera.idUniversidad,
                    'ano_ingreso': ano_ingreso,
                    'semestre_actual': semestre_actual,
                    'estado_academico': estado_final,
                    'nacionalidad': random.choice(['Boliviana', 'Peruana', 'Chilena', 'Argentina']),
                    'direccion': f"Calle {random.randint(1, 100)} Nro {random.randint(100, 999)}",
                    'telefono_emergencia': f'666-{2000+idx:04d}',
                    'contacto_emergencia_nombre': f"Familiar de {nombre}",
                }
            )
            if created and es_abandono:
                self._crear_riesgos_para_abandono(estudiante)
                    
        except Exception as e:
            self.stdout.write(f'   ⚠️ Error creando estudiante {idx+1}: {str(e)}')

    def _crear_riesgos_para_abandono(self, estudiante):
        """Crea riesgos automáticos para estudiantes abandonados"""
        factores = CatalogoFactorRiesgo.objects.filter(activo=True)
        if not factores:
            return
        
        num_factores = random.randint(2, 4)
        factores_seleccionados = random.sample(list(factores), min(num_factores, len(factores)))
        
        for factor in factores_seleccionados:
            nivel = random.choices(['Medio', 'Alto', 'Critico'], weights=[30, 50, 20])[0]
            
            try:
                RiesgoEstudiante.objects.create(
                    idEstudiante=estudiante,
                    idFactor=factor,
                    nivel=nivel,
                    puntaje=random.uniform(50, 95),
                    fecha_deteccion=timezone.now().date() - timedelta(days=random.randint(30, 180)),
                    estado='Resuelto' if random.random() > 0.3 else 'Activo',
                    observaciones=f"Riesgo crítico detectado: {factor.nombre}"
                )
            except Exception as e:
                pass

    def _create_asignaciones_tutor(self):
        """Asignar estudiantes a tutores"""
        tutores = Usuario.objects.filter(rol='tutor')
        estudiantes = Estudiante.objects.all()
        
        if not tutores or not estudiantes:
            return
        
        asignaciones = 0
        for i, estudiante in enumerate(estudiantes):
            tutor = tutores[i % len(tutores)]
            try:
                _, created = UsuarioEstudiantes.objects.get_or_create(
                    usuario=tutor,
                    estudiante=estudiante
                )
                if created:
                    asignaciones += 1
            except Exception as e:
                pass
        
        self.stdout.write(f'   [TUTOR] {asignaciones} asignaciones creadas')

    def _create_historial_academico(self):
        """Crear historial académico con datos realistas"""
        estudiantes = Estudiante.objects.all()
        total_creados = 0
        
        for estudiante in estudiantes:
            es_abandonado = estudiante.estado_academico == 'Abandonado'
            materias = CatalogoMateria.objects.filter(idCarrera=estudiante.idCarrera)
            
            if not materias:
                continue
            
            if es_abandonado:
                num_materias = random.randint(3, 8)
            else:
                num_materias = random.randint(2, 6)
            
            num_materias = min(num_materias, len(materias))
            materias_seleccionadas = random.sample(list(materias), num_materias)
            
            for materia in materias_seleccionadas:
                semestre_ano = 2022 + random.randint(0, 3)
                semestre_num = random.choice(['I', 'II'])
                semestre = f"{semestre_ano}-{semestre_num}"
                
                if es_abandonado:
                    es_aprobada = random.random() < 0.4
                    if es_aprobada:
                        nota = random.uniform(51, 70)
                        estado = 'Aprobada'
                    else:
                        rand_val = random.random()
                        if rand_val < 0.5:
                            nota = random.uniform(0, 50)
                            estado = 'Reprobada'
                        elif rand_val < 0.8:
                            nota = None
                            estado = 'Retirada'
                        else:
                            nota = None
                            estado = 'Cursando'
                else:
                    es_aprobada = random.random() < 0.75
                    if es_aprobada:
                        nota = random.uniform(51, 100)
                        estado = 'Aprobada'
                    else:
                        nota = random.uniform(0, 50)
                        estado = 'Reprobada'
                
                try:
                    historial, created = HistorialAcademico.objects.get_or_create(
                        idEstudiante=estudiante,
                        idMateria=materia,
                        semestre=semestre,
                        defaults={
                            'nota_final': round(nota, 2) if nota else None,
                            'estado_materia': estado,
                            'intentos': random.randint(1, 2) if es_abandonado else 1,
                            'fecha_registro': timezone.now().date() - timedelta(days=random.randint(30, 365))
                        }
                    )
                    if created:
                        total_creados += 1
                except Exception as e:
                    pass
        
        self.stdout.write(f'   [HISTORIAL] {total_creados} registros creados')

    def _create_asistencias(self):
        """Crear asistencias con datos realistas"""
        estudiantes = Estudiante.objects.all()
        aulas = CatalogoAula.objects.all()
        
        if not aulas:
            self.stdout.write('   ⚠️ No hay aulas para asistencias')
            return
        
        total_creados = 0
        
        for estudiante in estudiantes:
            es_abandonado = estudiante.estado_academico == 'Abandonado'
            
            if es_abandonado:
                num_asistencias = random.randint(5, 15)
                porcentaje_presente = random.uniform(0.4, 0.6)
            else:
                num_asistencias = random.randint(15, 40)
                porcentaje_presente = random.uniform(0.7, 0.9)
            
            aula = random.choice(aulas)
            
            for _ in range(num_asistencias):
                fecha = timezone.now().date() - timedelta(days=random.randint(1, 180))
                presente = random.random() < porcentaje_presente
                # ✅ CAMBIO: justificacion es TextField, no BooleanField
                justificacion = '' if presente else ('Motivo familiar' if random.random() < 0.3 else '')
                
                try:
                    _, created = Asistencia.objects.get_or_create(
                        idEstudiante=estudiante,
                        idAula=aula,
                        fecha=fecha,
                        defaults={
                            'presente': presente,
                            'justificacion': justificacion or None,
                            'hora_entrada': (timezone.now() + timedelta(hours=random.randint(6, 10))).time(),
                            'hora_salida': (timezone.now() + timedelta(hours=random.randint(10, 14))).time(),
                        }
                    )
                    if created:
                        total_creados += 1
                except Exception as e:
                    pass
        
        self.stdout.write(f'   [ASISTENCIA] {total_creados} registros creados')

    def _create_becas(self):
        """
        ✅ CAMBIO: Crear Becas institucionales y luego asignarlas con BecaAsignacion.
        """
        universidad_tec = CatalogoUniversidad.objects.filter(
            nombre='Universidad Tecnologica del Sur'
        ).first()
        tipos = CatalogoTipoBeca.objects.all()
        
        if not universidad_tec or not tipos.exists():
            self.stdout.write('   ⚠️ No hay universidad o tipos para becas')
            return
        
        # 1. Crear Becas institucionales (una por cada tipo)
        becas_creadas = []
        for i, tipo in enumerate(tipos):
            try:
                beca, created = Beca.objects.get_or_create(
                    codigo=f"BECA-{tipo.nombre[:6].upper()}-{i+1:02d}",
                    defaults={
                        'nombre': f"Beca {tipo.nombre}",
                        'descripcion': tipo.descripcion,
                        'tipo': tipo,
                        'monto': random.choice([200, 300, 500, 800, 1000]),
                        'porcentaje_cobertura': random.choice([25, 50, 75, 100]),
                        'duracion_meses': random.choice([6, 12, 24]),
                        'cupos_disponibles': random.randint(10, 50),
                        'estado': 'Activa',
                        'idUniversidad': universidad_tec,
                    }
                )
                becas_creadas.append(beca)
                if created:
                    self.stdout.write(f'   [BECA] Creada: {beca.nombre}')
            except Exception as e:
                self.stdout.write(f'   ⚠️ Error creando beca {tipo.nombre}: {str(e)}')
        
        # 2. Asignar becas a estudiantes activos
        estudiantes = Estudiante.objects.filter(estado_academico='Activo')
        if not becas_creadas or not estudiantes:
            return
        
        total_asignaciones = 0
        estudiantes_con_beca = random.sample(
            list(estudiantes), 
            min(int(len(estudiantes) * 0.3), len(estudiantes))
        )
        
        for i, estudiante in enumerate(estudiantes_con_beca):
            beca = becas_creadas[i % len(becas_creadas)]
            try:
                _, created = BecaAsignacion.objects.get_or_create(
                    idBeca=beca,
                    idEstudiante=estudiante,
                    defaults={
                        'fecha_inicio': timezone.now().date() - timedelta(days=random.randint(30, 180)),
                        'fecha_fin': timezone.now().date() + timedelta(days=random.randint(90, 365)),
                        'estado': 'Activa',
                        'observaciones': 'Beca asignada por rendimiento academico' if random.random() > 0.5 else None,
                        'renovable': random.choice([True, False]),
                    }
                )
                if created:
                    total_asignaciones += 1
            except Exception as e:
                pass
        
        self.stdout.write(f'   [BECA] {total_asignaciones} becas asignadas')

    def _create_encuestas(self):
        """Crear encuestas"""
        universidad_tec = CatalogoUniversidad.objects.filter(
            nombre='Universidad Tecnologica del Sur'
        ).first()
        
        if not universidad_tec:
            return
        
        encuestas_data = [
            {'titulo': 'Encuesta de Satisfaccion Academica', 'descripcion': 'Evalua la satisfaccion con los servicios academicos', 'es_obligatoria': True},
            {'titulo': 'Encuesta de Bienestar Estudiantil', 'descripcion': 'Evalua el bienestar emocional y social', 'es_obligatoria': False},
            {'titulo': 'Encuesta de Satisfaccion de Servicios', 'descripcion': 'Evalua la calidad de los servicios universitarios', 'es_obligatoria': False},
        ]
        
        total_creadas = 0
        for data in encuestas_data:
            try:
                encuesta, created = Encuesta.objects.get_or_create(
                    titulo=data['titulo'],
                    defaults={
                        'descripcion': data['descripcion'],
                        'creador': Usuario.objects.filter(rol='admin').first(),
                        'idUniversidad': universidad_tec,
                        'fecha_inicio': timezone.now() - timedelta(days=30),
                        'fecha_fin': timezone.now() + timedelta(days=60),
                        'es_obligatoria': data['es_obligatoria'],
                        'estado': 'activa',
                    }
                )
                if created:
                    total_creadas += 1
                    
                    preguntas = [
                        ('¿Como calificas la calidad de la enseñanza?', 'escala'),
                        ('¿Recomendarias la universidad a otros?', 'si_no'),
                        ('¿Como calificas los servicios de apoyo?', 'escala'),
                    ]
                    for orden, (pregunta_text, tipo) in enumerate(preguntas, start=1):
                        EncuestaPregunta.objects.create(
                            encuesta=encuesta,
                            pregunta=pregunta_text,
                            tipo=tipo,
                            orden=orden,
                            es_obligatoria=True
                        )
            except Exception as e:
                self.stdout.write(f'   ⚠️ Error creando encuesta {data["titulo"]}: {str(e)}')
        
        self.stdout.write(f'   [ENCUESTA] {total_creadas} encuestas creadas')

    def _create_tareas(self):
        """Crear tareas"""
        universidad_tec = CatalogoUniversidad.objects.filter(
            nombre='Universidad Tecnologica del Sur'
        ).first()
        
        if not universidad_tec:
            return
        
        profesores = Usuario.objects.filter(rol='profesor')
        if not profesores:
            return
        
        tareas = [
            {'titulo': 'Tarea 1 - Programacion', 'descripcion': 'Ejercicios de programacion basica', 'puntaje_maximo': 100},
            {'titulo': 'Tarea 2 - Base de Datos', 'descripcion': 'Consultas SQL avanzadas', 'puntaje_maximo': 100},
            {'titulo': 'Tarea 3 - Redes', 'descripcion': 'Configuracion de redes', 'puntaje_maximo': 100},
            {'titulo': 'Proyecto Final', 'descripcion': 'Proyecto integrador', 'puntaje_maximo': 200},
        ]
        
        total_creadas = 0
        for tarea_data in tareas:
            try:
                tarea, created = Tarea.objects.get_or_create(
                    titulo=tarea_data['titulo'],
                    defaults={
                        'descripcion': tarea_data['descripcion'],
                        'instrucciones': 'Siga las instrucciones detalladas en el material de clase',
                        'puntaje_maximo': tarea_data['puntaje_maximo'],
                        'creador': random.choice(profesores),
                        'idUniversidad': universidad_tec,
                        'fecha_publicacion': timezone.now() - timedelta(days=random.randint(5, 15)),
                        'fecha_limite': timezone.now() + timedelta(days=random.randint(7, 21)),
                        'estado': 'publicada',
                    }
                )
                if created:
                    total_creadas += 1
            except Exception as e:
                self.stdout.write(f'   ⚠️ Error creando tarea {tarea_data["titulo"]}: {str(e)}')
        
        self.stdout.write(f'   [TAREA] {total_creadas} tareas creadas')

    def _create_riesgos_intervenciones(self):
        """Crear riesgos e intervenciones"""
        estudiantes = Estudiante.objects.all()
        factores = CatalogoFactorRiesgo.objects.filter(activo=True)
        
        if not factores:
            return
        
        estudiantes_con_riesgo = random.sample(list(estudiantes), min(int(len(estudiantes) * 0.2), len(estudiantes)))
        
        total_riesgos = 0
        total_intervenciones = 0
        
        for estudiante in estudiantes_con_riesgo:
            num_factores = random.randint(1, 3)
            factores_seleccionados = random.sample(list(factores), min(num_factores, len(factores)))
            
            for factor in factores_seleccionados:
                nivel = random.choices(['Bajo', 'Medio', 'Alto', 'Critico'], weights=[30, 40, 20, 10])[0]
                
                try:
                    riesgo, created = RiesgoEstudiante.objects.get_or_create(
                        idEstudiante=estudiante,
                        idFactor=factor,
                        defaults={
                            'nivel': nivel,
                            'puntaje': random.uniform(20, 90),
                            'fecha_deteccion': timezone.now().date() - timedelta(days=random.randint(1, 60)),
                            'fecha_resolucion': None,
                            'estado': random.choices(['Activo', 'En seguimiento', 'Resuelto'], weights=[50, 30, 20])[0],
                            'observaciones': f"Riesgo detectado por {factor.nombre}",
                        }
                    )
                    if created:
                        total_riesgos += 1
                        
                        if random.random() < 0.5:
                            tipos_intervencion = ['Tutoria', 'Orientacion', 'Academica']
                            Intervencion.objects.create(
                                idEstudiante=estudiante,
                                idAlerta=None,   # ✅ CAMBIO: el campo es idAlerta, no idRiesgo
                                tipo_intervencion=random.choice(tipos_intervencion),
                                fecha_programada=timezone.now() + timedelta(days=random.randint(1, 15)),
                                fecha_realizada=timezone.now() + timedelta(days=random.randint(1, 10)) if random.random() > 0.3 else None,
                                responsable=random.choice(Usuario.objects.filter(rol='tutor')) if Usuario.objects.filter(rol='tutor').exists() else None,
                                descripcion=f"Intervención para {factor.nombre}",
                                efectiva=random.choice([True, False]),
                            )
                            total_intervenciones += 1
                except Exception as e:
                    pass
        
        self.stdout.write(f'   [RIESGO] {total_riesgos} riesgos creados')
        self.stdout.write(f'   [INTERVENCION] {total_intervenciones} intervenciones creadas')

    def _create_mensajes(self):
        """Crear mensajes entre usuarios"""
        usuarios = Usuario.objects.all()
        
        if len(usuarios) < 2:
            return
        
        total_creados = 0
        for i in range(30):
            remitente = random.choice(usuarios)
            destinatarios = [u for u in usuarios if u.id != remitente.id]
            if not destinatarios:
                continue
            destinatario = random.choice(destinatarios)
            
            try:
                _, created = Mensaje.objects.get_or_create(
                    remitente=remitente,
                    destinatario=destinatario,
                    asunto=f"Consulta sobre {random.choice(['tarea', 'examen', 'beca', 'horario'])}",
                    defaults={
                        'contenido': f"Contenido del mensaje aleatorio {i+1}",
                        'leido': random.random() > 0.3,
                        'fecha_envio': timezone.now() - timedelta(days=random.randint(1, 30)),
                        'fecha_lectura': timezone.now() - timedelta(days=random.randint(1, 25)) if random.random() > 0.3 else None,
                    }
                )
                if created:
                    total_creados += 1
            except Exception as e:
                pass
        
        self.stdout.write(f'   [MENSAJE] {total_creados} mensajes creados')

    def _create_reuniones(self):
        """Crear reuniones"""
        tutores = Usuario.objects.filter(rol='tutor')
        estudiantes = Estudiante.objects.all()
        
        if not tutores or not estudiantes:
            return
        
        universidad_tec = CatalogoUniversidad.objects.filter(
            nombre='Universidad Tecnologica del Sur'
        ).first()
        
        if not universidad_tec:
            return
        
        total_creados = 0
        for i in range(20):
            tutor = random.choice(tutores)
            estudiante = random.choice(estudiantes)
            
            try:
                _, created = Reunion.objects.get_or_create(
                    tutor=tutor,
                    estudiante=estudiante,
                    titulo=f"Reunión de seguimiento {i+1}",
                    defaults={
                        'descripcion': 'Reunión para revisar el progreso academico',
                        'fecha_programada': timezone.now() + timedelta(days=random.randint(1, 30)),
                        'duracion': random.choice([30, 45, 60]),
                        'estado': random.choices(['programada', 'completada', 'cancelada'], weights=[60, 30, 10])[0],
                        'ubicacion': random.choice(['Oficina 101', 'Virtual', 'Sala de reuniones']),
                        'idUniversidad': universidad_tec,
                    }
                )
                if created:
                    total_creados += 1
            except Exception as e:
                pass
        
        self.stdout.write(f'   [REUNION] {total_creados} reuniones creadas')

    def _create_notificaciones(self):
        """Crear notificaciones"""
        usuarios = Usuario.objects.all()
        
        if not usuarios:
            return
        
        tipos_notificacion = ['alerta', 'recordatorio', 'mensaje', 'sistema']
        total_creados = 0
        
        for usuario in usuarios:
            for _ in range(random.randint(3, 8)):
                try:
                    _, created = Notificacion.objects.get_or_create(
                        usuario=usuario,
                        titulo=f"Notificación para {usuario.username}",
                        defaults={
                            'mensaje': 'Contenido de la notificación de prueba',
                            'tipo': random.choice(tipos_notificacion),
                            'leido': random.random() > 0.4,
                            'url': f"/dashboard/{random.randint(1, 100)}",
                        }
                    )
                    if created:
                        total_creados += 1
                except Exception as e:
                    pass
        
        self.stdout.write(f'   [NOTIFICACION] {total_creados} notificaciones creadas')