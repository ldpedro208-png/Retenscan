# core/views/aulas.py

from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.db.models import Count, Q
from django.core.paginator import Paginator
from ..models import CatalogoAula, CatalogoUniversidad
from .base import get_universidad_id, logger


@login_required
def aula_list(request):
    """Listar aulas (solo admin) — filtrado por universidad"""
    user_rol = request.user.rol
    universidad_id = get_universidad_id(request)

    if user_rol != 'admin':
        messages.error(request, "No tienes permiso para ver aulas.")
        return redirect('dashboard')

    # ✅ CAMBIO: filtrar por universidad
    if request.user.is_superuser:
        aulas = CatalogoAula.objects.all().select_related('idUniversidad').order_by('nombre')
    else:
        aulas = CatalogoAula.objects.filter(
            idUniversidad_id=universidad_id
        ).select_related('idUniversidad').order_by('nombre')

    context = {
        'aulas': aulas,
        'total': aulas.count(),
        'user_rol': user_rol,
        'titulo': 'Lista de Aulas',
    }
    return render(request, 'admin/aula_list.html', context)


@login_required
def aula_create(request):
    """Crear nueva aula (solo admin)"""
    user_rol = request.user.rol
    universidad_id = get_universidad_id(request)

    # Verificar permisos
    if user_rol != 'admin':
        messages.error(request, "No tienes permiso para crear aulas.")
        return redirect('dashboard')

    # ✅ CAMBIO: verificar que el usuario tenga universidad
    if not request.user.is_superuser and not universidad_id:
        messages.error(request, "No tienes una universidad asignada. Contacta al administrador.")
        return redirect('dashboard')

    # Variables base del contexto
    context_base = {
        'user_rol': user_rol,
        'titulo': 'Crear Aula',
        'tipos': ['Teoria', 'Laboratorio', 'Taller', 'Virtual'],
        'codigo': '',
        'nombre': '',
        'capacidad': 30,
        'tipo': 'Teoria',
    }

    if request.method == 'POST':
        codigo = request.POST.get('codigo', '').strip()
        nombre = request.POST.get('nombre', '').strip()
        capacidad = request.POST.get('capacidad', 30)
        tipo = request.POST.get('tipo', 'Teoria')

        # Validaciones
        if not codigo or not nombre:
            messages.error(request, "Código y nombre son obligatorios.")
            context = context_base.copy()
            context.update({
                'codigo': codigo,
                'nombre': nombre,
                'capacidad': capacidad,
                'tipo': tipo,
            })
            return render(request, 'admin/aula_form.html', context)

        # Verificar código único — ✅ CAMBIO: solo dentro de la misma universidad
        if request.user.is_superuser:
            existe_codigo = CatalogoAula.objects.filter(codigo=codigo).exists()
        else:
            existe_codigo = CatalogoAula.objects.filter(
                codigo=codigo,
                idUniversidad_id=universidad_id
            ).exists()

        if existe_codigo:
            messages.error(request, f"El código '{codigo}' ya está registrado en tu universidad.")
            context = context_base.copy()
            context.update({
                'codigo': codigo,
                'nombre': nombre,
                'capacidad': capacidad,
                'tipo': tipo,
            })
            return render(request, 'admin/aula_form.html', context)

        # Crear aula
        try:
            # ✅ CAMBIO: asignar idUniversidad
            aula = CatalogoAula.objects.create(
                codigo=codigo,
                nombre=nombre,
                capacidad=int(capacidad) if capacidad else 30,
                tipo=tipo,
                idUniversidad=request.user.idUniversidad,  # ← ✅ ASIGNAR UNIVERSIDAD
            )

            messages.success(request, f"✅ Aula '{aula.nombre}' creada exitosamente.")
            return redirect('aula_list')

        except Exception as e:
            logger.error(f"Error creando aula: {str(e)}")
            messages.error(request, f"Error al crear el aula: {str(e)}")
            context = context_base.copy()
            context.update({
                'codigo': codigo,
                'nombre': nombre,
                'capacidad': capacidad,
                'tipo': tipo,
            })
            return render(request, 'admin/aula_form.html', context)

    # GET request
    return render(request, 'admin/aula_form.html', context_base)


@login_required
def aula_detail(request, id):
    """Detalle de un aula"""
    aula = get_object_or_404(CatalogoAula, id=id)
    user_rol = request.user.rol

    # Verificar permisos
    if user_rol not in ['admin', 'profesor']:
        messages.error(request, "No tienes permiso para ver esta aula.")
        return redirect('dashboard')

    # Verificar que pertenece a la universidad del usuario
    if not request.user.is_superuser:
        if aula.idUniversidad_id != request.user.idUniversidad_id:
            messages.error(request, "Esta aula no pertenece a tu universidad.")
            return redirect('dashboard')

    context = {
        'aula': aula,
        'user_rol': user_rol,
        'puede_editar': user_rol == 'admin',
        'puede_eliminar': user_rol == 'admin',
    }
    return render(request, 'aulas/aula_detail.html', context)


@login_required
def aula_edit(request, id):
    """Editar aula (solo admin)"""
    aula = get_object_or_404(CatalogoAula, id=id)
    user_rol = request.user.rol

    # Verificar permisos
    if user_rol != 'admin':
        messages.error(request, "No tienes permiso para editar aulas.")
        return redirect('dashboard')

    # Verificar que pertenece a la universidad del usuario
    if not request.user.is_superuser:
        if aula.idUniversidad_id != request.user.idUniversidad_id:
            messages.error(request, "Esta aula no pertenece a tu universidad.")
            return redirect('dashboard')

    if request.method == 'POST':
        nombre = request.POST.get('nombre')
        codigo = request.POST.get('codigo')
        capacidad = request.POST.get('capacidad', 0)
        ubicacion = request.POST.get('ubicacion', '')
        tiene_proyector = request.POST.get('tiene_proyector') == 'on'
        tiene_pizarra = request.POST.get('tiene_pizarra') == 'on'
        tiene_aire_acondicionado = request.POST.get('tiene_aire_acondicionado') == 'on'
        estado = request.POST.get('estado', 'Disponible')

        # Validaciones
        if not nombre or not codigo:
            messages.error(request, "Nombre y código son obligatorios.")
            return render(request, 'aulas/aula_form.html', {
                'aula': aula,
                'user_rol': user_rol,
                'estados': ['Disponible', 'Ocupada', 'Mantenimiento', 'Inactiva'],
            })

        # ✅ CAMBIO: verificar código único excluyendo el actual (con filtro correcto)
        existe_codigo = CatalogoAula.objects.exclude(id=aula.id).filter(codigo=codigo)
        if not request.user.is_superuser:
            existe_codigo = existe_codigo.filter(idUniversidad_id=aula.idUniversidad_id)

        if existe_codigo.exists():
            messages.error(request, f"El código '{codigo}' ya está registrado en otra aula.")
            return render(request, 'aulas/aula_form.html', {
                'aula': aula,
                'user_rol': user_rol,
                'estados': ['Disponible', 'Ocupada', 'Mantenimiento', 'Inactiva'],
            })

        # Actualizar aula
        aula.nombre = nombre
        aula.codigo = codigo
        aula.capacidad = int(capacidad) if capacidad else 0
        aula.ubicacion = ubicacion
        aula.tiene_proyector = tiene_proyector
        aula.tiene_pizarra = tiene_pizarra
        aula.tiene_aire_acondicionado = tiene_aire_acondicionado
        aula.estado = estado
        aula.save()

        messages.success(request, f"✅ Aula '{aula.nombre}' actualizada exitosamente.")
        return redirect('aula_detail', id=aula.id)

    context = {
        'aula': aula,
        'user_rol': user_rol,
        'titulo': 'Editar Aula',
        'estados': ['Disponible', 'Ocupada', 'Mantenimiento', 'Inactiva'],
        'es_superuser': request.user.is_superuser,
    }
    return render(request, 'aulas/aula_form.html', context)


@login_required
def aula_delete(request, id):
    """Eliminar aula (solo admin)"""
    aula = get_object_or_404(CatalogoAula, id=id)
    user_rol = request.user.rol

    # Verificar permisos
    if user_rol != 'admin':
        messages.error(request, "No tienes permiso para eliminar aulas.")
        return redirect('dashboard')

    # Verificar que pertenece a la universidad del usuario
    if not request.user.is_superuser:
        if aula.idUniversidad_id != request.user.idUniversidad_id:
            messages.error(request, "Esta aula no pertenece a tu universidad.")
            return redirect('dashboard')

    if request.method == 'POST':
        nombre = aula.nombre
        aula.delete()
        messages.success(request, f"✅ Aula '{nombre}' eliminada exitosamente.")
        return redirect('aula_list')

    context = {
        'aula': aula,
        'user_rol': user_rol,
    }
    return render(request, 'aulas/aula_confirm_delete.html', context)


@login_required
def aula_cambiar_estado(request, id):
    """Cambiar estado de un aula (solo admin)"""
    aula = get_object_or_404(CatalogoAula, id=id)
    user_rol = request.user.rol

    # Verificar permisos
    if user_rol != 'admin':
        messages.error(request, "No tienes permiso para cambiar el estado del aula.")
        return redirect('dashboard')

    # Verificar que pertenece a la universidad del usuario
    if not request.user.is_superuser:
        if aula.idUniversidad_id != request.user.idUniversidad_id:
            messages.error(request, "Esta aula no pertenece a tu universidad.")
            return redirect('dashboard')

    if request.method == 'POST':
        nuevo_estado = request.POST.get('estado')
        if nuevo_estado in ['Disponible', 'Ocupada', 'Mantenimiento', 'Inactiva']:
            aula.estado = nuevo_estado
            aula.save()
            messages.success(request, f"✅ Estado del aula actualizado a '{nuevo_estado}'.")
        else:
            messages.error(request, "Estado inválido.")

    return redirect('aula_detail', id=aula.id)