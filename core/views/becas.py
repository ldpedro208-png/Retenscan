# core/views/becas.py - VERSIÓN FINAL CORREGIDA

from decimal import Decimal
from functools import wraps
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.db import transaction
from django.db.models import Count, Q, Sum, Avg
from django.core.paginator import Paginator
from django.core.cache import cache
from django.utils import timezone
from datetime import datetime, timedelta

from ..models import Beca, BecaAsignacion, Estudiante, CatalogoUniversidad
from .base import get_universidad_id, logger


# ============================================
# CONSTANTES
# ============================================

TIPOS_BECA = [
    ('Académica', 'Académica'),
    ('Deportiva', 'Deportiva'),
    ('Cultural', 'Cultural'),
    ('Social', 'Social'),
    ('Investigación', 'Investigación'),
    ('Excelencia', 'Excelencia'),
    ('Necesidad', 'Necesidad'),
    ('Otra', 'Otra'),
]

ESTADOS_BECA = [
    ('Activa', 'Activa'),
    ('Inactiva', 'Inactiva'),
    ('Completa', 'Completa'),
    ('Cancelada', 'Cancelada'),
]

CACHE_TIMEOUT = 600  # 10 minutos


# ============================================
# FUNCIONES AUXILIARES
# ============================================

def parse_decimal(value, default=0):
    """
    Convierte un valor a Decimal de forma segura.
    """
    if value is None or value == '':
        return Decimal(str(default))
    try:
        return Decimal(str(value))
    except (ValueError, TypeError):
        return Decimal(str(default))


def mensaje_exito(request, accion, nombre, tipo="elemento"):
    """
    Genera un mensaje de éxito consistente.
    """
    messages.success(request, f"✅ {tipo.title()} '{nombre}' {accion} exitosamente.")


def mensaje_error(request, mensaje_texto):
    """
    Genera un mensaje de error consistente.
    """
    messages.error(request, f"❌ {mensaje_texto}")


# ============================================
# DECORADOR DE PERMISOS
# ============================================

def beca_permisos(view_func):
    """Decorador para verificar permisos de becas"""
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        user_rol = getattr(request.user, 'rol', 'estudiante')
        
        if user_rol not in ['admin', 'tutor']:
            messages.error(request, "No tienes permiso para acceder a becas.")
            return redirect('dashboard')
        
        beca_id = kwargs.get('id') or kwargs.get('pk')
        if beca_id and not request.user.is_superuser:
            try:
                beca = Beca.objects.get(id=beca_id)
                universidad_id = get_universidad_id(request)
                if beca.idUniversidad_id != universidad_id:
                    messages.error(request, "Esta beca no pertenece a tu universidad.")
                    return redirect('beca_list')
                request.beca = beca
            except Beca.DoesNotExist:
                messages.error(request, "Beca no encontrada.")
                return redirect('beca_list')
        
        return view_func(request, *args, **kwargs)
    return wrapper


# ============================================
# VISTAS
# ============================================

@login_required
@beca_permisos
def beca_list(request):
    """Lista de becas filtradas por universidad"""
    user_rol = request.user.rol
    universidad_id = get_universidad_id(request)
    
    # Caché
    cache_key = f'beca_list_{universidad_id}_{timezone.now().date()}'
    cached_context = cache.get(cache_key)
    if cached_context:
        return render(request, 'becas/beca_list.html', cached_context)
    
    # Filtros
    search = request.GET.get('search', '').strip()
    tipo = request.GET.get('tipo', '')
    estado = request.GET.get('estado', '')
    
    # Queryset
    if request.user.is_superuser:
        becas = Beca.objects.all().select_related('idUniversidad')
    else:
        becas = Beca.objects.filter(idUniversidad_id=universidad_id).select_related('idUniversidad')
    
    if search:
        becas = becas.filter(
            Q(nombre__icontains=search) |
            Q(codigo__icontains=search) |
            Q(descripcion__icontains=search)
        )
    
    if tipo:
        becas = becas.filter(tipo=tipo)
    
    if estado:
        becas = becas.filter(estado=estado)
    
    # Estadísticas
    stats = {
        'total': becas.count(),
        'activas': becas.filter(estado='Activa').count(),
        'inactivas': becas.filter(estado='Inactiva').count(),
        'completas': becas.filter(estado='Completa').count(),
        'canceladas': becas.filter(estado='Cancelada').count(),
        'total_estudiantes_beneficiados': BecaAsignacion.objects.filter(
            idBeca__in=becas,
            estado='Activa'
        ).values('idEstudiante').distinct().count(),
        'monto_total_mensual': becas.filter(estado='Activa').aggregate(
            total=Sum('monto')
        )['total'] or 0,
    }
    
    # Paginación
    paginator = Paginator(becas, 15)
    page_number = request.GET.get('page', 1)
    becas_page = paginator.get_page(page_number)
    
    context = {
        'becas': becas_page,
        'stats': stats,
        'tipos': [t[0] for t in TIPOS_BECA],
        'estados': [e[0] for e in ESTADOS_BECA],
        'search': search,
        'tipo_filtro': tipo,
        'estado_filtro': estado,
        'user_rol': user_rol,
        'universidad_id': universidad_id,
        'is_superuser': request.user.is_superuser,
        'total_registros': stats['total'],
    }
    
    cache.set(cache_key, context, CACHE_TIMEOUT)
    return render(request, 'becas/beca_list.html', context)


@login_required
@beca_permisos
def beca_create(request):
    """Crear nueva beca (solo admin)"""
    user_rol = request.user.rol
    universidad_id = get_universidad_id(request)
    
    if user_rol != 'admin':
        mensaje_error(request, "No tienes permiso para crear becas.")
        return redirect('dashboard')
    
    if request.user.is_superuser:
        universidades = CatalogoUniversidad.objects.all()
    else:
        universidades = CatalogoUniversidad.objects.filter(idUniversidad=universidad_id)
        if not universidades.exists():
            mensaje_error(request, "No tienes una universidad asignada.")
            return redirect('dashboard')
    
    if request.method == 'POST':
        nombre = request.POST.get('nombre', '').strip()
        codigo = request.POST.get('codigo', '').strip()
        descripcion = request.POST.get('descripcion', '').strip()
        tipo = request.POST.get('tipo', 'Académica')
        monto = parse_decimal(request.POST.get('monto'), 0)
        porcentaje_cobertura = parse_decimal(request.POST.get('porcentaje_cobertura'), 0)
        duracion_meses = int(request.POST.get('duracion_meses', 12))
        requisitos = request.POST.get('requisitos', '').strip()
        beneficios = request.POST.get('beneficios', '').strip()
        fecha_inicio = request.POST.get('fecha_inicio')
        fecha_fin = request.POST.get('fecha_fin')
        cupos_disponibles = int(request.POST.get('cupos_disponibles', 0))
        estado = request.POST.get('estado', 'Activa')
        universidad_id_seleccionada = request.POST.get('universidad_id')
        
        # Validaciones
        errores = []
        if not nombre:
            errores.append("El nombre de la beca es obligatorio.")
        if not codigo:
            errores.append("El código de la beca es obligatorio.")
        elif Beca.objects.filter(codigo=codigo).exists():
            errores.append(f"El código '{codigo}' ya está registrado.")
        if request.user.is_superuser and not universidad_id_seleccionada:
            errores.append("Debes seleccionar una universidad.")
        
        if errores:
            for error in errores:
                messages.error(request, f"❌ {error}")
            return render(request, 'becas/beca_form.html', {
                'universidades': universidades,
                'user_rol': user_rol,
                'tipos': TIPOS_BECA,
                'estados': ESTADOS_BECA,
                'nombre': nombre,
                'codigo': codigo,
                'descripcion': descripcion,
                'tipo': tipo,
                'monto': monto,
                'porcentaje_cobertura': porcentaje_cobertura,
                'duracion_meses': duracion_meses,
                'requisitos': requisitos,
                'beneficios': beneficios,
                'fecha_inicio': fecha_inicio,
                'fecha_fin': fecha_fin,
                'cupos_disponibles': cupos_disponibles,
                'estado': estado,
                'es_superuser': request.user.is_superuser,
            })
        
        # Asignar universidad
        if request.user.is_superuser:
            universidad = get_object_or_404(CatalogoUniversidad, idUniversidad=universidad_id_seleccionada)
        else:
            universidad = request.user.idUniversidad
            if not universidad:
                mensaje_error(request, "No tienes una universidad asignada.")
                return redirect('dashboard')
        
        # Crear beca
        try:
            with transaction.atomic():
                beca = Beca.objects.create(
                    nombre=nombre,
                    codigo=codigo,
                    descripcion=descripcion,
                    tipo=tipo,
                    monto=monto,
                    porcentaje_cobertura=porcentaje_cobertura,
                    duracion_meses=duracion_meses,
                    requisitos=requisitos,
                    beneficios=beneficios,
                    fecha_inicio=fecha_inicio if fecha_inicio else None,
                    fecha_fin=fecha_fin if fecha_fin else None,
                    cupos_disponibles=cupos_disponibles,
                    estado=estado,
                    idUniversidad=universidad,
                )
            
            cache.delete_pattern(f'beca_list_*')
            mensaje_exito(request, "creada", beca.nombre, "beca")
            return redirect('beca_list')
            
        except Exception as e:
            logger.error(f"Error creando beca: {str(e)}")
            mensaje_error(request, f"Error al crear la beca: {str(e)}")
    
    context = {
        'universidades': universidades,
        'user_rol': user_rol,
        'titulo': 'Crear Beca',
        'es_superuser': request.user.is_superuser,
        'tipos': TIPOS_BECA,
        'estados': ESTADOS_BECA,
        'duracion_meses_default': 12,
    }
    return render(request, 'becas/beca_form.html', context)


@login_required
@beca_permisos
def beca_detail(request, id):
    """Detalle de una beca"""
    user_rol = request.user.rol
    
    beca = getattr(request, 'beca', None)
    if not beca:
        beca = get_object_or_404(Beca, id=id)
    
    if not request.user.is_superuser:
        universidad_id = get_universidad_id(request)
        if beca.idUniversidad_id != universidad_id:
            mensaje_error(request, "Esta beca no pertenece a tu universidad.")
            return redirect('dashboard')
    
    asignaciones = BecaAsignacion.objects.filter(
        idBeca=beca
    ).select_related('idEstudiante', 'idEstudiante__idUsuario')
    
    stats_asignaciones = {
        'total': asignaciones.count(),
        'activas': asignaciones.filter(estado='Activa').count(),
        'finalizadas': asignaciones.filter(estado='Finalizada').count(),
        'canceladas': asignaciones.filter(estado='Cancelada').count(),
        'pendientes': asignaciones.filter(estado='Pendiente').count(),
        'monto_total': asignaciones.filter(estado='Activa').aggregate(
            total=Sum('idBeca__monto')
        )['total'] or 0,
    }
    
    tiene_beca = False
    if user_rol == 'estudiante':
        tiene_beca = asignaciones.filter(
            idEstudiante__idUsuario=request.user,
            estado='Activa'
        ).exists()
    
    context = {
        'beca': beca,
        'asignaciones': asignaciones,
        'stats_asignaciones': stats_asignaciones,
        'user_rol': user_rol,
        'puede_editar': user_rol == 'admin',
        'puede_eliminar': user_rol == 'admin',
        'puede_asignar': user_rol == 'admin',
        'tiene_beca': tiene_beca,
        'cupos_disponibles': beca.cupos_disponibles_actuales(),
    }
    return render(request, 'becas/beca_detail.html', context)


@login_required
@beca_permisos
def beca_edit(request, id):
    """Editar beca (solo admin)"""
    user_rol = request.user.rol
    
    beca = getattr(request, 'beca', None)
    if not beca:
        beca = get_object_or_404(Beca, id=id)
    
    if user_rol != 'admin':
        mensaje_error(request, "No tienes permiso para editar becas.")
        return redirect('dashboard')
    
    if not request.user.is_superuser:
        universidad_id = get_universidad_id(request)
        if beca.idUniversidad_id != universidad_id:
            mensaje_error(request, "Esta beca no pertenece a tu universidad.")
            return redirect('dashboard')
    
    if request.method == 'POST':
        nombre = request.POST.get('nombre', '').strip()
        codigo = request.POST.get('codigo', '').strip()
        descripcion = request.POST.get('descripcion', '').strip()
        tipo = request.POST.get('tipo', 'Académica')
        monto = parse_decimal(request.POST.get('monto'), 0)
        porcentaje_cobertura = parse_decimal(request.POST.get('porcentaje_cobertura'), 0)
        duracion_meses = int(request.POST.get('duracion_meses', 12))
        requisitos = request.POST.get('requisitos', '').strip()
        beneficios = request.POST.get('beneficios', '').strip()
        fecha_inicio = request.POST.get('fecha_inicio')
        fecha_fin = request.POST.get('fecha_fin')
        cupos_disponibles = int(request.POST.get('cupos_disponibles', 0))
        estado = request.POST.get('estado', 'Activa')
        
        errores = []
        if not nombre:
            errores.append("El nombre de la beca es obligatorio.")
        if not codigo:
            errores.append("El código de la beca es obligatorio.")
        elif Beca.objects.exclude(id=beca.id).filter(codigo=codigo).exists():
            errores.append(f"El código '{codigo}' ya está registrado en otra beca.")
        
        if errores:
            for error in errores:
                messages.error(request, f"❌ {error}")
            return render(request, 'becas/beca_form.html', {
                'beca': beca,
                'user_rol': user_rol,
                'tipos': TIPOS_BECA,
                'estados': ESTADOS_BECA,
                'nombre': nombre,
                'codigo': codigo,
                'descripcion': descripcion,
                'tipo': tipo,
                'monto': monto,
                'porcentaje_cobertura': porcentaje_cobertura,
                'duracion_meses': duracion_meses,
                'requisitos': requisitos,
                'beneficios': beneficios,
                'fecha_inicio': fecha_inicio,
                'fecha_fin': fecha_fin,
                'cupos_disponibles': cupos_disponibles,
                'estado': estado,
            })
        
        try:
            with transaction.atomic():
                beca.nombre = nombre
                beca.codigo = codigo
                beca.descripcion = descripcion
                beca.tipo = tipo
                beca.monto = monto
                beca.porcentaje_cobertura = porcentaje_cobertura
                beca.duracion_meses = duracion_meses
                beca.requisitos = requisitos
                beca.beneficios = beneficios
                beca.fecha_inicio = fecha_inicio if fecha_inicio else None
                beca.fecha_fin = fecha_fin if fecha_fin else None
                beca.cupos_disponibles = cupos_disponibles
                beca.estado = estado
                beca.save()
            
            cache.delete_pattern(f'beca_list_*')
            mensaje_exito(request, "actualizada", beca.nombre, "beca")
            return redirect('beca_detail', id=beca.id)
            
        except Exception as e:
            logger.error(f"Error editando beca: {str(e)}")
            mensaje_error(request, f"Error al actualizar la beca: {str(e)}")
    
    context = {
        'beca': beca,
        'user_rol': user_rol,
        'titulo': 'Editar Beca',
        'tipos': TIPOS_BECA,
        'estados': ESTADOS_BECA,
        'es_superuser': request.user.is_superuser,
    }
    return render(request, 'becas/beca_form.html', context)


@login_required
@beca_permisos
def beca_delete(request, id):
    """Eliminar beca (solo admin)"""
    user_rol = request.user.rol
    
    beca = getattr(request, 'beca', None)
    if not beca:
        beca = get_object_or_404(Beca, id=id)
    
    if user_rol != 'admin':
        mensaje_error(request, "No tienes permiso para eliminar becas.")
        return redirect('dashboard')
    
    if not request.user.is_superuser:
        universidad_id = get_universidad_id(request)
        if beca.idUniversidad_id != universidad_id:
            mensaje_error(request, "Esta beca no pertenece a tu universidad.")
            return redirect('dashboard')
    
    asignaciones_activas = BecaAsignacion.objects.filter(
        idBeca=beca,
        estado='Activa'
    ).count()
    
    if asignaciones_activas > 0:
        mensaje_error(
            request, 
            f"No se puede eliminar la beca porque tiene {asignaciones_activas} estudiantes con esta beca activa."
        )
        return redirect('beca_detail', id=beca.id)
    
    if request.method == 'POST':
        nombre = beca.nombre
        beca.delete()
        cache.delete_pattern(f'beca_list_*')
        mensaje_exito(request, "eliminada", nombre, "beca")
        return redirect('beca_list')
    
    context = {
        'beca': beca,
        'user_rol': user_rol,
        'asignaciones_count': BecaAsignacion.objects.filter(idBeca=beca).count(),
    }
    return render(request, 'becas/beca_confirm_delete.html', context)


@login_required
@beca_permisos
def beca_asignar(request, id):
    """Asignar beca a un estudiante (solo admin)"""
    user_rol = request.user.rol
    
    beca = getattr(request, 'beca', None)
    if not beca:
        beca = get_object_or_404(Beca, id=id)
    
    if user_rol != 'admin':
        mensaje_error(request, "No tienes permiso para asignar becas.")
        return redirect('dashboard')
    
    if not request.user.is_superuser:
        universidad_id = get_universidad_id(request)
        if beca.idUniversidad_id != universidad_id:
            mensaje_error(request, "Esta beca no pertenece a tu universidad.")
            return redirect('dashboard')
    
    cupos_disponibles = beca.cupos_disponibles_actuales()
    if cupos_disponibles <= 0:
        mensaje_error(request, "No hay cupos disponibles para esta beca.")
        return redirect('beca_detail', id=beca.id)
    
    estudiantes_con_beca = BecaAsignacion.objects.filter(
        idBeca=beca,
        estado__in=['Activa', 'Pendiente']
    ).values_list('idEstudiante_id', flat=True)
    
    if request.user.is_superuser:
        estudiantes = Estudiante.objects.exclude(
            idEstudiante__in=estudiantes_con_beca
        ).select_related('idUsuario')
    else:
        estudiantes = Estudiante.objects.filter(
            idCarrera__idUniversidad_id=universidad_id
        ).exclude(
            idEstudiante__in=estudiantes_con_beca
        ).select_related('idUsuario')
    
    if request.method == 'POST':
        estudiante_id = request.POST.get('estudiante_id')
        fecha_inicio = request.POST.get('fecha_inicio')
        fecha_fin = request.POST.get('fecha_fin')
        observaciones = request.POST.get('observaciones', '').strip()
        renovable = request.POST.get('renovable') == 'on'
        
        if not estudiante_id or not fecha_inicio or not fecha_fin:
            mensaje_error(request, "Todos los campos son obligatorios.")
            return render(request, 'becas/beca_asignar.html', {
                'beca': beca,
                'estudiantes': estudiantes,
                'user_rol': user_rol,
                'cupos_disponibles': cupos_disponibles,
            })
        
        estudiante = get_object_or_404(Estudiante, idEstudiante=estudiante_id)
        
        try:
            with transaction.atomic():
                asignacion = BecaAsignacion.objects.create(
                    idBeca=beca,
                    idEstudiante=estudiante,
                    fecha_inicio=fecha_inicio,
                    fecha_fin=fecha_fin,
                    estado='Activa',
                    observaciones=observaciones,
                    renovable=renovable,
                )
            
            cache.delete_pattern(f'beca_list_*')
            mensaje_exito(
                request, 
                f"asignada a {estudiante.nombre_completo}", 
                beca.nombre, 
                "beca"
            )
            return redirect('beca_detail', id=beca.id)
            
        except Exception as e:
            logger.error(f"Error asignando beca: {str(e)}")
            mensaje_error(request, f"Error al asignar la beca: {str(e)}")
    
    context = {
        'beca': beca,
        'estudiantes': estudiantes,
        'user_rol': user_rol,
        'cupos_disponibles': cupos_disponibles,
        'fecha_inicio_default': timezone.now().date(),
        'fecha_fin_default': timezone.now().date() + timedelta(days=beca.duracion_meses * 30),
    }
    return render(request, 'becas/beca_asignar.html', context)


@login_required
@beca_permisos
def beca_cancelar_asignacion(request, id):
    """Cancelar asignación de beca (solo admin)"""
    asignacion = get_object_or_404(BecaAsignacion, id=id)
    user_rol = request.user.rol
    
    if user_rol != 'admin':
        mensaje_error(request, "No tienes permiso para cancelar asignaciones de becas.")
        return redirect('dashboard')
    
    if not request.user.is_superuser:
        universidad_id = get_universidad_id(request)
        if asignacion.idBeca.idUniversidad_id != universidad_id:
            mensaje_error(request, "Esta beca no pertenece a tu universidad.")
            return redirect('dashboard')
    
    if request.method == 'POST':
        asignacion.estado = 'Cancelada'
        asignacion.save()
        cache.delete_pattern(f'beca_list_*')
        mensaje_exito(
            request, 
            f"cancelada para {asignacion.idEstudiante.nombre_completo}", 
            asignacion.idBeca.nombre, 
            "asignación de beca"
        )
        return redirect('beca_detail', id=asignacion.idBeca.id)
    
    context = {
        'asignacion': asignacion,
        'user_rol': user_rol,
    }
    return render(request, 'becas/beca_cancelar_asignacion.html', context)


@login_required
@beca_permisos
def beca_estudiantes(request, id):
    """Lista de estudiantes con beca"""
    user_rol = request.user.rol
    
    beca = getattr(request, 'beca', None)
    if not beca:
        beca = get_object_or_404(Beca, id=id)
    
    if user_rol not in ['admin', 'tutor']:
        mensaje_error(request, "No tienes permiso para ver esta lista.")
        return redirect('dashboard')
    
    if not request.user.is_superuser:
        universidad_id = get_universidad_id(request)
        if beca.idUniversidad_id != universidad_id:
            mensaje_error(request, "Esta beca no pertenece a tu universidad.")
            return redirect('dashboard')
    
    asignaciones = BecaAsignacion.objects.filter(
        idBeca=beca
    ).select_related('idEstudiante', 'idEstudiante__idUsuario')
    
    context = {
        'beca': beca,
        'asignaciones': asignaciones,
        'user_rol': user_rol,
    }
    return render(request, 'becas/beca_estudiantes.html', context)