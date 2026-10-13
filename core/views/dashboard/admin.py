# core/views/dashboard/admin.py

from django.shortcuts import render
from django.db.models import Count, Avg, Q
from django.utils import timezone
from django.core.cache import cache
from datetime import timedelta
from core.models import Mensaje
from ...models import (
    Estudiante, HistorialAcademico, Asistencia,
    RiesgoEstudiante, Intervencion, Usuario, Tutor,
    CatalogoMateria, CatalogoCarrera, CatalogoAula,
    Beca, Encuesta, Tarea  # ✅ ESTOS MODELOS DEBEN ESTAR IMPORTADOS
)
from ..base import get_universidad_id
from .base import get_estudiantes_por_usuario, obtener_estadisticas_avanzadas


def dashboard_admin(request):
    """
    Dashboard para administradores con todos los gráficos.
    """
    universidad_id = get_universidad_id(request)
    
    # ✅ Clave de caché por universidad y fecha
    cache_key = f'dashboard_admin_{universidad_id}_{timezone.now().date()}'
    
    # ✅ Intentar obtener el CONTEXTO del caché (NO la respuesta)
    cached_context = cache.get(cache_key)
    if cached_context:
        # ✅ Asegurar que el contexto tenga el rol
        cached_context['rol'] = 'admin'
        # ✅ Renderizar con el contexto
        return render(request, 'admin/dashboard_admin.html', cached_context)
    
    # ✅ Obtener estudiantes (una sola vez, con select_related)
    estudiantes_qs = get_estudiantes_por_usuario(request, include_all=True)
    estudiantes_qs = estudiantes_qs.select_related('idCarrera', 'idUsuario')
    estudiantes_ids = list(estudiantes_qs.values_list('idEstudiante', flat=True))
    
    # ============================================
    # ESTADÍSTICAS BÁSICAS
    # ============================================
    total_estudiantes = estudiantes_qs.count()
    activos = estudiantes_qs.filter(estado_academico='Activo').count()
    
    riesgos_qs = RiesgoEstudiante.objects.filter(
        idEstudiante__in=estudiantes_ids,
        estado='Activo'
    ).select_related('idEstudiante', 'idFactor')
    
    alertas_recientes = riesgos_qs.order_by('-fecha_deteccion')[:10]
    en_riesgo = riesgos_qs.values('idEstudiante').distinct().count()
    
    # ============================================
    # ✅ CONTEO DE USUARIOS POR TIPO
    # ============================================
    
    # 1. Contar usuarios por rol (desde el modelo Usuario)
    usuarios_por_rol = Usuario.objects.filter(
        idUniversidad_id=universidad_id
    ).values('rol').annotate(
        total=Count('id')
    )
    
    # Diccionario para almacenar los conteos
    total_administradores = 0
    total_profesores_usuario = 0
    total_tutores_usuario = 0
    total_estudiantes_usuario = 0
    
    for item in usuarios_por_rol:
        if item['rol'] == 'admin':
            total_administradores = item['total']
        elif item['rol'] == 'profesor':
            total_profesores_usuario = item['total']
        elif item['rol'] == 'tutor':
            total_tutores_usuario = item['total']
        elif item['rol'] == 'estudiante':
            total_estudiantes_usuario = item['total']
    
    # 2. Contar tutores específicamente (desde el modelo Tutor)
    total_tutores_perfil = Tutor.objects.filter(
        usuario__idUniversidad_id=universidad_id,
        activo=True
    ).count()
    
    # 3. Contar administradores de universidad (campo específico)
    total_admins_universidad = Usuario.objects.filter(
        idUniversidad_id=universidad_id,
        es_admin_universidad=True
    ).count()
    
    # 4. Contar usuarios totales del sistema (para esta universidad)
    total_usuarios_sistema = Usuario.objects.filter(
        idUniversidad_id=universidad_id
    ).count()
    
    # 5. Usuarios activos vs inactivos
    usuarios_activos = Usuario.objects.filter(
        idUniversidad_id=universidad_id,
        is_active=True
    ).count()
    
    usuarios_inactivos = Usuario.objects.filter(
        idUniversidad_id=universidad_id,
        is_active=False
    ).count()
    
    # 6. Distribución de roles en porcentaje
    if total_usuarios_sistema > 0:
        porcentaje_administradores = round((total_administradores / total_usuarios_sistema) * 100, 1)
        porcentaje_profesores = round((total_profesores_usuario / total_usuarios_sistema) * 100, 1)
        porcentaje_tutores = round((total_tutores_usuario / total_usuarios_sistema) * 100, 1)
        porcentaje_estudiantes = round((total_estudiantes_usuario / total_usuarios_sistema) * 100, 1)
    else:
        porcentaje_administradores = 0
        porcentaje_profesores = 0
        porcentaje_tutores = 0
        porcentaje_estudiantes = 0

    # ============================================
    # ✅ CONTADORES PARA MÓDULOS DEL SISTEMA
    # ============================================
    
    # ✅ Usar la consulta que verificaste en la consola
    total_materias = CatalogoMateria.objects.filter(
        idCarrera__idUniversidad_id=universidad_id
    ).count()
    
    # Total de carreras
    total_carreras = CatalogoCarrera.objects.filter(
        idUniversidad_id=universidad_id
    ).count()
    
    # Total de aulas
    total_aulas = CatalogoAula.objects.count()
    
    # Total de becas
    total_becas = Beca.objects.filter(
        idUniversidad_id=universidad_id
    ).count()
    
    # Total de encuestas
    total_encuestas = Encuesta.objects.filter(
        idUniversidad_id=universidad_id
    ).count()
    
    # Total de tareas
    total_tareas = Tarea.objects.filter(
        idUniversidad_id=universidad_id
    ).count()
    
    # Total de intervenciones
    total_intervenciones = Intervencion.objects.filter(
        idEstudiante__idUniversidad_id=universidad_id
    ).count()
    
    # Total de riesgos activos
    total_riesgos = RiesgoEstudiante.objects.filter(
        idEstudiante__idUniversidad_id=universidad_id,
        estado='Activo'
    ).count()
    
    # Total de profesores (desde Usuario)
    total_profesores = Usuario.objects.filter(
        idUniversidad_id=universidad_id,
        rol='profesor'
    ).count()
    
    # Total de tutores (desde Usuario)
    total_tutores = Usuario.objects.filter(
        idUniversidad_id=universidad_id,
        rol='tutor'
    ).count()

    # ============================================
    # GRÁFICOS
    # ============================================
    estados_data = list(estudiantes_qs.values('estado_academico').annotate(
        cantidad=Count('idEstudiante')
    ))
    
    carreras_data = list(estudiantes_qs.values(
        'idCarrera__nombre'
    ).annotate(
        cantidad=Count('idEstudiante')
    ).order_by('-cantidad')[:5])
    
    factores_data = list(riesgos_qs.values('idFactor__nombre').annotate(
        cantidad=Count('idFactor')
    ).order_by('-cantidad')[:5])
    
    materias_rendimiento = HistorialAcademico.objects.filter(
        idEstudiante__in=estudiantes_ids,
        nota_final__isnull=False
    ).values('idMateria__nombre').annotate(
        promedio=Avg('nota_final'),
        cantidad=Count('idHistorial')
    ).order_by('-promedio')[:10]
    
    materias_rendimiento_labels = [item['idMateria__nombre'][:25] for item in materias_rendimiento]
    materias_rendimiento_values = [float(item['promedio']) if item['promedio'] else 0 for item in materias_rendimiento]
    
    calificaciones_distribucion = {
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
            calificaciones_distribucion['Excelente (18-20)'] += 1
        elif nota >= 15:
            calificaciones_distribucion['Muy Bueno (15-17)'] += 1
        elif nota >= 12:
            calificaciones_distribucion['Bueno (12-14)'] += 1
        elif nota >= 10:
            calificaciones_distribucion['Regular (10-11)'] += 1
        else:
            calificaciones_distribucion['Reprobado (0-9)'] += 1
    
    total_materias_calif = sum(calificaciones_distribucion.values())
    if total_materias_calif > 0:
        aprobadas = (calificaciones_distribucion['Excelente (18-20)'] + 
                    calificaciones_distribucion['Muy Bueno (15-17)'] + 
                    calificaciones_distribucion['Bueno (12-14)'] + 
                    calificaciones_distribucion['Regular (10-11)'])
        reprobadas = calificaciones_distribucion['Reprobado (0-9)']
        tasa_aprobacion = round((aprobadas / total_materias_calif) * 100, 1)
        tasa_reprobacion = round((reprobadas / total_materias_calif) * 100, 1)
    else:
        tasa_aprobacion = 0
        tasa_reprobacion = 0
    
    from django.db.models.functions import ExtractWeekDay
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
    
    asistencias_dias_values = asistencias_por_dia[1:] + asistencias_por_dia[:1]
    asistencias_dias_labels = dias_semana
    
    hoy = timezone.now().date()
    asistencias_semana = []
    for i in range(6, -1, -1):
        fecha = hoy - timedelta(days=i)
        count = Asistencia.objects.filter(
            idEstudiante__in=estudiantes_ids,
            fecha=fecha,
            presente=True
        ).count()
        asistencias_semana.append({
            'fecha': fecha.strftime('%d/%m'),
            'cantidad': count
        })
    
    intervenciones_recientes = Intervencion.objects.filter(
        idEstudiante__in=estudiantes_ids
    ).select_related('idEstudiante').order_by('-created_at')[:5]
    
    stats_avanzadas = obtener_estadisticas_avanzadas(universidad_id, estudiantes_ids)
    
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
        # ✅ Rol
        'rol': 'admin',
        
        # ✅ Estadísticas básicas
        'total_estudiantes': total_estudiantes,
        'activos': activos,
        'en_riesgo': en_riesgo,
        'bajo_rendimiento': stats_avanzadas.get('bajo_rendimiento', 0),
        
        # ✅ NUEVAS VARIABLES PARA USUARIOS
        'total_administradores': total_administradores,
        'total_profesores_usuario': total_profesores_usuario,
        'total_tutores_usuario': total_tutores_usuario,
        'total_estudiantes_usuario': total_estudiantes_usuario,
        'total_tutores_perfil': total_tutores_perfil,
        'total_admins_universidad': total_admins_universidad,
        'total_usuarios_sistema': total_usuarios_sistema,
        'usuarios_activos': usuarios_activos,
        'usuarios_inactivos': usuarios_inactivos,
        'porcentaje_administradores': porcentaje_administradores,
        'porcentaje_profesores': porcentaje_profesores,
        'porcentaje_tutores': porcentaje_tutores,
        'porcentaje_estudiantes': porcentaje_estudiantes,
        
        # ✅ CONTADORES PARA MÓDULOS DEL SISTEMA - ¡VERIFICAR!
        'total_materias': total_materias,  # ✅ Esta línea es la clave
        'total_carreras': total_carreras,
        'total_aulas': total_aulas,
        'total_becas': total_becas,
        'total_encuestas': total_encuestas,
        'total_tareas': total_tareas,
        'total_intervenciones': total_intervenciones,
        'total_riesgos': total_riesgos,
        'total_profesores': total_profesores,
        'total_tutores': total_tutores,
        
        # ✅ Datos para gráfico de distribución de usuarios
        'roles_labels': ['Administradores', 'Profesores', 'Tutores', 'Estudiantes'],
        'roles_values': [
            total_administradores,
            total_profesores_usuario,
            total_tutores_usuario,
            total_estudiantes_usuario
        ],
        
        # ✅ Datos para gráfico de estado de usuarios
        'estado_usuarios_labels': ['Activos', 'Inactivos'],
        'estado_usuarios_values': [usuarios_activos, usuarios_inactivos],
        
        # ✅ Gráficos existentes
        'estados_labels': [item['estado_academico'] for item in estados_data],
        'estados_values': [item['cantidad'] for item in estados_data],
        'carreras_labels': [item['idCarrera__nombre'] for item in carreras_data],
        'carreras_values': [item['cantidad'] for item in carreras_data],
        'factores_labels': [item['idFactor__nombre'] for item in factores_data],
        'factores_values': [item['cantidad'] for item in factores_data],
        'factores_riesgo': list(factores_data),
        'materias_rendimiento_labels': materias_rendimiento_labels,
        'materias_rendimiento_values': materias_rendimiento_values,
        'calificaciones_distribucion': calificaciones_distribucion,
        'tasa_aprobacion': tasa_aprobacion,
        'tasa_reprobacion': tasa_reprobacion,
        'asistencias_dias_labels': asistencias_dias_labels,
        'asistencias_dias_values': asistencias_dias_values,
        'asistencias_labels': [item['fecha'] for item in asistencias_semana],
        'asistencias_values': [item['cantidad'] for item in asistencias_semana],
        'intervenciones_recientes': intervenciones_recientes,
        'alertas_recientes': alertas_recientes,
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
        
        # ✅ Mensajes
        'mensajes_recientes': mensajes_recientes,
        'mensajes_no_leidos': mensajes_no_leidos,
        'total_mensajes': total_mensajes,
        
        # ✅ Datos de la universidad
        'universidad': request.user.idUniversidad,
        'fecha_actual': timezone.now(),
        
        # ✅ Agregar esto para depuración
        'debug_materias': total_materias,
    }
    
    # ✅ DEPURACIÓN - Imprimir en consola
    print("=" * 60)
    print("🔍 CONTADORES DEL DASHBOARD ADMIN")
    print("=" * 60)
    print(f"total_materias: {total_materias}")
    print(f"total_carreras: {total_carreras}")
    print(f"total_aulas: {total_aulas}")
    print(f"total_becas: {total_becas}")
    print(f"total_encuestas: {total_encuestas}")
    print(f"total_tareas: {total_tareas}")
    print("=" * 60)
    
    # ✅ Guardar en caché por 10 minutos
    cache.set(cache_key, context, 600)
    
    # ✅ Renderizar la plantilla con el contexto
    return render(request, 'admin/dashboard_admin.html', context)