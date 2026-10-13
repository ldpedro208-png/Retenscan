# core/views/admin/carreras.py

"""
Vistas para la gestión de carreras (Administradores de universidad)
"""
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Count, Q
from django.core.cache import cache
from django.utils import timezone
from django.http import JsonResponse, HttpResponse
from django.core.paginator import Paginator
import json
import logging

from ...models import (
    CatalogoCarrera,
    CatalogoUniversidad,
    Estudiante,
    Usuario
)
from ..base import get_universidad_id, logger


# ============================================
# LISTAR CARRERAS
# ============================================
@login_required
def carrera_list(request):
    """
    Listar carreras de la universidad del administrador
    """
    user_rol = getattr(request.user, 'rol', 'estudiante')
    universidad_id = get_universidad_id(request)
    
    if user_rol != 'admin':
        messages.error(request, "No tienes permiso para ver carreras.")
        return redirect('dashboard')
    
    if not universidad_id:
        messages.error(request, "No tienes una universidad asociada.")
        return redirect('dashboard')
    
    carreras = CatalogoCarrera.objects.filter(
        idUniversidad_id=universidad_id
    ).annotate(
        total_estudiantes=Count('estudiantes', filter=Q(estudiantes__estado_academico='Activo')),
        total_egresados=Count('estudiantes', filter=Q(estudiantes__estado_academico='Egresado')),
        total_abandonados=Count('estudiantes', filter=Q(estudiantes__estado_academico='Abandonado'))
    ).order_by('nombre')
    
    universidad = CatalogoUniversidad.objects.get(idUniversidad=universidad_id)
    
    total_carreras = carreras.count()
    total_estudiantes = sum(c.total_estudiantes for c in carreras)
    
    context = {
        'carreras': carreras,
        'universidad': universidad,
        'total_carreras': total_carreras,
        'total_estudiantes': total_estudiantes,
        'user_rol': user_rol,
        'titulo': 'Gestión de Carreras',
    }
    
    return render(request, 'admin/carrera_list.html', context)


# ============================================
# CREAR CARRERA
# ============================================
@login_required
def carrera_create(request):
    user_rol = request.user.rol
    user_rol_display = request.user.get_rol_display()
    
    universidad_id = get_universidad_id(request)
    
    # Verificar si es administrador
    if user_rol != 'admin':
        messages.error(request, "No tienes permiso para crear carreras.")
        return redirect('dashboard')
    
    if not universidad_id:
        messages.error(request, "No tienes una universidad asociada.")
        return redirect('dashboard')
    
    universidad = CatalogoUniversidad.objects.get(idUniversidad=universidad_id)
    
    # Variables que siempre estarán en el contexto
    context_base = {
        'universidad': universidad,
        'user_rol': user_rol,
        'titulo': 'Nueva Carrera',
        'duracion_semestres': 10,
        'nombre': '',  # <- Siempre presente
        'codigo': '',  # <- Siempre presente
    }
    
    if request.method == 'POST':
        nombre = request.POST.get('nombre', '').strip()
        codigo = request.POST.get('codigo', '').strip()
        duracion_semestres = request.POST.get('duracion_semestres', 10)
        
        if not nombre:
            messages.error(request, "El nombre de la carrera es obligatorio.")
            context = context_base.copy()
            context.update({
                'nombre': nombre,
                'codigo': codigo,
                'duracion_semestres': duracion_semestres,
            })
            return render(request, 'admin/carrera_form.html', context)
        
        if CatalogoCarrera.objects.filter(
            idUniversidad_id=universidad_id,
            nombre__iexact=nombre
        ).exists():
            messages.error(request, f"Ya existe una carrera con el nombre '{nombre}'.")
            context = context_base.copy()
            context.update({
                'nombre': nombre,
                'codigo': codigo,
                'duracion_semestres': duracion_semestres,
            })
            return render(request, 'admin/carrera_form.html', context)
        
        if codigo and CatalogoCarrera.objects.filter(
            codigo__iexact=codigo
        ).exists():
            messages.error(request, f"Ya existe una carrera con el código '{codigo}'.")
            context = context_base.copy()
            context.update({
                'nombre': nombre,
                'codigo': codigo,
                'duracion_semestres': duracion_semestres,
            })
            return render(request, 'admin/carrera_form.html', context)
        
        try:
            carrera = CatalogoCarrera.objects.create(
                nombre=nombre,
                codigo=codigo or None,
                duracion_semestres=int(duracion_semestres),
                idUniversidad=universidad
            )
            
            messages.success(
                request, 
                f"✅ Carrera '{carrera.nombre}' creada exitosamente."
            )
            
            cache.delete(f'carreras_universidad_{universidad_id}')
            
            return redirect('carrera_list')
            
        except Exception as e:
            logger.error(f"Error creando carrera: {str(e)}")
            messages.error(request, f"Error al crear la carrera: {str(e)}")
            context = context_base.copy()
            context.update({
                'nombre': nombre,
                'codigo': codigo,
                'duracion_semestres': duracion_semestres,
            })
            return render(request, 'admin/carrera_form.html', context)
    
    # GET request - usa el contexto base que ya tiene nombre='' y codigo=''
    return render(request, 'admin/carrera_form.html', context_base)

# ============================================
# DETALLE DE CARRERA
# ============================================
@login_required
def carrera_detail(request, pk):
    """
    Ver detalle de una carrera
    """
    user_rol = getattr(request.user, 'rol', 'estudiante')
    universidad_id = get_universidad_id(request)
    
    if user_rol != 'admin':
        messages.error(request, "No tienes permiso para ver detalles de carreras.")
        return redirect('dashboard')
    
    if not universidad_id:
        messages.error(request, "No tienes una universidad asociada.")
        return redirect('dashboard')
    
    carrera = get_object_or_404(
        CatalogoCarrera.objects.annotate(
            total_estudiantes=Count('estudiantes'),
            activos=Count('estudiantes', filter=Q(estudiantes__estado_academico='Activo')),
            inactivos=Count('estudiantes', filter=Q(estudiantes__estado_academico='Inactivo')),
            egresados=Count('estudiantes', filter=Q(estudiantes__estado_academico='Egresado')),
            abandonados=Count('estudiantes', filter=Q(estudiantes__estado_academico='Abandonado'))
        ),
        idCarrera=pk,
        idUniversidad_id=universidad_id
    )
    
    estudiantes = Estudiante.objects.filter(
        idCarrera=carrera
    ).select_related('idUsuario').order_by('idUsuario__last_name')[:50]
    
    context = {
        'carrera': carrera,
        'estudiantes': estudiantes,
        'user_rol': user_rol,
        'titulo': f'Detalle de {carrera.nombre}',
    }
    return render(request, 'admin/carrera_detail.html', context)


# ============================================
# EDITAR CARRERA
# ============================================
@login_required
def carrera_edit(request, pk):
    """
    Editar una carrera existente
    """
    user_rol = getattr(request.user, 'rol', 'estudiante')
    universidad_id = get_universidad_id(request)
    
    if user_rol != 'admin':
        messages.error(request, "No tienes permiso para editar carreras.")
        return redirect('dashboard')
    
    if not universidad_id:
        messages.error(request, "No tienes una universidad asociada.")
        return redirect('dashboard')
    
    carrera = get_object_or_404(
        CatalogoCarrera.objects.annotate(
            total_estudiantes=Count('estudiantes')
        ),
        idCarrera=pk,
        idUniversidad_id=universidad_id
    )
    
    universidad = carrera.idUniversidad
    
    if request.method == 'POST':
        nombre = request.POST.get('nombre', '').strip()
        codigo = request.POST.get('codigo', '').strip()
        duracion_semestres = request.POST.get('duracion_semestres', 10)
        
        if not nombre:
            messages.error(request, "El nombre de la carrera es obligatorio.")
            return render(request, 'admin/carrera_form.html', {
                'carrera': carrera,
                'universidad': universidad,
                'user_rol': user_rol,
                'titulo': 'Editar Carrera',
                'editando': True,
            })
        
        if CatalogoCarrera.objects.filter(
            idUniversidad_id=universidad_id,
            nombre__iexact=nombre
        ).exclude(idCarrera=pk).exists():
            messages.error(request, f"Ya existe una carrera con el nombre '{nombre}'.")
            return render(request, 'admin/carrera_form.html', {
                'carrera': carrera,
                'universidad': universidad,
                'user_rol': user_rol,
                'titulo': 'Editar Carrera',
                'editando': True,
            })
        
        if codigo and CatalogoCarrera.objects.filter(
            codigo__iexact=codigo
        ).exclude(idCarrera=pk).exists():
            messages.error(request, f"Ya existe una carrera con el código '{codigo}'.")
            return render(request, 'admin/carrera_form.html', {
                'carrera': carrera,
                'universidad': universidad,
                'user_rol': user_rol,
                'titulo': 'Editar Carrera',
                'editando': True,
            })
        
        try:
            carrera.nombre = nombre
            carrera.codigo = codigo or None
            carrera.duracion_semestres = int(duracion_semestres)
            carrera.save()
            
            messages.success(
                request, 
                f"✅ Carrera '{carrera.nombre}' actualizada exitosamente."
            )
            
            cache.delete(f'carreras_universidad_{universidad_id}')
            
            return redirect('carrera_list')
            
        except Exception as e:
            logger.error(f"Error actualizando carrera: {str(e)}")
            messages.error(request, f"Error al actualizar la carrera: {str(e)}")
            return render(request, 'admin/carrera_form.html', {
                'carrera': carrera,
                'universidad': universidad,
                'user_rol': user_rol,
                'titulo': 'Editar Carrera',
                'editando': True,
            })
    
    context = {
        'carrera': carrera,
        'universidad': universidad,
        'user_rol': user_rol,
        'titulo': 'Editar Carrera',
        'editando': True,
        'total_estudiantes': getattr(carrera, 'total_estudiantes', 0),
    }
    return render(request, 'admin/carrera_form.html', context)


# ============================================
# ELIMINAR CARRERA
# ============================================
@login_required
def carrera_delete(request, pk):
    """
    Eliminar una carrera (solo si no tiene estudiantes)
    """
    user_rol = getattr(request.user, 'rol', 'estudiante')
    universidad_id = get_universidad_id(request)
    
    if user_rol != 'admin':
        messages.error(request, "No tienes permiso para eliminar carreras.")
        return redirect('dashboard')
    
    if not universidad_id:
        messages.error(request, "No tienes una universidad asociada.")
        return redirect('dashboard')
    
    carrera = get_object_or_404(
        CatalogoCarrera.objects.annotate(
            total_estudiantes=Count('estudiantes')
        ),
        idCarrera=pk,
        idUniversidad_id=universidad_id
    )
    
    if request.method == 'POST':
        if carrera.total_estudiantes > 0:
            messages.error(
                request, 
                f"No se puede eliminar la carrera '{carrera.nombre}' porque tiene "
                f"{carrera.total_estudiantes} estudiantes asignados."
            )
            return redirect('carrera_list')
        
        try:
            nombre = carrera.nombre
            carrera.delete()
            
            messages.success(
                request, 
                f"✅ Carrera '{nombre}' eliminada exitosamente."
            )
            
            cache.delete(f'carreras_universidad_{universidad_id}')
            
        except Exception as e:
            logger.error(f"Error eliminando carrera: {str(e)}")
            messages.error(request, f"Error al eliminar la carrera: {str(e)}")
        
        return redirect('carrera_list')
    
    context = {
        'carrera': carrera,
        'total_estudiantes': getattr(carrera, 'total_estudiantes', 0),
        'user_rol': user_rol,
        'titulo': 'Eliminar Carrera',
    }
    return render(request, 'admin/carrera_confirm_delete.html', context)


# ============================================
# API: OBTENER CARRERAS (AJAX)
# ============================================
@login_required
def carrera_api(request):
    """
    API para obtener carreras de la universidad (para selects dinámicos)
    """
    user_rol = getattr(request.user, 'rol', 'estudiante')
    universidad_id = get_universidad_id(request)
    
    if user_rol != 'admin':
        return JsonResponse({'error': 'No autorizado'}, status=403)
    
    if not universidad_id:
        return JsonResponse({'error': 'Sin universidad'}, status=400)
    
    carreras = CatalogoCarrera.objects.filter(
        idUniversidad_id=universidad_id
    ).values('idCarrera', 'nombre', 'codigo')
    
    return JsonResponse({'carreras': list(carreras)}, safe=False)