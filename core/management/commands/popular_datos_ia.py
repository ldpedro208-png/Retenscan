# core/management/commands/popular_datos_ia.py
from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta, datetime
import random

from core.models import (
    Estudiante, ConexionLMS, HorarioEstudiante, 
    SituacionLaboral, EstadoSalud
)


class Command(BaseCommand):
    help = 'Pobla datos de prueba para el sistema IA'

    def handle(self, *args, **options):
        self.stdout.write('🔄 Poblando datos para IA...')
        
        estudiantes = Estudiante.objects.all()[:20]
        
        for estudiante in estudiantes:
            self.crear_conexiones_lms(estudiante)
            self.crear_horario(estudiante)
            self.crear_situacion_laboral(estudiante)
            self.crear_estado_salud(estudiante)
        
        self.stdout.write(self.style.SUCCESS('✅ Datos de IA poblados exitosamente!'))
    
    def crear_conexiones_lms(self, estudiante):
        """Crea conexiones LMS simuladas"""
        for i in range(random.randint(10, 30)):
            ConexionLMS.objects.create(
                idEstudiante=estudiante,
                fecha=timezone.now() - timedelta(days=random.randint(1, 60)),
                duracion_minutos=random.randint(10, 120),
                paginas_vistas=random.randint(5, 50),
                recursos_descargados=random.randint(0, 10),
                foros_participacion=random.randint(0, 5),
                entregas_realizadas=random.randint(0, 3)
            )
    
    def crear_horario(self, estudiante):
        """Crea horario de clases simulado"""
        dias = [1, 2, 3, 4, 5]  # Lunes a Viernes
        for dia in dias:
            HorarioEstudiante.objects.create(
                idEstudiante=estudiante,
                dia_semana=dia,
                hora_inicio=timezone.now().replace(hour=8, minute=0, second=0).time(),
                hora_fin=timezone.now().replace(hour=10, minute=0, second=0).time(),
                materia=f"Materia {random.randint(1, 5)}"
            )
    
    def crear_situacion_laboral(self, estudiante):
        """Crea situación laboral simulada"""
        trabaja = random.choice([True, False])
        SituacionLaboral.objects.create(
            idEstudiante=estudiante,
            trabaja=trabaja,
            tipo_trabajo='Medio tiempo' if trabaja else '',
            horas_semanales=random.randint(10, 30) if trabaja else 0,
            ingreso_mensual=random.randint(500, 2000) if trabaja else 0
        )
    
    def crear_estado_salud(self, estudiante):
        """Crea estado de salud simulado"""
        EstadoSalud.objects.create(
            idEstudiante=estudiante,
            salud_fisica=random.randint(1, 5),
            salud_mental=random.randint(1, 5),
            estres=random.randint(1, 5),
            observaciones='Datos de prueba para IA'
        )