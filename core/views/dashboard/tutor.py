# core/views/dashboard/tutor.py

"""
Dashboard para tutores
"""
from django.shortcuts import render
from django.db.models import Count, Avg, Q
from django.utils import timezone
from django.core.cache import cache
from datetime import timedelta

from ...models import (
    Estudiante, HistorialAcademico, Asistencia,
    RiesgoEstudiante, Intervencion, UsuarioEstudiantes
)
from ..base import get_universidad_id
from .base import obtener_estadisticas_avanzadas_tutor

# core/views/dashboard/tutor.py

# ... (imports) ...

def dashboard_tutor(request):
    """Dashboard para tutores con todos los gráficos de sus estudiantes asignados."""
    universidad_id = get_universidad_id(request)
    cache_key = f'dashboard_tutor_{universidad_id}_{timezone.now().date()}'

    context = cache.get(cache_key)
    if context:
        return render(request, 'tutor/dashboard_tutor.html', context)

    estudiantes_asignados = UsuarioEstudiantes.objects.filter(
        usuario_id=request.user.id
    ).values_list('estudiante_id', flat=True)

    estudiantes_ids = list(estudiantes_asignados)
    total_asignados = len(estudiantes_ids)

    en_riesgo = RiesgoEstudiante.objects.filter(
        idEstudiante__in=estudiantes_ids,
        estado='Activo'
    ).values('idEstudiante').distinct().count()

    estado_data = Estudiante.objects.filter(
        idEstudiante__in=estudiantes_ids
    ).values('estado_academico').annotate(
        cantidad=Count('idEstudiante')
    )

    riesgo_data = RiesgoEstudiante.objects.filter(
        idEstudiante__in=estudiantes_ids,
        estado='Activo'
    ).values('nivel').annotate(
        cantidad=Count('idRiesgo')  # ✅ CORREGIDO: 'idRiesgo' en lugar de 'idRiesgo'
    )

    rendimiento_materias = HistorialAcademico.objects.filter(
        idEstudiante__in=estudiantes_ids,
        nota_final__isnull=False
    ).values(
        'idMateria__nombre'
    ).annotate(
        promedio=Avg('nota_final'),
        cantidad=Count('idHistorial')  # ✅ CORREGIDO: 'idHistorial' en lugar de 'idHistorial'
    ).order_by('-cantidad')[:10]

    materias_labels = [item['idMateria__nombre'][:20] for item in rendimiento_materias]
    materias_values = [float(item['promedio']) if item['promedio'] else 0 for item in rendimiento_materias]
    materias_cantidad = [item['cantidad'] for item in rendimiento_materias]

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

    dias_semana = ['Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes', 'Sábado', 'Domingo']

    asistencias_dias = Asistencia.objects.filter(
        idEstudiante__in=estudiantes_ids,
        presente=True
    ).extra(
        select={'dia_semana': "EXTRACT(DOW FROM fecha)"}
    ).values('dia_semana').annotate(
        cantidad=Count('idAsistencia')  # ✅ CORREGIDO: 'idAsistencia' en lugar de 'idAsistencia'
    ).order_by('dia_semana')

    asistencias_por_dia = [0] * 7
    for item in asistencias_dias:
        dia_idx = int(item['dia_semana']) - 1
        if 0 <= dia_idx < 7:
            asistencias_por_dia[dia_idx] = item['cantidad']

    asistencias_por_dia = asistencias_por_dia[1:] + asistencias_por_dia[:1]
    dias_labels = dias_semana

    # ✅ CORREGIDO: Cambiar 'idIntervencion' por 'id' en el Count
    intervencion_data = Intervencion.objects.filter(
        idEstudiante__in=estudiantes_ids
    ).values('tipo_intervencion').annotate(
        cantidad=Count('id')  # ✅ CORREGIDO: 'id' en lugar de 'idIntervencion'
    ).order_by('-cantidad')[:5]

    alertas_mis_estudiantes = RiesgoEstudiante.objects.filter(
        idEstudiante__in=estudiantes_ids,
        estado='Activo'
    ).select_related('idEstudiante', 'idFactor')[:10]

    intervenciones_programadas = Intervencion.objects.filter(
        idEstudiante__in=estudiantes_ids,
        fecha_realizada__isnull=True
    ).select_related('idEstudiante')[:5]

    stats_avanzadas = obtener_estadisticas_avanzadas_tutor(universidad_id, estudiantes_ids, request.user)

    estudiantes_riesgo_ia = stats_avanzadas.get('estudiantes_riesgo_ia', [])
    ia_disponible = stats_avanzadas.get('ia_disponible', False)

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

    context = {
        'rol': 'tutor',
        'total_asignados': total_asignados,
        'en_riesgo': en_riesgo,
        'estado_labels': [item['estado_academico'] for item in estado_data],
        'estado_values': [item['cantidad'] for item in estado_data],
        'riesgo_labels': [item['nivel'] for item in riesgo_data],
        'riesgo_values': [item['cantidad'] for item in riesgo_data],
        'materias_labels': materias_labels,
        'materias_values': materias_values,
        'materias_cantidad': materias_cantidad,
        'rango_labels': list(rangos.keys()),
        'rango_values': list(rangos.values()),
        'dias_labels': dias_labels,
        'dias_values': asistencias_por_dia,
        'intervencion_labels': [item['tipo_intervencion'] for item in intervencion_data],
        'intervencion_values': [item['cantidad'] for item in intervencion_data],
        'alertas_mis_estudiantes': alertas_mis_estudiantes,
        'intervenciones_programadas': intervenciones_programadas,
        'promedio_asistencia': stats_avanzadas.get('promedio_asistencia', 0),
        'promedio_horas_estudio': stats_avanzadas.get('promedio_horas_estudio', 0),
        'promedio_compromiso': stats_avanzadas.get('promedio_compromiso', 0),
        'promedio_bienestar': stats_avanzadas.get('promedio_bienestar', 0),
        'compromiso_labels': stats_avanzadas.get('compromiso_labels', []),
        'compromiso_values': stats_avanzadas.get('compromiso_values', []),
        'bienestar_labels': stats_avanzadas.get('bienestar_labels', []),
        'bienestar_values': stats_avanzadas.get('bienestar_values', []),
        'estudiantes_riesgo_ia': estudiantes_riesgo_ia,
        'ia_disponible': ia_disponible,
        'ia_labels': ia_labels,
        'ia_values': ia_values,
    }

    cache.set(cache_key, context, 600)
    return render(request, 'tutor/dashboard_tutor.html', context)