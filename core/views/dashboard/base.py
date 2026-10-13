# core/views/dashboard/base.py

"""
Funciones auxiliares compartidas para todos los dashboards
"""
from django.db.models import Count, Avg, Q
from django.utils import timezone
from django.shortcuts import redirect
from django.contrib import messages

from ..base import (
    get_universidad_id,
    obtener_modelo_predictivo,
    obtener_servicio_prediccion,
    logger
)
from ...models import (
    Estudiante, HistorialAcademico, Asistencia,
    RiesgoEstudiante, UsuarioEstudiantes
)


# ============================================
# HELPERS DE ESTUDIANTES
# ============================================

def get_estudiantes_por_usuario(request, include_all=False):
    """
    Obtiene los estudiantes según el rol del usuario.
    """
    user_rol = getattr(request.user, 'rol', 'estudiante')
    universidad_id = get_universidad_id(request)

    if request.user.is_superuser:
        queryset = Estudiante.objects.select_related('idCarrera__idUniversidad')
    else:
        queryset = Estudiante.objects.filter(
            idCarrera__idUniversidad_id=universidad_id
        ).select_related('idCarrera__idUniversidad')

    if user_rol == 'admin' or include_all:
        return queryset
    elif user_rol == 'tutor':
        estudiantes_asignados = UsuarioEstudiantes.objects.filter(
            usuario_id=request.user.id
        ).values_list('estudiante_id', flat=True)
        return queryset.filter(idEstudiante__in=estudiantes_asignados)
    elif user_rol == 'estudiante':
        try:
            estudiante = Estudiante.objects.get(idUsuario=request.user.id)
            return queryset.filter(idEstudiante=estudiante.idEstudiante)
        except Estudiante.DoesNotExist:
            return Estudiante.objects.none()

    return queryset


# ============================================
# ROUTER DE DASHBOARD POR ROL
# ============================================

# Mapeo de rol → nombre de URL
DASHBOARD_URL_MAP = {
    'admin': 'dashboard_admin',
    'tutor': 'dashboard_tutor',
    'profesor': 'dashboard_profesor',
    'estudiante': 'dashboard_estudiante',
}


def get_dashboard_url_by_rol(rol):
    """
    Obtiene el nombre de la URL del dashboard según el rol.
    """
    return DASHBOARD_URL_MAP.get(rol)


def redirect_to_dashboard_by_rol(request):
    """
    Redirige al dashboard correspondiente según el rol del usuario.
    Maneja superusuarios correctamente.

    Uso:
        return redirect_to_dashboard_by_rol(request)
    """
    user = request.user

    # ✅ Superusuario → dashboard_admin
    if user.is_superuser:
        return redirect('dashboard_admin')

    # ✅ Obtener rol
    user_rol = getattr(user, 'rol', None)

    if not user_rol:
        messages.error(request, "Tu usuario no tiene un rol asignado. Contacta al administrador.")
        return redirect('logout')

    # ✅ Verificar universidad asignada
    universidad_id = get_universidad_id(request)
    if not universidad_id:
        messages.warning(request, "No tienes una universidad asignada. Contacta al administrador.")
        return redirect('logout')

    # ✅ Redirigir según el rol
    url_name = DASHBOARD_URL_MAP.get(user_rol)
    if url_name:
        return redirect(url_name)

    messages.error(request, f"Rol '{user_rol}' no reconocido. Contacta al administrador.")
    return redirect('logout')


# ============================================
# ESTADÍSTICAS AVANZADAS (sin cambios)
# ============================================

def obtener_estadisticas_avanzadas(universidad_id, estudiantes_ids):
    """Obtiene estadísticas avanzadas usando IA con gráficos adicionales."""
    stats = {
        'promedio_asistencia': 0,
        'promedio_horas_estudio': 0,
        'promedio_compromiso': 0,
        'promedio_bienestar': 0,
        'compromiso_labels': [],
        'compromiso_values': [],
        'bienestar_labels': [],
        'bienestar_values': [],
        'estudiantes_riesgo_ia': [],
        'ia_disponible': False,
        'bajo_rendimiento': 0,
        'rendimiento_labels': [],
        'rendimiento_values': [],
        'materias_rendimiento_labels': [],
        'materias_rendimiento_values': [],
        'calificaciones_distribucion': {},
        'asistencias_dias_labels': ['Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes'],
        'asistencias_dias_values': [0, 0, 0, 0, 0],
        'tasa_aprobacion': 0,
        'tasa_reprobacion': 0,
    }

    try:
        from django.db.models import Avg, Count, Q
        from django.db.models.functions import ExtractWeekDay

        # Rendimiento por materia
        materias_data = HistorialAcademico.objects.filter(
            idEstudiante__in=estudiantes_ids,
            nota_final__isnull=False
        ).values('idMateria__nombre').annotate(
            promedio=Avg('nota_final'),
            total_estudiantes=Count('idEstudiante', distinct=True)
        ).order_by('-promedio')[:10]

        stats['materias_rendimiento_labels'] = [item['idMateria__nombre'][:20] for item in materias_data]
        stats['materias_rendimiento_values'] = [
            float(item['promedio']) if item['promedio'] else 0 for item in materias_data
        ]

        # Distribución de calificaciones
        rangos = {
            'Excelente (18-20)': 0,
            'Muy Bueno (15-17)': 0,
            'Bueno (12-14)': 0,
            'Regular (10-11)': 0,
            'Reprobado (0-9)': 0
        }

        notas = HistorialAcademico.objects.filter(
            idEstudiante__in=estudiantes_ids,
            nota_final__isnull=False
        ).values_list('nota_final', flat=True)

        for nota in notas:
            if nota >= 18:
                rangos['Excelente (18-20)'] += 1
            elif nota >= 15:
                rangos['Muy Bueno (15-17)'] += 1
            elif nota >= 12:
                rangos['Bueno (12-14)'] += 1
            elif nota >= 10:
                rangos['Regular (10-11)'] += 1
            else:
                rangos['Reprobado (0-9)'] += 1

        stats['calificaciones_distribucion'] = rangos

        total_materias = sum(rangos.values())
        if total_materias > 0:
            aprobadas = (rangos['Excelente (18-20)'] + rangos['Muy Bueno (15-17)']
                         + rangos['Bueno (12-14)'] + rangos['Regular (10-11)'])
            reprobadas = rangos['Reprobado (0-9)']
            stats['tasa_aprobacion'] = round((aprobadas / total_materias) * 100, 1)
            stats['tasa_reprobacion'] = round((reprobadas / total_materias) * 100, 1)

        # Asistencias por día
        asistencias_dias = Asistencia.objects.filter(
            idEstudiante__in=estudiantes_ids
        ).values(dia=ExtractWeekDay('fecha')).annotate(
            total=Count('idAsistencia'),
            presentes=Count('idAsistencia', filter=Q(presente=True))
        ).order_by('dia')

        dias_map = {2: 'Lunes', 3: 'Martes', 4: 'Miércoles', 5: 'Jueves', 6: 'Viernes', 7: 'Sábado', 1: 'Domingo'}
        dias_laborales = ['Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes']
        stats['asistencias_dias_values'] = [0] * 5

        for item in asistencias_dias:
            dia_nombre = dias_map.get(item['dia'], '')
            if dia_nombre in dias_laborales:
                idx = dias_laborales.index(dia_nombre)
                stats['asistencias_dias_values'][idx] = item['presentes']

        # Estadísticas IA
        modelo = obtener_modelo_predictivo()
        if modelo is None or modelo.modelo is None:
            return stats

        from core.ml.features import FeatureEngineer
        feature_engineer = FeatureEngineer()
        df = feature_engineer.crear_dataset_entrenamiento(universidad_id)

        if df is not None and not df.empty:
            if 'porcentaje_asistencia' in df:
                stats['promedio_asistencia'] = round(df['porcentaje_asistencia'].mean(), 1)
            if 'horas_estudio' in df:
                stats['promedio_horas_estudio'] = round(df['horas_estudio'].mean(), 1)

            if 'indice_compromiso' in df:
                stats['promedio_compromiso'] = round(df['indice_compromiso'].mean(), 2)
                compromiso_bajo = len(df[df['indice_compromiso'] < 0.4])
                compromiso_medio = len(df[(df['indice_compromiso'] >= 0.4) & (df['indice_compromiso'] < 0.7)])
                compromiso_alto = len(df[df['indice_compromiso'] >= 0.7])
                stats['compromiso_labels'] = ['Bajo', 'Medio', 'Alto']
                stats['compromiso_values'] = [compromiso_bajo, compromiso_medio, compromiso_alto]

            if 'indice_bienestar' in df:
                stats['promedio_bienestar'] = round(df['indice_bienestar'].mean(), 2)
                bienestar_bajo = len(df[df['indice_bienestar'] < 0.4])
                bienestar_medio = len(df[(df['indice_bienestar'] >= 0.4) & (df['indice_bienestar'] < 0.7)])
                bienestar_alto = len(df[df['indice_bienestar'] >= 0.7])
                stats['bienestar_labels'] = ['Bajo', 'Medio', 'Alto']
                stats['bienestar_values'] = [bienestar_bajo, bienestar_medio, bienestar_alto]

            if modelo.modelo is not None:
                servicio = obtener_servicio_prediccion()
                if servicio:
                    try:
                        stats['estudiantes_riesgo_ia'] = servicio.obtener_estudiantes_riesgo(None, limit=50)
                        stats['ia_disponible'] = True
                    except Exception as e:
                        logger.warning(f"Error obteniendo estudiantes en riesgo: {str(e)}")

    except ImportError as e:
        logger.warning(f"No se pudo importar FeatureEngineer: {str(e)}")
    except Exception as e:
        logger.warning(f"Error obteniendo estadísticas avanzadas: {str(e)}")

    return stats


def obtener_estadisticas_avanzadas_tutor(universidad_id, estudiantes_ids, usuario):
    """Obtiene estadísticas avanzadas con IA para el tutor."""
    stats = {
        'promedio_asistencia': 0,
        'promedio_horas_estudio': 0,
        'promedio_compromiso': 0,
        'promedio_bienestar': 0,
        'compromiso_labels': [],
        'compromiso_values': [],
        'bienestar_labels': [],
        'bienestar_values': [],
        'estudiantes_riesgo_ia': [],
        'ia_disponible': False,
        'materias_rendimiento_labels': [],
        'materias_rendimiento_values': [],
        'calificaciones_distribucion': {},
        'asistencias_dias_labels': ['Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes'],
        'asistencias_dias_values': [0, 0, 0, 0, 0],
        'tasa_aprobacion': 0,
        'tasa_reprobacion': 0,
        'estudiantes_por_nivel_riesgo': {},
    }

    try:
        from django.db.models import Avg, Count, Q
        from django.db.models.functions import ExtractWeekDay

        if not estudiantes_ids:
            return stats

        materias_data = HistorialAcademico.objects.filter(
            idEstudiante__in=estudiantes_ids,
            nota_final__isnull=False
        ).values('idMateria__nombre').annotate(
            promedio=Avg('nota_final'),
            total_estudiantes=Count('idEstudiante', distinct=True)
        ).order_by('-promedio')[:10]

        stats['materias_rendimiento_labels'] = [item['idMateria__nombre'][:20] for item in materias_data]
        stats['materias_rendimiento_values'] = [
            float(item['promedio']) if item['promedio'] else 0 for item in materias_data
        ]

        rangos = {
            'Excelente (18-20)': 0,
            'Muy Bueno (15-17)': 0,
            'Bueno (12-14)': 0,
            'Regular (10-11)': 0,
            'Reprobado (0-9)': 0
        }

        notas = HistorialAcademico.objects.filter(
            idEstudiante__in=estudiantes_ids,
            nota_final__isnull=False
        ).values_list('nota_final', flat=True)

        for nota in notas:
            if nota >= 18:
                rangos['Excelente (18-20)'] += 1
            elif nota >= 15:
                rangos['Muy Bueno (15-17)'] += 1
            elif nota >= 12:
                rangos['Bueno (12-14)'] += 1
            elif nota >= 10:
                rangos['Regular (10-11)'] += 1
            else:
                rangos['Reprobado (0-9)'] += 1

        stats['calificaciones_distribucion'] = rangos

        total_materias = sum(rangos.values())
        if total_materias > 0:
            aprobadas = (rangos['Excelente (18-20)'] + rangos['Muy Bueno (15-17)']
                         + rangos['Bueno (12-14)'] + rangos['Regular (10-11)'])
            reprobadas = rangos['Reprobado (0-9)']
            stats['tasa_aprobacion'] = round((aprobadas / total_materias) * 100, 1)
            stats['tasa_reprobacion'] = round((reprobadas / total_materias) * 100, 1)

        asistencias_dias = Asistencia.objects.filter(
            idEstudiante__in=estudiantes_ids
        ).values(dia=ExtractWeekDay('fecha')).annotate(
            total=Count('idAsistencia'),
            presentes=Count('idAsistencia', filter=Q(presente=True))
        ).order_by('dia')

        dias_map = {2: 'Lunes', 3: 'Martes', 4: 'Miércoles', 5: 'Jueves', 6: 'Viernes', 7: 'Sábado', 1: 'Domingo'}
        dias_laborales = ['Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes']
        stats['asistencias_dias_values'] = [0] * 5

        for item in asistencias_dias:
            dia_nombre = dias_map.get(item['dia'], '')
            if dia_nombre in dias_laborales:
                idx = dias_laborales.index(dia_nombre)
                stats['asistencias_dias_values'][idx] = item['presentes']

        modelo = obtener_modelo_predictivo()
        if modelo is None or modelo.modelo is None:
            return stats

        from core.ml.features import FeatureEngineer
        feature_engineer = FeatureEngineer()
        df = feature_engineer.crear_dataset_entrenamiento(universidad_id)

        if df is not None and not df.empty and estudiantes_ids:
            df = df[df['estudiante_id'].isin(estudiantes_ids)]

        if df is not None and not df.empty:
            if 'porcentaje_asistencia' in df:
                stats['promedio_asistencia'] = round(df['porcentaje_asistencia'].mean(), 1)
            if 'horas_estudio' in df:
                stats['promedio_horas_estudio'] = round(df['horas_estudio'].mean(), 1)

            if 'indice_compromiso' in df:
                stats['promedio_compromiso'] = round(df['indice_compromiso'].mean(), 2)
                compromiso_bajo = len(df[df['indice_compromiso'] < 0.4])
                compromiso_medio = len(df[(df['indice_compromiso'] >= 0.4) & (df['indice_compromiso'] < 0.7)])
                compromiso_alto = len(df[df['indice_compromiso'] >= 0.7])
                stats['compromiso_labels'] = ['Bajo', 'Medio', 'Alto']
                stats['compromiso_values'] = [compromiso_bajo, compromiso_medio, compromiso_alto]

            if 'indice_bienestar' in df:
                stats['promedio_bienestar'] = round(df['indice_bienestar'].mean(), 2)
                bienestar_bajo = len(df[df['indice_bienestar'] < 0.4])
                bienestar_medio = len(df[(df['indice_bienestar'] >= 0.4) & (df['indice_bienestar'] < 0.7)])
                bienestar_alto = len(df[df['indice_bienestar'] >= 0.7])
                stats['bienestar_labels'] = ['Bajo', 'Medio', 'Alto']
                stats['bienestar_values'] = [bienestar_bajo, bienestar_medio, bienestar_alto]

            if modelo.modelo is not None:
                servicio = obtener_servicio_prediccion()
                if servicio:
                    try:
                        stats['estudiantes_riesgo_ia'] = servicio.obtener_estudiantes_riesgo(usuario, limit=50)
                        stats['ia_disponible'] = True
                    except Exception as e:
                        logger.warning(f"Error obteniendo estudiantes en riesgo: {str(e)}")

    except ImportError as e:
        logger.warning(f"No se pudo importar FeatureEngineer: {str(e)}")
    except Exception as e:
        logger.warning(f"Error obteniendo estadísticas avanzadas: {str(e)}")

    return stats


def obtener_estadisticas_avanzadas_profesor(universidad_id, estudiantes_ids, usuario):
    """Obtiene estadísticas avanzadas con IA para el profesor."""
    stats = {
        'promedio_asistencia': 0,
        'promedio_horas_estudio': 0,
        'promedio_compromiso': 0,
        'promedio_bienestar': 0,
        'compromiso_labels': [],
        'compromiso_values': [],
        'bienestar_labels': [],
        'bienestar_values': [],
        'estudiantes_riesgo_ia': [],
        'ia_disponible': False,
        'materias_rendimiento_labels': [],
        'materias_rendimiento_values': [],
        'calificaciones_distribucion': {},
        'asistencias_dias_labels': ['Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes'],
        'asistencias_dias_values': [0, 0, 0, 0, 0],
        'tasa_aprobacion': 0,
        'tasa_reprobacion': 0,
        'distribucion_estados': {},
    }

    try:
        from django.db.models import Avg, Count, Q
        from django.db.models.functions import ExtractWeekDay

        if not estudiantes_ids:
            return stats

        materias_data = HistorialAcademico.objects.filter(
            idEstudiante__in=estudiantes_ids,
            nota_final__isnull=False
        ).values('idMateria__nombre').annotate(
            promedio=Avg('nota_final'),
            total_estudiantes=Count('idEstudiante', distinct=True)
        ).order_by('-promedio')[:10]

        stats['materias_rendimiento_labels'] = [item['idMateria__nombre'][:20] for item in materias_data]
        stats['materias_rendimiento_values'] = [
            float(item['promedio']) if item['promedio'] else 0 for item in materias_data
        ]

        rangos = {
            'Excelente (18-20)': 0,
            'Muy Bueno (15-17)': 0,
            'Bueno (12-14)': 0,
            'Regular (10-11)': 0,
            'Reprobado (0-9)': 0
        }

        notas = HistorialAcademico.objects.filter(
            idEstudiante__in=estudiantes_ids,
            nota_final__isnull=False
        ).values_list('nota_final', flat=True)

        for nota in notas:
            if nota >= 18:
                rangos['Excelente (18-20)'] += 1
            elif nota >= 15:
                rangos['Muy Bueno (15-17)'] += 1
            elif nota >= 12:
                rangos['Bueno (12-14)'] += 1
            elif nota >= 10:
                rangos['Regular (10-11)'] += 1
            else:
                rangos['Reprobado (0-9)'] += 1

        stats['calificaciones_distribucion'] = rangos

        total_materias = sum(rangos.values())
        if total_materias > 0:
            aprobadas = (rangos['Excelente (18-20)'] + rangos['Muy Bueno (15-17)']
                         + rangos['Bueno (12-14)'] + rangos['Regular (10-11)'])
            reprobadas = rangos['Reprobado (0-9)']
            stats['tasa_aprobacion'] = round((aprobadas / total_materias) * 100, 1)
            stats['tasa_reprobacion'] = round((reprobadas / total_materias) * 100, 1)

        asistencias_dias = Asistencia.objects.filter(
            idEstudiante__in=estudiantes_ids
        ).values(dia=ExtractWeekDay('fecha')).annotate(
            total=Count('idAsistencia'),
            presentes=Count('idAsistencia', filter=Q(presente=True))
        ).order_by('dia')

        dias_map = {2: 'Lunes', 3: 'Martes', 4: 'Miércoles', 5: 'Jueves', 6: 'Viernes', 7: 'Sábado', 1: 'Domingo'}
        dias_laborales = ['Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes']
        stats['asistencias_dias_values'] = [0] * 5

        for item in asistencias_dias:
            dia_nombre = dias_map.get(item['dia'], '')
            if dia_nombre in dias_laborales:
                idx = dias_laborales.index(dia_nombre)
                stats['asistencias_dias_values'][idx] = item['presentes']

        modelo = obtener_modelo_predictivo()
        if modelo is None or modelo.modelo is None:
            return stats

        from core.ml.features import FeatureEngineer
        feature_engineer = FeatureEngineer()
        df = feature_engineer.crear_dataset_entrenamiento(universidad_id)

        if df is not None and not df.empty:
            if 'porcentaje_asistencia' in df:
                stats['promedio_asistencia'] = round(df['porcentaje_asistencia'].mean(), 1)
            if 'horas_estudio' in df:
                stats['promedio_horas_estudio'] = round(df['horas_estudio'].mean(), 1)

            if 'indice_compromiso' in df:
                stats['promedio_compromiso'] = round(df['indice_compromiso'].mean(), 2)
                compromiso_bajo = len(df[df['indice_compromiso'] < 0.4])
                compromiso_medio = len(df[(df['indice_compromiso'] >= 0.4) & (df['indice_compromiso'] < 0.7)])
                compromiso_alto = len(df[df['indice_compromiso'] >= 0.7])
                stats['compromiso_labels'] = ['Bajo', 'Medio', 'Alto']
                stats['compromiso_values'] = [compromiso_bajo, compromiso_medio, compromiso_alto]

            if 'indice_bienestar' in df:
                stats['promedio_bienestar'] = round(df['indice_bienestar'].mean(), 2)
                bienestar_bajo = len(df[df['indice_bienestar'] < 0.4])
                bienestar_medio = len(df[(df['indice_bienestar'] >= 0.4) & (df['indice_bienestar'] < 0.7)])
                bienestar_alto = len(df[df['indice_bienestar'] >= 0.7])
                stats['bienestar_labels'] = ['Bajo', 'Medio', 'Alto']
                stats['bienestar_values'] = [bienestar_bajo, bienestar_medio, bienestar_alto]

            if modelo.modelo is not None:
                servicio = obtener_servicio_prediccion()
                if servicio:
                    try:
                        stats['estudiantes_riesgo_ia'] = servicio.obtener_estudiantes_riesgo(usuario, limit=50)
                        stats['ia_disponible'] = True
                    except Exception as e:
                        logger.warning(f"Error obteniendo estudiantes en riesgo: {str(e)}")

    except ImportError as e:
        logger.warning(f"No se pudo importar FeatureEngineer: {str(e)}")
    except Exception as e:
        logger.warning(f"Error obteniendo estadísticas avanzadas: {str(e)}")

    return stats


def obtener_estadisticas_estudiante_ia(estudiante_id):
    """Obtiene la predicción de IA y estadísticas personales para un estudiante."""
    stats = {
        'prediccion': {},
        'disponible': False,
        'nivel_riesgo': 'No disponible',
        'probabilidad': 0,
        'materias_promedio': {},
        'calificaciones_personales': [],
        'asistencia_por_dia': {},
        'rendimiento_tendencia': [],
        'comparativa_promedio': 0,
        'comparativa_general': 0,
    }

    try:
        estudiante = Estudiante.objects.get(idEstudiante=estudiante_id)

        materias = HistorialAcademico.objects.filter(
            idEstudiante=estudiante,
            nota_final__isnull=False
        ).values('idMateria__nombre').annotate(promedio=Avg('nota_final'))

        stats['materias_promedio'] = {item['idMateria__nombre']: float(item['promedio']) for item in materias}

        calificaciones = HistorialAcademico.objects.filter(
            idEstudiante=estudiante,
            nota_final__isnull=False
        ).values_list('nota_final', flat=True)

        stats['calificaciones_personales'] = list(calificaciones)

        from django.db.models import Count, Q
        from django.db.models.functions import ExtractWeekDay

        asistencias = Asistencia.objects.filter(
            idEstudiante=estudiante
        ).values(dia=ExtractWeekDay('fecha')).annotate(
            presentes=Count('idAsistencia', filter=Q(presente=True)),
            total=Count('idAsistencia')
        )

        dias_map = {2: 'Lunes', 3: 'Martes', 4: 'Miércoles', 5: 'Jueves', 6: 'Viernes'}
        stats['asistencia_por_dia'] = {}

        for item in asistencias:
            dia_nombre = dias_map.get(item['dia'], '')
            if dia_nombre:
                stats['asistencia_por_dia'][dia_nombre] = {
                    'presentes': item['presentes'],
                    'total': item['total'],
                    'porcentaje': round(
                        (item['presentes'] / item['total'] * 100) if item['total'] > 0 else 0, 1
                    )
                }

        tendencia = HistorialAcademico.objects.filter(
            idEstudiante=estudiante,
            nota_final__isnull=False
        ).order_by('-fecha_registro')[:10].values_list('nota_final', flat=True)

        stats['rendimiento_tendencia'] = list(reversed(list(tendencia)))

        promedio_estudiante = HistorialAcademico.objects.filter(
            idEstudiante=estudiante,
            nota_final__isnull=False
        ).aggregate(Avg('nota_final'))['nota_final__avg'] or 0

        promedio_general = HistorialAcademico.objects.filter(
            nota_final__isnull=False
        ).aggregate(Avg('nota_final'))['nota_final__avg'] or 0

        stats['comparativa_promedio'] = round(float(promedio_estudiante), 1)
        stats['comparativa_general'] = round(float(promedio_general), 1)

        modelo = obtener_modelo_predictivo()
        if modelo is None or modelo.modelo is None:
            return stats

        servicio = obtener_servicio_prediccion()
        if servicio:
            try:
                prediccion = modelo.predecir_estudiante(estudiante_id)
                stats['prediccion'] = prediccion
                stats['disponible'] = True
                stats['nivel_riesgo'] = prediccion.get('nivel_riesgo', 'No disponible')
                stats['probabilidad'] = prediccion.get('probabilidad', 0)
            except Exception as e:
                logger.warning(f"Error obteniendo predicción para estudiante {estudiante_id}: {str(e)}")

    except Estudiante.DoesNotExist:
        logger.warning(f"Estudiante {estudiante_id} no encontrado")
    except Exception as e:
        logger.warning(f"Error obteniendo estadísticas IA para estudiante: {str(e)}")

    return stats