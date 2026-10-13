# core/views/dashboard/asignacion_tutores.py

"""
Vistas para la asignación de estudiantes a tutores (Profesores)
SOLO TUTORES DE LA MISMA UNIVERSIDAD
"""
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Count, Q, Sum, F
from django.utils import timezone
from django.core.paginator import Paginator
from django.http import JsonResponse

from ...models import (
    Estudiante,
    Tutor,
    AsignacionTutor,
    Usuario,
    CatalogoCarrera,
    CatalogoUniversidad
)
from ..base import (
    get_universidad_id,
    get_universidad_nombre,
)
from ...logging_config import logger


# ============================================
# FUNCIÓN PRINCIPAL PARA OBTENER TUTORES DE LA MISMA UNIVERSIDAD
# ============================================

def _get_tutores_por_universidad(universidad_id, solo_activos=True):
    """
    Obtiene SOLO los tutores que pertenecen a la misma universidad.
    ¡ESTA ES LA FUNCIÓN CLAVE!
    """
    queryset = Tutor.objects.filter(
        usuario__idUniversidad_id=universidad_id  # 🔴 FILTRO CRÍTICO
    )
    
    if solo_activos:
        queryset = queryset.filter(activo=True)
    
    return queryset.select_related('usuario').order_by('usuario__first_name')


def _get_tutores_disponibles(universidad_id):
    """
    Obtiene los tutores activos de la universidad con sus cupos.
    """
    return _get_tutores_por_universidad(universidad_id, solo_activos=True)


def _get_estudiantes_con_asignaciones(universidad_id, filters=None):
    """Obtiene estudiantes de la universidad con sus asignaciones actuales."""
    queryset = Estudiante.objects.filter(
        idUniversidad_id=universidad_id,
        estado_academico='Activo'
    ).select_related('idUsuario', 'idCarrera')

    if filters:
        if filters.get('carrera_id'):
            queryset = queryset.filter(idCarrera_id=filters['carrera_id'])
        
        if filters.get('search'):
            search = filters['search']
            queryset = queryset.filter(
                Q(idUsuario__first_name__icontains=search) |
                Q(idUsuario__last_name__icontains=search) |
                Q(idUsuario__carnet__icontains=search) |
                Q(idUsuario__email__icontains=search)
            )
        
        if filters.get('estado_asignacion') == 'asignados':
            queryset = queryset.filter(tutores_asignados__isnull=False)
        elif filters.get('estado_asignacion') == 'no_asignados':
            queryset = queryset.filter(tutores_asignados__isnull=True)

    return queryset


def _get_asignaciones_map(estudiantes_ids, universidad_id):
    """Crea un mapa de asignaciones por estudiante (solo de la misma universidad)."""
    asignaciones = AsignacionTutor.objects.filter(
        estudiante_id__in=estudiantes_ids,
        estudiante__idUniversidad_id=universidad_id,
        estado__in=['pendiente', 'confirmada']
    ).select_related('estudiante', 'tutor', 'tutor__usuario')

    asignaciones_map = {}
    for asig in asignaciones:
        estudiante_id = asig.estudiante_id
        if estudiante_id not in asignaciones_map:
            asignaciones_map[estudiante_id] = []
        asignaciones_map[estudiante_id].append({
            'tutor_id': asig.tutor.id,
            'tutor_nombre': asig.tutor.usuario.get_full_name(),
            'estado': asig.estado,
            'asignacion_id': asig.id
        })
    
    return asignaciones_map


def _get_estadisticas_tutores_universidad(universidad_id):
    """
    Obtiene estadísticas de tutores de la universidad.
    """
    # Total de tutores activos en la universidad
    total_tutores = Tutor.objects.filter(
        usuario__idUniversidad_id=universidad_id,
        activo=True
    ).count()
    
    # Tutores con estudiantes asignados
    tutores_con_estudiantes = Tutor.objects.filter(
        usuario__idUniversidad_id=universidad_id,
        activo=True,
        estudiantes_asignados__gt=0
    ).count()
    
    # Tutores disponibles (con cupo)
    tutores_disponibles = Tutor.objects.filter(
        usuario__idUniversidad_id=universidad_id,
        activo=True
    ).exclude(
        estudiantes_asignados__gte=F('max_estudiantes')
    ).count()
    
    # Total de estudiantes con tutor (asignación confirmada)
    total_estudiantes_con_tutor = AsignacionTutor.objects.filter(
        estudiante__idUniversidad_id=universidad_id,
        estado='confirmada'
    ).values('estudiante').distinct().count()
    
    # Total de estudiantes activos
    total_estudiantes = Estudiante.objects.filter(
        idUniversidad_id=universidad_id,
        estado_academico='Activo'
    ).count()
    
    # Porcentaje de estudiantes con tutor
    if total_estudiantes > 0:
        porcentaje_con_tutor = round((total_estudiantes_con_tutor / total_estudiantes) * 100, 1)
    else:
        porcentaje_con_tutor = 0
    
    return {
        'total_tutores': total_tutores,
        'tutores_con_estudiantes': tutores_con_estudiantes,
        'tutores_disponibles': tutores_disponibles,
        'total_estudiantes_con_tutor': total_estudiantes_con_tutor,
        'total_estudiantes': total_estudiantes,
        'porcentaje_con_tutor': porcentaje_con_tutor,
    }


# ============================================
# VISTAS PRINCIPALES
# ============================================

@login_required
def asignacion_tutores_lista(request):
    """
    Lista de estudiantes para asignar a tutores.
    SOLO muestra tutores de la misma universidad.
    """
    universidad_id = get_universidad_id(request)
    
    if not universidad_id and not request.user.is_superuser:
        messages.error(request, 'No se pudo identificar tu universidad.')
        return redirect('dashboard')
    
    # Obtener filtros
    carrera_id = request.GET.get('carrera')
    search = request.GET.get('search', '')
    estado_asignacion = request.GET.get('estado_asignacion', '')
    
    # Construir filtros
    filters = {
        'carrera_id': carrera_id,
        'search': search,
        'estado_asignacion': estado_asignacion,
    }
    
    # Obtener estudiantes de la universidad
    estudiantes_qs = _get_estudiantes_con_asignaciones(universidad_id, filters)
    estudiantes_ids = list(estudiantes_qs.values_list('idEstudiante', flat=True))
    
    # Obtener mapa de asignaciones
    asignaciones_map = _get_asignaciones_map(estudiantes_ids, universidad_id)
    
    # Paginación
    paginator = Paginator(estudiantes_qs, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Obtener carreras para filtro (solo de la universidad)
    carreras = CatalogoCarrera.objects.filter(
        idUniversidad_id=universidad_id
    ).order_by('nombre')
    
    # OBTENER SOLO TUTORES DE LA MISMA UNIVERSIDAD
    tutores = _get_tutores_disponibles(universidad_id)
    
    # OBTENER ESTADÍSTICAS DE TUTORES DE LA UNIVERSIDAD
    estadisticas_tutores = _get_estadisticas_tutores_universidad(universidad_id)
    
    context = {
        'titulo': 'Asignación de Estudiantes a Tutores',
        'estudiantes': page_obj,
        'carreras': carreras,
        'tutores': tutores,
        'asignaciones_map': asignaciones_map,
        'carrera_selected': carrera_id,
        'search': search,
        'estado_asignacion': estado_asignacion,
        'total_estudiantes': estudiantes_qs.count(),
        'universidad_nombre': get_universidad_nombre(universidad_id),
        'universidad_id': universidad_id,
        
        # ✅ ESTADÍSTICAS DE TUTORES
        'total_tutores_universidad': estadisticas_tutores['total_tutores'],
        'tutores_con_estudiantes': estadisticas_tutores['tutores_con_estudiantes'],
        'tutores_disponibles': estadisticas_tutores['tutores_disponibles'],
        'total_estudiantes_con_tutor': estadisticas_tutores['total_estudiantes_con_tutor'],
        'porcentaje_con_tutor': estadisticas_tutores['porcentaje_con_tutor'],
    }
    
    return render(request, 'profesor/asignacion_tutores_lista.html', context)


@login_required
def asignacion_tutores_crear(request):
    """
    Crear asignaciones masivas de estudiantes a tutores.
    SOLO permite seleccionar tutores de la misma universidad.
    """
    if request.method != 'POST':
        return redirect('asignacion_tutores_lista')
    
    universidad_id = get_universidad_id(request)
    
    if not universidad_id and not request.user.is_superuser:
        messages.error(request, 'No se pudo identificar tu universidad.')
        return redirect('asignacion_tutores_lista')
    
    # Obtener datos del formulario
    estudiantes_ids = request.POST.getlist('estudiantes_seleccionados')
    tutor_id = request.POST.get('tutor_id')
    accion = request.POST.get('accion')
    
    # Si viene como string con comas, convertir a lista
    if estudiantes_ids and len(estudiantes_ids) == 1 and ',' in estudiantes_ids[0]:
        estudiantes_ids = estudiantes_ids[0].split(',')
    
    if not estudiantes_ids:
        messages.error(request, 'Debes seleccionar al menos un estudiante.')
        return redirect('asignacion_tutores_lista')
    
    if accion == 'remover':
        # Remover asignaciones existentes
        removidos = AsignacionTutor.objects.filter(
            estudiante_id__in=estudiantes_ids,
            estudiante__idUniversidad_id=universidad_id,
            estado='pendiente'
        ).delete()[0]
        messages.success(request, f'Se removieron {removidos} asignaciones de estudiantes.')
        return redirect('asignacion_tutores_lista')
    
    if not tutor_id:
        messages.error(request, 'Debes seleccionar un tutor.')
        return redirect('asignacion_tutores_lista')
    
    try:
        # VERIFICAR QUE EL TUTOR SEA DE LA MISMA UNIVERSIDAD
        tutor = Tutor.objects.get(
            id=tutor_id,
            usuario__idUniversidad_id=universidad_id,
            activo=True
        )
    except Tutor.DoesNotExist:
        messages.error(request, 'El tutor seleccionado no existe, no está activo o no pertenece a tu universidad.')
        return redirect('asignacion_tutores_lista')
    
    # Verificar cupos disponibles del tutor
    cupos_disponibles = tutor.max_estudiantes - tutor.estudiantes_asignados
    if len(estudiantes_ids) > cupos_disponibles:
        messages.error(
            request, 
            f'El tutor solo tiene {cupos_disponibles} cupos disponibles. '
            f'Has seleccionado {len(estudiantes_ids)} estudiantes.'
        )
        return redirect('asignacion_tutores_lista')
    
    # Crear asignaciones
    asignados = 0
    errores = 0
    
    for estudiante_id in estudiantes_ids:
        try:
            # VERIFICAR QUE EL ESTUDIANTE SEA DE LA MISMA UNIVERSIDAD
            estudiante = Estudiante.objects.get(
                idEstudiante=estudiante_id,
                idUniversidad_id=universidad_id
            )
            
            # Verificar si ya tiene una asignación confirmada
            asignacion_confirmada = AsignacionTutor.objects.filter(
                estudiante=estudiante,
                estado='confirmada'
            ).first()
            
            if asignacion_confirmada:
                errores += 1
                continue
            
            # Verificar si tiene asignación pendiente
            asignacion_pendiente = AsignacionTutor.objects.filter(
                estudiante=estudiante,
                estado='pendiente'
            ).first()
            
            if asignacion_pendiente:
                asignacion_pendiente.tutor = tutor
                asignacion_pendiente.profesor_asignador = request.user
                asignacion_pendiente.observaciones = (
                    f'Asignación actualizada por {request.user.get_full_name()} el {timezone.now().strftime("%d/%m/%Y %H:%M")}'
                )
                asignacion_pendiente.save()
                asignados += 1
            else:
                AsignacionTutor.objects.create(
                    estudiante=estudiante,
                    tutor=tutor,
                    profesor_asignador=request.user,
                    estado='pendiente',
                    observaciones=f'Asignado por {request.user.get_full_name()}'
                )
                asignados += 1
                
        except Estudiante.DoesNotExist:
            errores += 1
            continue
    
    if asignados > 0:
        messages.success(
            request, 
            f'Se asignaron {asignados} estudiantes al tutor {tutor.usuario.get_full_name()}.'
        )
    if errores > 0:
        messages.warning(
            request, 
            f'{errores} estudiantes no pudieron ser asignados (tienen asignación confirmada o no pertenecen a tu universidad).'
        )
    
    return redirect('asignacion_tutores_lista')


@login_required
def asignacion_tutores_individual(request):
    """
    Asignación individual de un estudiante a un tutor (vía AJAX).
    SOLO permite tutores de la misma universidad.
    """
    if request.method != 'POST':
        return JsonResponse({'error': 'Método no permitido'}, status=405)
    
    universidad_id = get_universidad_id(request)
    
    estudiante_id = request.POST.get('estudiante_id')
    tutor_id = request.POST.get('tutor_id')
    accion = request.POST.get('accion')
    
    if not estudiante_id:
        return JsonResponse({'error': 'ID de estudiante requerido'}, status=400)
    
    try:
        # VERIFICAR QUE EL ESTUDIANTE SEA DE LA MISMA UNIVERSIDAD
        estudiante = Estudiante.objects.get(
            idEstudiante=estudiante_id,
            idUniversidad_id=universidad_id
        )
    except Estudiante.DoesNotExist:
        return JsonResponse({'error': 'Estudiante no encontrado'}, status=404)
    
    if accion == 'remover':
        removido = AsignacionTutor.objects.filter(
            estudiante=estudiante,
            estado='pendiente'
        ).delete()[0]
        return JsonResponse({
            'success': True,
            'message': f'Asignación removida para {estudiante.nombre_completo}',
            'estado': 'sin_asignar'
        })
    
    # Asignar
    if not tutor_id:
        return JsonResponse({'error': 'ID de tutor requerido'}, status=400)
    
    try:
        # VERIFICAR QUE EL TUTOR SEA DE LA MISMA UNIVERSIDAD
        tutor = Tutor.objects.get(
            id=tutor_id,
            usuario__idUniversidad_id=universidad_id,
            activo=True
        )
    except Tutor.DoesNotExist:
        return JsonResponse({'error': 'Tutor no encontrado o no pertenece a tu universidad'}, status=404)
    
    # Verificar cupo
    if tutor.estudiantes_asignados >= tutor.max_estudiantes:
        return JsonResponse({
            'error': f'El tutor {tutor.usuario.get_full_name()} no tiene cupos disponibles'
        }, status=400)
    
    # Verificar si ya tiene asignación confirmada
    asignacion_confirmada = AsignacionTutor.objects.filter(
        estudiante=estudiante,
        estado='confirmada'
    ).first()
    
    if asignacion_confirmada:
        return JsonResponse({
            'error': f'El estudiante ya tiene una asignación confirmada con {asignacion_confirmada.tutor.usuario.get_full_name()}'
        }, status=400)
    
    # Verificar si tiene asignación pendiente
    asignacion_pendiente = AsignacionTutor.objects.filter(
        estudiante=estudiante,
        estado='pendiente'
    ).first()
    
    if asignacion_pendiente:
        asignacion_pendiente.tutor = tutor
        asignacion_pendiente.profesor_asignador = request.user
        asignacion_pendiente.save()
    else:
        AsignacionTutor.objects.create(
            estudiante=estudiante,
            tutor=tutor,
            profesor_asignador=request.user,
            estado='pendiente',
            observaciones=f'Asignado por {request.user.get_full_name()}'
        )
    
    return JsonResponse({
        'success': True,
        'message': f'Estudiante asignado a {tutor.usuario.get_full_name()}',
        'tutor_nombre': tutor.usuario.get_full_name(),
        'tutor_id': tutor.id,
        'estado': 'asignado'
    })


@login_required
def asignacion_tutores_masiva(request):
    """
    Vista para asignación masiva con selección múltiple y confirmación.
    SOLO muestra tutores de la misma universidad.
    """
    universidad_id = get_universidad_id(request)
    
    if not universidad_id and not request.user.is_superuser:
        messages.error(request, 'No se pudo identificar tu universidad.')
        return redirect('dashboard')
    
    if request.method == 'POST':
        accion = request.POST.get('accion')
        
        if accion == 'asignar_todos':
            tutor_id = request.POST.get('tutor_id')
            carrera_id = request.POST.get('carrera_id')
            
            if not tutor_id:
                messages.error(request, 'Debes seleccionar un tutor.')
                return redirect('asignacion_tutores_masiva')
            
            try:
                # VERIFICAR QUE EL TUTOR SEA DE LA MISMA UNIVERSIDAD
                tutor = Tutor.objects.get(
                    id=tutor_id,
                    usuario__idUniversidad_id=universidad_id,
                    activo=True
                )
            except Tutor.DoesNotExist:
                messages.error(request, 'El tutor seleccionado no existe, no está activo o no pertenece a tu universidad.')
                return redirect('asignacion_tutores_masiva')
            
            # Obtener estudiantes de la misma universidad
            estudiantes_qs = Estudiante.objects.filter(
                idUniversidad_id=universidad_id,
                estado_academico='Activo'
            )
            
            if carrera_id:
                estudiantes_qs = estudiantes_qs.filter(idCarrera_id=carrera_id)
            
            # Excluir estudiantes ya asignados confirmados
            estudiantes_excluidos = AsignacionTutor.objects.filter(
                estudiante__idUniversidad_id=universidad_id,
                estado='confirmada'
            ).values_list('estudiante_id', flat=True)
            
            estudiantes_qs = estudiantes_qs.exclude(idEstudiante__in=estudiantes_excluidos)
            
            total_estudiantes = estudiantes_qs.count()
            cupos_disponibles = tutor.max_estudiantes - tutor.estudiantes_asignados
            
            if total_estudiantes == 0:
                messages.warning(request, 'No hay estudiantes disponibles para asignar.')
                return redirect('asignacion_tutores_masiva')
            
            if total_estudiantes > cupos_disponibles:
                messages.error(
                    request,
                    f'El tutor solo tiene {cupos_disponibles} cupos disponibles para {total_estudiantes} estudiantes.'
                )
                return redirect('asignacion_tutores_masiva')
            
            # Asignar todos
            asignados = 0
            for estudiante in estudiantes_qs:
                asignacion_pendiente = AsignacionTutor.objects.filter(
                    estudiante=estudiante,
                    estado='pendiente'
                ).first()
                
                if asignacion_pendiente:
                    asignacion_pendiente.tutor = tutor
                    asignacion_pendiente.profesor_asignador = request.user
                    asignacion_pendiente.save()
                else:
                    AsignacionTutor.objects.create(
                        estudiante=estudiante,
                        tutor=tutor,
                        profesor_asignador=request.user,
                        estado='pendiente',
                        observaciones=f'Asignado masivamente por {request.user.get_full_name()}'
                    )
                asignados += 1
            
            messages.success(
                request,
                f'Se asignaron {asignados} estudiantes al tutor {tutor.usuario.get_full_name()}.'
            )
            return redirect('asignacion_tutores_lista')
    
    # GET: Mostrar formulario de asignación masiva
    carreras = CatalogoCarrera.objects.filter(
        idUniversidad_id=universidad_id
    ).order_by('nombre')
    
    # OBTENER SOLO TUTORES DE LA MISMA UNIVERSIDAD
    tutores = _get_tutores_disponibles(universidad_id)
    
    # OBTENER ESTADÍSTICAS DE TUTORES DE LA UNIVERSIDAD
    estadisticas_tutores = _get_estadisticas_tutores_universidad(universidad_id)
    
    context = {
        'titulo': 'Asignación Masiva de Estudiantes',
        'carreras': carreras,
        'tutores': tutores,
        'total_estudiantes': estadisticas_tutores['total_estudiantes'],
        'estudiantes_asignados': estadisticas_tutores['total_estudiantes_con_tutor'],
        'universidad_nombre': get_universidad_nombre(universidad_id),
        'universidad_id': universidad_id,
        
        # ✅ ESTADÍSTICAS DE TUTORES
        'total_tutores_universidad': estadisticas_tutores['total_tutores'],
        'tutores_con_estudiantes': estadisticas_tutores['tutores_con_estudiantes'],
        'tutores_disponibles': estadisticas_tutores['tutores_disponibles'],
        'total_estudiantes_con_tutor': estadisticas_tutores['total_estudiantes_con_tutor'],
        'porcentaje_con_tutor': estadisticas_tutores['porcentaje_con_tutor'],
        'estudiantes_pendientes': 0,  # Puedes calcularlo si lo necesitas
        'estudiantes_sin_asignar': 0,  # Puedes calcularlo si lo necesitas
    }
    
    return render(request, 'profesor/asignacion_tutores_masiva.html', context)


@login_required
def asignacion_tutores_confirmar(request, asignacion_id):
    """
    Confirmar una asignación de estudiante a tutor.
    """
    universidad_id = get_universidad_id(request)
    
    try:
        # VERIFICAR QUE LA ASIGNACIÓN SEA DE LA MISMA UNIVERSIDAD
        asignacion = AsignacionTutor.objects.get(
            id=asignacion_id,
            estudiante__idUniversidad_id=universidad_id
        )
    except AsignacionTutor.DoesNotExist:
        messages.error(request, 'La asignación no existe.')
        return redirect('asignacion_tutores_lista')
    
    if request.method == 'POST':
        if asignacion.estado == 'pendiente':
            if asignacion.tutor.estudiantes_asignados >= asignacion.tutor.max_estudiantes:
                messages.error(
                    request,
                    f'El tutor {asignacion.tutor.usuario.get_full_name()} no tiene cupos disponibles.'
                )
                return redirect('asignacion_tutores_lista')
            
            asignacion.estado = 'confirmada'
            asignacion.fecha_confirmacion = timezone.now()
            asignacion.save()
            
            asignacion.tutor.estudiantes_asignados += 1
            asignacion.tutor.save()
            
            messages.success(request, '✅ Asignación confirmada exitosamente.')
        else:
            messages.warning(request, 'Esta asignación ya fue confirmada o cancelada.')
    
    return redirect('asignacion_tutores_lista')


@login_required
def asignacion_tutores_cancelar(request, asignacion_id):
    """
    Cancelar una asignación de estudiante a tutor.
    """
    universidad_id = get_universidad_id(request)
    
    try:
        # VERIFICAR QUE LA ASIGNACIÓN SEA DE LA MISMA UNIVERSIDAD
        asignacion = AsignacionTutor.objects.get(
            id=asignacion_id,
            estudiante__idUniversidad_id=universidad_id
        )
    except AsignacionTutor.DoesNotExist:
        messages.error(request, 'La asignación no existe.')
        return redirect('asignacion_tutores_lista')
    
    if request.method == 'POST':
        if asignacion.estado == 'pendiente':
            asignacion.estado = 'cancelada'
            asignacion.save()
            messages.success(request, '✅ Asignación cancelada exitosamente.')
        elif asignacion.estado == 'confirmada':
            asignacion.tutor.estudiantes_asignados -= 1
            asignacion.tutor.save()
            asignacion.estado = 'cancelada'
            asignacion.save()
            messages.success(request, '✅ Asignación cancelada exitosamente.')
        else:
            messages.warning(request, 'Esta asignación ya fue cancelada.')
    
    return redirect('asignacion_tutores_lista')


@login_required
def asignacion_tutores_estadisticas(request):
    """
    Estadísticas de asignación de tutores.
    SOLO muestra datos de la misma universidad.
    """
    universidad_id = get_universidad_id(request)
    
    if not universidad_id and not request.user.is_superuser:
        messages.error(request, 'No se pudo identificar tu universidad.')
        return redirect('dashboard')
    
    # ============================================
    # ESTADÍSTICAS POR TUTOR (SOLO DE LA UNIVERSIDAD)
    # ============================================
    tutores_stats = Tutor.objects.filter(
        usuario__idUniversidad_id=universidad_id,
        activo=True
    ).annotate(
        total_estudiantes=Count('asignaciones', filter=Q(asignaciones__estado='confirmada'))
    ).select_related('usuario').order_by('-total_estudiantes')
    
    # ============================================
    # ESTADÍSTICAS POR CARRERA
    # ============================================
    carreras = CatalogoCarrera.objects.filter(
        idUniversidad_id=universidad_id
    )
    
    carreras_stats = []
    for carrera in carreras:
        total_estudiantes = Estudiante.objects.filter(
            idCarrera=carrera,
            estado_academico='Activo'
        ).count()
        
        estudiantes_asignados = AsignacionTutor.objects.filter(
            estudiante__idCarrera=carrera,
            estudiante__estado_academico='Activo',
            estado='confirmada'
        ).values('estudiante').distinct().count()
        
        porcentaje = round((estudiantes_asignados / total_estudiantes * 100), 2) if total_estudiantes > 0 else 0
        
        carreras_stats.append({
            'idCarrera': carrera.idCarrera,
            'nombre': carrera.nombre,
            'codigo': carrera.codigo,
            'total_estudiantes': total_estudiantes,
            'estudiantes_asignados': estudiantes_asignados,
            'porcentaje_asignados': porcentaje,
        })
    
    carreras_stats.sort(key=lambda x: x['porcentaje_asignados'], reverse=True)
    
    # ============================================
    # ESTADÍSTICAS GENERALES (SOLO DE LA UNIVERSIDAD)
    # ============================================
    total_estudiantes = Estudiante.objects.filter(
        idUniversidad_id=universidad_id,
        estado_academico='Activo'
    ).count()
    
    total_asignaciones = AsignacionTutor.objects.filter(
        estudiante__idUniversidad_id=universidad_id,
        estado='confirmada'
    ).count()
    
    total_pendientes = AsignacionTutor.objects.filter(
        estudiante__idUniversidad_id=universidad_id,
        estado='pendiente'
    ).count()
    
    estudiantes_con_tutor = AsignacionTutor.objects.filter(
        estudiante__idUniversidad_id=universidad_id,
        estado='confirmada'
    ).values('estudiante').distinct().count()
    
    estudiantes_con_asignacion_ids = AsignacionTutor.objects.filter(
        estudiante__idUniversidad_id=universidad_id,
        estado='confirmada'
    ).values_list('estudiante_id', flat=True).distinct()
    
    estudiantes_sin_tutor = Estudiante.objects.filter(
        idUniversidad_id=universidad_id,
        estado_academico='Activo'
    ).exclude(
        idEstudiante__in=estudiantes_con_asignacion_ids
    ).count()
    
    # Calcular porcentaje de ocupación por tutor
    for tutor in tutores_stats:
        if tutor.max_estudiantes > 0:
            tutor.porcentaje_ocupacion = round(
                (tutor.total_estudiantes / tutor.max_estudiantes) * 100, 2
            )
        else:
            tutor.porcentaje_ocupacion = 0
        tutor.cupos_disponibles = tutor.max_estudiantes - tutor.total_estudiantes
    
    # CONTADOR DE TUTORES DE LA UNIVERSIDAD
    total_tutores_universidad = tutores_stats.count()
    
    # OBTENER ESTADÍSTICAS DE TUTORES DE LA UNIVERSIDAD
    estadisticas_tutores = _get_estadisticas_tutores_universidad(universidad_id)
    
    context = {
        'titulo': 'Estadísticas de Asignación de Tutores',
        'tutores_stats': tutores_stats,
        'carreras_stats': carreras_stats,
        'total_tutores': total_tutores_universidad,
        'total_asignaciones': total_asignaciones,
        'total_pendientes': total_pendientes,
        'total_estudiantes': total_estudiantes,
        'estudiantes_con_tutor': estudiantes_con_tutor,
        'estudiantes_sin_tutor': estudiantes_sin_tutor,
        'universidad_nombre': get_universidad_nombre(universidad_id),
        'universidad_id': universidad_id,
        'porcentaje_asignados': round((estudiantes_con_tutor / total_estudiantes * 100), 2) if total_estudiantes > 0 else 0,
        
        # ✅ ESTADÍSTICAS DE TUTORES
        'tutores_con_estudiantes': estadisticas_tutores['tutores_con_estudiantes'],
        'tutores_disponibles': estadisticas_tutores['tutores_disponibles'],
        'total_estudiantes_con_tutor': estadisticas_tutores['total_estudiantes_con_tutor'],
        'porcentaje_con_tutor': estadisticas_tutores['porcentaje_con_tutor'],
    }
    
    return render(request, 'profesor/asignacion_tutores_estadisticas.html', context)