# core/views/encuestas/base.py

"""
Funciones auxiliares compartidas para todas las vistas de encuestas
"""
from django.shortcuts import get_object_or_404
from django.core.cache import cache
from django.contrib import messages
from django.db.models import Count, Q, Prefetch
from django.utils import timezone

from ...models import (
    Encuesta, EncuestaAsignacion, EncuestaRespuesta,
    Estudiante, UsuarioEstudiantes
)
from ..base import get_universidad_id, logger


def obtener_encuesta_con_permisos(pk, user, universidad_id):
    """
    Obtiene una encuesta verificando permisos de usuario.
    """
    if user.is_superuser:
        encuesta = get_object_or_404(
            Encuesta.objects.select_related('creador', 'idUniversidad'),
            pk=pk
        )
    else:
        encuesta = get_object_or_404(
            Encuesta.objects.select_related('creador', 'idUniversidad'),
            pk=pk,
            idUniversidad_id=universidad_id
        )
    return encuesta


def obtener_estudiantes_asignados(encuesta, universidad_id, user=None):
    """
    Obtiene los estudiantes asignados a una encuesta.
    """
    if user and user.is_superuser:
        estudiantes = Estudiante.objects.filter(
            estado_academico='Activo'
        ).order_by('idUsuario__last_name')
    else:
        estudiantes = Estudiante.objects.filter(
            estado_academico='Activo',
            idCarrera__idUniversidad_id=universidad_id
        ).order_by('idUsuario__last_name')
    
    asignados_ids = EncuestaAsignacion.objects.filter(
        encuesta=encuesta
    ).values_list('estudiante_id', flat=True)
    
    return estudiantes, list(asignados_ids)


def obtener_estadisticas_respuestas(encuesta):
    """
    Obtiene estadísticas de respuestas de una encuesta.
    """
    respuestas = EncuestaRespuesta.objects.filter(
        asignacion__encuesta=encuesta
    ).select_related(
        'pregunta',
        'opcion',
        'asignacion',
        'asignacion__estudiante',
        'asignacion__estudiante__idUsuario'
    )
    
    estadisticas = {}
    preguntas = encuesta.preguntas.all().prefetch_related('opciones')
    
    for pregunta in preguntas:
        respuestas_pregunta = [r for r in respuestas if r.pregunta_id == pregunta.idPreguntaEncuesta]
        
        if pregunta.tipo in ['opcion_unica', 'opcion_multiple']:
            opciones_count = {}
            for opcion in pregunta.opciones.all():
                count = sum(1 for r in respuestas_pregunta if r.opcion_id == opcion.idOpcion)
                opciones_count[opcion.texto] = count
            estadisticas[pregunta.idPreguntaEncuesta] = opciones_count
        
        elif pregunta.tipo == 'escala':
            valores = [r.respuesta_escala for r in respuestas_pregunta if r.respuesta_escala is not None]
            if valores:
                promedio = sum(valores) / len(valores)
                estadisticas[pregunta.idPreguntaEncuesta] = {
                    'promedio': round(promedio, 2),
                    'total_respuestas': len(valores)
                }
    
    return estadisticas, respuestas


def limpiar_cache_encuesta(encuesta_id):
    """
    Limpia la caché relacionada con una encuesta.
    """
    cache.delete_pattern(f'encuesta_detail_{encuesta_id}_*')
    cache.delete_pattern(f'encuesta_resultados_{encuesta_id}_*')
    cache.delete_pattern(f'encuesta_list_*')
    logger.info(f"Cache limpiada para encuesta {encuesta_id}")


def verificar_permisos_tutor(user, encuesta, universidad_id):
    """
    Verifica si un tutor tiene acceso a una encuesta.
    """
    if user.rol != 'tutor':
        return True
    
    estudiantes_asignados = UsuarioEstudiantes.objects.filter(
        usuario_id=user.id
    ).values_list('estudiante_id', flat=True)
    
    tiene_estudiantes = EncuestaAsignacion.objects.filter(
        encuesta=encuesta,
        estudiante_id__in=estudiantes_asignados
    ).exists()
    
    return tiene_estudiantes

# core/views/encuestas/base.py
# core/views/encuestas/base.py

def obtener_contexto_encuesta_list(user_rol, user, universidad_id):
    """
    Obtiene el contexto para la lista de encuestas según el rol.
    """
    from django.utils import timezone
    ahora = timezone.now()
    
    # ADMIN - Ver todas las encuestas
    if user_rol == 'admin':
        if user.is_superuser:
            encuestas = Encuesta.objects.all().select_related('creador', 'idUniversidad')
        else:
            encuestas = Encuesta.objects.filter(
                idUniversidad_id=universidad_id
            ).select_related('creador', 'idUniversidad')
        
        encuestas = encuestas.annotate(
            total_asignaciones=Count('asignaciones'),
            completadas_count=Count('asignaciones', filter=Q(asignaciones__completada=True))
        )
        titulo = "Todas las Encuestas"
    
    # TUTOR - Ver encuestas de sus estudiantes
    elif user_rol == 'tutor':
        estudiantes_asignados = UsuarioEstudiantes.objects.filter(
            usuario_id=user.id
        ).values_list('estudiante_id', flat=True)
        
        encuestas = Encuesta.objects.filter(
            asignaciones__estudiante_id__in=estudiantes_asignados
        ).distinct().select_related('creador', 'idUniversidad')
        
        encuestas = encuestas.annotate(
            total_asignados=Count(
                'asignaciones',
                filter=Q(asignaciones__estudiante_id__in=estudiantes_asignados)
            ),
            completados=Count(
                'asignaciones',
                filter=Q(
                    asignaciones__estudiante_id__in=estudiantes_asignados,
                    asignaciones__completada=True
                )
            )
        ).order_by('-created_at')
        
        for encuesta in encuestas:
            if encuesta.total_asignados > 0:
                encuesta.progreso_tutor = round((encuesta.completados / encuesta.total_asignados) * 100)
            else:
                encuesta.progreso_tutor = 0
        
        titulo = "Encuestas de Mis Estudiantes"
    
    # PROFESOR - Ver sus encuestas
    elif user_rol == 'profesor':
        encuestas = Encuesta.objects.filter(
            Q(creador=user) | Q(estado='activa'),
            idUniversidad_id=universidad_id
        ).distinct().select_related('creador', 'idUniversidad').order_by('-created_at')
        
        encuestas = encuestas.annotate(
            total_asignaciones=Count('asignaciones'),
            completadas_count=Count('asignaciones', filter=Q(asignaciones__completada=True))
        )
        titulo = "Mis Encuestas"
    
    # ✅ ESTUDIANTE - Ver encuestas asignadas (CORREGIDO)
    else:
        try:
            estudiante = Estudiante.objects.get(idUsuario=user.id)
            
            
            # Obtener TODAS las encuestas asignadas al estudiante
            encuestas_asignadas = EncuestaAsignacion.objects.filter(
                estudiante=estudiante
            ).select_related(
                'encuesta',
                'encuesta__creador'
            ).order_by('-encuesta__created_at')
            
            encuestas = []
            for asignacion in encuestas_asignadas:
                encuesta = asignacion.encuesta
                
                # ✅ Calcular estado completo de la encuesta para el estudiante
                encuesta.completada_por_estudiante = asignacion.completada
                encuesta.fecha_respuesta = asignacion.fecha_respuesta
                
                # ✅ Verificar si la encuesta está activa y dentro del período
                # 🔥 IMPORTANTE: Una encuesta puede ser visible aunque esté 'cerrada'
                # si el estudiante ya la respondió
                esta_activa = encuesta.estado == 'activa'
                dentro_periodo = encuesta.fecha_inicio <= ahora <= encuesta.fecha_fin
                no_respondida = not asignacion.completada
                
                # ✅ El estudiante puede responder si:
                # 1. La encuesta está activa
                # 2. Está dentro del período de fechas
                # 3. No ha respondido aún
                encuesta.puede_responder = esta_activa and dentro_periodo and no_respondida
                
                # ✅ Estado descriptivo para el template
                if asignacion.completada:
                    encuesta.estado_estudiante = 'respondida'
                elif encuesta.estado == 'activa' and dentro_periodo:
                    encuesta.estado_estudiante = 'pendiente'
                elif encuesta.estado == 'activa' and not dentro_periodo:
                    if encuesta.fecha_fin < ahora:
                        encuesta.estado_estudiante = 'vencida'
                    else:
                        encuesta.estado_estudiante = 'no_iniciada'
                elif encuesta.estado == 'borrador':
                    encuesta.estado_estudiante = 'borrador'
                else:
                    encuesta.estado_estudiante = 'cerrada'
                
                # ✅ Información de fechas para el template
                encuesta.fecha_inicio_display = encuesta.fecha_inicio
                encuesta.fecha_fin_display = encuesta.fecha_fin
                
                # ✅ Añadir la encuesta a la lista (SIEMPRE, incluso si está cerrada)
                encuestas.append(encuesta)
            
            titulo = "Mis Encuestas Asignadas"
            
        except Estudiante.DoesNotExist:
            encuestas = []
            titulo = "Mis Encuestas"
    
    return encuestas, titulo