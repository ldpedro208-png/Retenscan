# core/views/dashboard/estudiante.py

"""
Dashboard para estudiantes
"""
from django.shortcuts import render
from django.db.models import Avg, Count, Q
from django.utils import timezone
from django.core.cache import cache
from datetime import timedelta
from core.models import Mensaje

# ✅ CAMBIO: BecaEstudiante → BecaAsignacion
from ...models import (
    Estudiante, HistorialAcademico, Asistencia,
    RiesgoEstudiante, BecaAsignacion
)
from .base import obtener_estadisticas_estudiante_ia


def dashboard_estudiante(request):
    """Dashboard para estudiantes con estadísticas e IA personal."""
    try:
        estudiante = Estudiante.objects.get(idUsuario=request.user.id)
    except Estudiante.DoesNotExist:
        # ✅ RETORNAR UN RENDER CON UN CONTEXTO VÁLIDO
        context = {
            'rol': 'estudiante',
            'sin_perfil': True,
            'estudiante': None,
            'mensajes_recientes': [],
            'mensajes_no_leidos': 0,
            'total_mensajes': 0,
            'aprobadas': 0,
            'reprobadas': 0,
            'cursando': 0,
            'porcentaje_asistencia': 0,
            'tiene_riesgo': False,
            'riesgos': [],
            'beca_activa': None,
            'materias_labels': [],
            'materias_values': [],
            'estado_materias_labels': ['Aprobadas', 'Reprobadas', 'Cursando'],
            'estado_materias_values': [0, 0, 0],
            'meses_labels': [],
            'meses_values': [],
            'prediccion_ia': {},
            'ia_disponible': False,
            'nivel_riesgo_ia': 'No disponible',
            'probabilidad_ia': 0,
            'mi_historial': [],
        }
        return render(request, 'estudiante/dashboard_estudiante.html', context)

    cache_key = f'dashboard_estudiante_{estudiante.idEstudiante}_{timezone.now().date()}'

    context = cache.get(cache_key)
    if context:
        # ✅ Asegurar que el contexto tenga el rol
        context['rol'] = 'estudiante'
        return render(request, 'estudiante/dashboard_estudiante.html', context)

    # ============================================
    # DATOS ACADÉMICOS
    # ============================================
    historial = HistorialAcademico.objects.filter(
        idEstudiante=estudiante
    ).select_related('idMateria')

    materias_data = historial.values(
        'idMateria__nombre'
    ).annotate(
        nota=Avg('nota_final')
    )

    aprobadas = historial.filter(estado_materia='Aprobada').count()
    reprobadas = historial.filter(estado_materia='Reprobada').count()
    cursando = historial.filter(estado_materia='Cursando').count()

    # ============================================
    # ASISTENCIAS
    # ============================================
    meses = []
    asistencias_mensuales = []
    for i in range(5, -1, -1):
        mes = timezone.now().date() - timedelta(days=30*i)
        count = Asistencia.objects.filter(
            idEstudiante=estudiante,
            fecha__month=mes.month,
            fecha__year=mes.year,
            presente=True
        ).count()
        meses.append(mes.strftime('%b'))
        asistencias_mensuales.append(count)

    hace_un_mes = timezone.now().date() - timedelta(days=30)
    asistencias = Asistencia.objects.filter(
        idEstudiante=estudiante,
        fecha__gte=hace_un_mes
    )
    asistencias_presente = asistencias.filter(presente=True).count()
    asistencias_total = asistencias.count()
    porcentaje_asistencia = 0
    if asistencias_total > 0:
        porcentaje_asistencia = round((asistencias_presente / asistencias_total) * 100)

    # ============================================
    # RIESGOS Y BECAS
    # ============================================
    riesgos = RiesgoEstudiante.objects.filter(
        idEstudiante=estudiante,
        estado='Activo'
    ).select_related('idFactor')

    # ✅ CAMBIO: usar BecaAsignacion
    beca_activa = BecaAsignacion.objects.filter(
        idEstudiante=estudiante,
        estado='Activa'
    ).select_related('idBeca', 'idBeca__tipo').first()

    # ============================================
    # IA PERSONAL
    # ============================================
    stats_ia = obtener_estadisticas_estudiante_ia(estudiante.idEstudiante)

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
    # CONTEXTO COMPLETO
    # ============================================
    context = {
        'rol': 'estudiante',
        'estudiante': estudiante,
        'sin_perfil': False,
        'mi_historial': historial[:10],
        'aprobadas': aprobadas,
        'reprobadas': reprobadas,
        'cursando': cursando,
        'asistencias_presente': asistencias_presente,
        'asistencias_total': asistencias_total,
        'porcentaje_asistencia': porcentaje_asistencia,
        'riesgos': riesgos,
        'tiene_riesgo': riesgos.exists(),
        'beca_activa': beca_activa,
        'materias_labels': [item['idMateria__nombre'][:15] for item in materias_data],
        'materias_values': [float(item['nota']) if item['nota'] else 0 for item in materias_data],
        'estado_materias_labels': ['Aprobadas', 'Reprobadas', 'Cursando'],
        'estado_materias_values': [aprobadas, reprobadas, cursando],
        'meses_labels': meses,
        'meses_values': asistencias_mensuales,
        'prediccion_ia': stats_ia.get('prediccion', {}),
        'ia_disponible': stats_ia.get('disponible', False),
        'nivel_riesgo_ia': stats_ia.get('nivel_riesgo', 'No disponible'),
        'probabilidad_ia': stats_ia.get('probabilidad', 0),
        # ✅ Mensajes
        'mensajes_recientes': mensajes_recientes,
        'mensajes_no_leidos': mensajes_no_leidos,
        'total_mensajes': total_mensajes,
    }

    # ✅ Guardar en caché
    cache.set(cache_key, context, 600)

    # ✅ Renderizar con el template correcto de estudiante
    return render(request, 'estudiante/dashboard_estudiante.html', context)