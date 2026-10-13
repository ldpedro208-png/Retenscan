# core/management/commands/enviar_recordatorios.py
from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from core.models import EncuestaAsignacion, TareaAsignacion, Estudiante
from core.services.alert_service import AlertaService

class Command(BaseCommand):
    help = 'Envía recordatorios automáticos de encuestas y tareas pendientes'

    def handle(self, *args, **options):
        self.stdout.write('Enviando recordatorios...')
        
        hoy = timezone.now()
        limite = hoy + timedelta(days=3)  # Recordatorios para lo que vence en 3 días
        
        # Recordatorios de encuestas
        encuestas_pendientes = EncuestaAsignacion.objects.filter(
            completada=False,
            encuesta__fecha_fin__lte=limite,
            encuesta__fecha_fin__gte=hoy
        ).select_related('estudiante', 'encuesta')
        
        for asignacion in encuestas_pendientes:
            AlertaService.alerta_recordatorio_encuesta(
                asignacion.estudiante,
                asignacion.encuesta
            )
        
        # Recordatorios de tareas
        tareas_pendientes = TareaAsignacion.objects.filter(
            entregada=False,
            tarea__fecha_limite__lte=limite,
            tarea__fecha_limite__gte=hoy
        ).select_related('estudiante', 'tarea')
        
        for asignacion in tareas_pendientes:
            AlertaService.alerta_recordatorio_tarea(
                asignacion.estudiante,
                asignacion.tarea
            )
        
        self.stdout.write(f'Recordatorios enviados: {encuestas_pendientes.count() + tareas_pendientes.count()}')