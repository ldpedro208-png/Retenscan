# core/views/dashboard/profesor.py

"""
Dashboard para profesores
"""
from django.shortcuts import render
from django.db.models import Count, Avg, Q, F, Sum
from django.utils import timezone
from django.core.cache import cache
from datetime import timedelta

from ...models import (
    Estudiante, HistorialAcademico, Asistencia, Mensaje,
    Tutor, RiesgoEstudiante, UsuarioEstudiantes, AsignacionTutor
)
from ..base import get_universidad_id
from .base import (
    get_estudiantes_por_usuario,
    obtener_estadisticas_avanzadas_profesor
)

# ✅ Importar funciones de asignación de tutores
from .asignacion_tutores import (
    asignacion_tutores_lista,
    asignacion_tutores_crear,
    asignacion_tutores_individual,
    asignacion_tutores_masiva,
    asignacion_tutores_confirmar,
    asignacion_tutores_cancelar,
    asignacion_tutores_estadisticas,
)


def get_universidad_nombre(universidad_id):
    """Obtiene el nombre de la universidad por su ID."""
    from ...models import CatalogoUniversidad
    if universidad_id:
        try:
            universidad = CatalogoUniversidad.objects.get(idUniversidad=universidad_id)
            return universidad.nombre
        except CatalogoUniversidad.DoesNotExist:
            return "Sin universidad"
    return "Sin universidad"


def dashboard_profesor(request):
    """Dashboard para profesores con todos los gráficos de sus estudiantes."""
    universidad_id = get_universidad_id(request)
    cache_key = f'dashboard_profesor_{universidad_id}_{timezone.now().date()}'

    context = cache.get(cache_key)
    if context:
        context['rol'] = 'profesor'
        return render(request, 'profesor/dashboard_profesor.html', context)

    estudiantes_qs = get_estudiantes_por_usuario(request, include_all=True)
    estudiantes_ids = list(estudiantes_qs.values_list('idEstudiante', flat=True))

    total_estudiantes = estudiantes_qs.count()

    hoy = timezone.now().date()
    asistencias_hoy = Asistencia.objects.filter(
        idEstudiante__in=estudiantes_ids,
        fecha=hoy,
        presente=True
    ).count()
    
    # ============================================
    # ✅ ESTADÍSTICAS DE TUTORES DE LA UNIVERSIDAD
    # ============================================
    
    # 1. Total de tutores activos en la universidad
    total_tutores = Tutor.objects.filter(
        usuario__idUniversidad_id=universidad_id,
        activo=True
    ).count()
    
    # 2. Tutores con estudiantes asignados (usando AsignacionTutor)
    tutores_con_estudiantes = Tutor.objects.filter(
        usuario__idUniversidad_id=universidad_id,
        activo=True,
        estudiantes_asignados__gt=0
    ).count()
    
    # 3. Tutores disponibles (con cupo)
    tutores_disponibles = Tutor.objects.filter(
        usuario__idUniversidad_id=universidad_id,
        activo=True
    ).exclude(
        estudiantes_asignados__gte=F('max_estudiantes')
    ).count()
    
    # 4. Total de estudiantes asignados a tutores (con asignación confirmada)
    total_estudiantes_con_tutor = AsignacionTutor.objects.filter(
        estudiante__idUniversidad_id=universidad_id,
        estado='confirmada'
    ).values('estudiante').distinct().count()
    
    # 5. Porcentaje de estudiantes con tutor
    if total_estudiantes > 0:
        porcentaje_con_tutor = round((total_estudiantes_con_tutor / total_estudiantes) * 100, 1)
    else:
        porcentaje_con_tutor = 0
    
    # 6. Lista de tutores con sus estudiantes (para mostrar en tabla)
    tutores_detalle = Tutor.objects.filter(
        usuario__idUniversidad_id=universidad_id,
        activo=True
    ).select_related('usuario').annotate(
        estudiantes_count=Count('asignaciones', filter=Q(asignaciones__estado='confirmada'))
    ).order_by('usuario__first_name')[:10]
    
    # 7. Distribución de estudiantes por tutor (para gráfico)
    distribucion_tutores = Tutor.objects.filter(
        usuario__idUniversidad_id=universidad_id,
        activo=True
    ).values(
        'usuario__first_name', 
        'usuario__last_name'
    ).annotate(
        total_estudiantes=Sum('estudiantes_asignados')
    ).order_by('-total_estudiantes')[:5]
    
    # Labels para gráfico de distribución
    tutores_distribucion_labels = [
        f"{item['usuario__first_name']} {item['usuario__last_name']}" 
        for item in distribucion_tutores
    ]
    tutores_distribucion_values = [
        item['total_estudiantes'] if item['total_estudiantes'] else 0
        for item in distribucion_tutores
    ]
    
    # 8. Estado de los tutores (activos/inactivos)
    tutores_activos = total_tutores
    tutores_inactivos = Tutor.objects.filter(
        usuario__idUniversidad_id=universidad_id,
        activo=False
    ).count()
    
    # ============================================
    # RENDIMIENTO POR MATERIAS
    # ============================================
    rendimiento_materias = HistorialAcademico.objects.filter(
        idEstudiante__in=estudiantes_ids,
        nota_final__isnull=False
    ).values(
        'idMateria__nombre'
    ).annotate(
        promedio=Avg('nota_final'),
        cantidad=Count('idHistorial')
    ).order_by('-cantidad')[:10]

    materias_labels = [item['idMateria__nombre'][:20] for item in rendimiento_materias]
    materias_values = [float(item['promedio']) if item['promedio'] else 0 for item in rendimiento_materias]
    materias_cantidad = [item['cantidad'] for item in rendimiento_materias]

    # ============================================
    # DISTRIBUCIÓN DE CALIFICACIONES
    # ============================================
    rangos = {
        'Sobresaliente (18-20)': 0,
        'Bueno (14-17)': 0,
        'Regular (10-13)': 0,
        'Bajo (0-9)': 0
    }

    notas = HistorialAcademico.objects.filter(
        idEstudiante__in=estudiantes_ids,
        nota_final__isnull=False
    ).values_list('nota_final', flat=True)

    for nota in notas:
        if nota >= 18:
            rangos['Sobresaliente (18-20)'] += 1
        elif nota >= 14:
            rangos['Bueno (14-17)'] += 1
        elif nota >= 10:
            rangos['Regular (10-13)'] += 1
        else:
            rangos['Bajo (0-9)'] += 1

    # ============================================
    # ASISTENCIAS POR DÍA
    # ============================================
    dias_semana = ['Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes', 'Sábado', 'Domingo']

    asistencias_dias = Asistencia.objects.filter(
        idEstudiante__in=estudiantes_ids,
        presente=True
    ).extra(
        select={'dia_semana': "EXTRACT(DOW FROM fecha)"}
    ).values('dia_semana').annotate(
        cantidad=Count('idAsistencia')
    ).order_by('dia_semana')

    asistencias_por_dia = [0] * 7
    for item in asistencias_dias:
        dia_idx = int(item['dia_semana']) - 1
        if 0 <= dia_idx < 7:
            asistencias_por_dia[dia_idx] = item['cantidad']

    asistencias_por_dia = asistencias_por_dia[1:] + asistencias_por_dia[:1]
    dias_labels = dias_semana

    asistencias_ultimos_dias = []
    for i in range(4, -1, -1):
        fecha = hoy - timedelta(days=i)
        count = Asistencia.objects.filter(
            idEstudiante__in=estudiantes_ids,
            fecha=fecha,
            presente=True
        ).count()
        asistencias_ultimos_dias.append(count)

    # ============================================
    # ESTADÍSTICAS AVANZADAS
    # ============================================
    stats_avanzadas = obtener_estadisticas_avanzadas_profesor(universidad_id, estudiantes_ids, request.user)

    estudiantes_riesgo_ia = stats_avanzadas.get('estudiantes_riesgo_ia', [])
    ia_disponible = stats_avanzadas.get('ia_disponible', False)
    
    # Datos de riesgo por curso (para el template)
    riesgo_por_curso = stats_avanzadas.get('riesgo_por_curso', [])

    if estudiantes_riesgo_ia:
        ia_criticos = sum(1 for e in estudiantes_riesgo_ia if e.get('nivel_riesgo') == 'Crítico')
        ia_altos = sum(1 for e in estudiantes_riesgo_ia if e.get('nivel_riesgo') == 'Alto')
        ia_medios = sum(1 for e in estudiantes_riesgo_ia if e.get('nivel_riesgo') == 'Medio')
        ia_bajos = sum(1 for e in estudiantes_riesgo_ia if e.get('nivel_riesgo') == 'Bajo')
        ia_sin_riesgo = max(0, len(estudiantes_riesgo_ia) - (ia_criticos + ia_altos + ia_medios + ia_bajos))

        ia_labels = []
        ia_values = []
        if ia_criticos > 0:
            ia_labels.append('Crítico')
            ia_values.append(ia_criticos)
        if ia_altos > 0:
            ia_labels.append('Alto')
            ia_values.append(ia_altos)
        if ia_medios > 0:
            ia_labels.append('Medio')
            ia_values.append(ia_medios)
        if ia_bajos > 0:
            ia_labels.append('Bajo')
            ia_values.append(ia_bajos)
        if ia_sin_riesgo > 0:
            ia_labels.append('Sin riesgo')
            ia_values.append(ia_sin_riesgo)

        if not ia_labels:
            ia_labels = ['Sin datos']
            ia_values = [0]
    else:
        ia_labels = ['Sin datos']
        ia_values = [0]

    # ============================================
    # MENSAJES RECIENTES
    # ============================================
    mensajes_recientes = Mensaje.objects.filter(
        Q(remitente=request.user) | Q(destinatario=request.user)
    ).order_by('-fecha_envio')[:5]
    
    mensajes_no_leidos = Mensaje.objects.filter(
        destinatario=request.user,
        leido=False
    ).count()
    
    total_mensajes = Mensaje.objects.filter(
        Q(remitente=request.user) | Q(destinatario=request.user)
    ).count()

    # ============================================
    # ESTUDIANTES EN RIESGO
    # ============================================
    en_riesgo = RiesgoEstudiante.objects.filter(
        idEstudiante__in=estudiantes_ids,
        estado='Activo'
    ).values('idEstudiante').distinct().count()

    # ============================================
    # CONTEXTO COMPLETO
    # ============================================
    context = {
        # ✅ Rol
        'rol': 'profesor',
        
        # ✅ Estadísticas básicas
        'total_estudiantes': total_estudiantes,
        'asistencias_hoy': asistencias_hoy,
        'en_riesgo': en_riesgo,
        
        # ✅ Estadísticas de tutores (TODAS DEFINIDAS)
        'total_tutores': total_tutores,
        'tutores_con_estudiantes': tutores_con_estudiantes,
        'tutores_disponibles': tutores_disponibles,
        'total_estudiantes_con_tutor': total_estudiantes_con_tutor,
        'porcentaje_con_tutor': porcentaje_con_tutor,
        'tutores_activos': tutores_activos,
        'tutores_inactivos': tutores_inactivos,
        'tutores_detalle': tutores_detalle,
        'tutores_distribucion_labels': tutores_distribucion_labels,
        'tutores_distribucion_values': tutores_distribucion_values,
        
        # ✅ Gráficos
        'materias_labels': materias_labels,
        'materias_values': materias_values,
        'materias_cantidad': materias_cantidad,
        'rango_labels': list(rangos.keys()),
        'rango_values': list(rangos.values()),
        'dias_labels': dias_labels,
        'dias_values': asistencias_por_dia,
        'dias_ultimos_labels': ['Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes'],
        'dias_ultimos_values': asistencias_ultimos_dias,
        
        # ✅ Estadísticas avanzadas
        'promedio_asistencia': stats_avanzadas.get('promedio_asistencia', 0),
        'promedio_horas_estudio': stats_avanzadas.get('promedio_horas_estudio', 0),
        'promedio_compromiso': stats_avanzadas.get('promedio_compromiso', 0),
        'promedio_bienestar': stats_avanzadas.get('promedio_bienestar', 0),
        'compromiso_labels': stats_avanzadas.get('compromiso_labels', []),
        'compromiso_values': stats_avanzadas.get('compromiso_values', []),
        'bienestar_labels': stats_avanzadas.get('bienestar_labels', []),
        'bienestar_values': stats_avanzadas.get('bienestar_values', []),
        
        # ✅ IA
        'estudiantes_riesgo_ia': estudiantes_riesgo_ia,
        'ia_disponible': ia_disponible,
        'ia_labels': ia_labels,
        'ia_values': ia_values,
        'riesgo_por_curso': riesgo_por_curso,  # ✅ NUEVO
        
        # ✅ Mensajes
        'mensajes_recientes': mensajes_recientes,
        'mensajes_no_leidos': mensajes_no_leidos,
        'total_mensajes': total_mensajes,
        
        # ✅ Datos de la universidad
        'universidad_id': universidad_id,
        'universidad_nombre': get_universidad_nombre(universidad_id),  # ✅ NUEVO
    }

    cache.set(cache_key, context, 600)
    return render(request, 'profesor/dashboard_profesor.html', context)