# core/views/materias.py - VERSIÓN CORREGIDA

from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.db.models import Count, Avg, Q
from ..models import CatalogoMateria, CatalogoUniversidad, Estudiante, CatalogoCarrera
from .base import get_universidad_id, logger


@login_required
def materia_list(request):
    """Lista de materias (usando catálogo)"""
    user_rol = request.user.rol
    universidad_id = get_universidad_id(request)

    # Verificar permisos
    if user_rol not in ['admin', 'profesor']:
        messages.error(request, "No tienes permiso para ver esta lista.")
        return redirect('dashboard')

    # Usar CatalogoMateria en lugar de Materia
    if request.user.is_superuser:
        materias = CatalogoMateria.objects.all().select_related('idCarrera__idUniversidad')
    else:
        # Filtrar por universidad a través de la carrera
        materias = CatalogoMateria.objects.filter(
            idCarrera__idUniversidad_id=universidad_id
        ).select_related('idCarrera__idUniversidad')

    context = {
        'materias': materias,
        'total': materias.count(),
        'user_rol': user_rol,
    }
    return render(request, 'materias/materia_list.html', context)


@login_required
def materia_create(request):
    """Crear nueva materia (solo admin)"""
    user_rol = request.user.rol
    universidad_id = get_universidad_id(request)

    # Verificar permisos
    if user_rol != 'admin':
        messages.error(request, "No tienes permiso para crear materias.")
        return redirect('dashboard')

    # Obtener carreras disponibles
    if request.user.is_superuser:
        carreras = CatalogoCarrera.objects.all().select_related('idUniversidad')
    else:
        carreras = CatalogoCarrera.objects.filter(
            idUniversidad_id=universidad_id
        ).select_related('idUniversidad')
        if not carreras.exists():
            messages.error(request, "No hay carreras disponibles en tu universidad.")
            return redirect('dashboard')

    if request.method == 'POST':
        nombre = request.POST.get('nombre')
        codigo = request.POST.get('codigo')
        creditos = request.POST.get('creditos', 3)
        semestre_curricular = request.POST.get('semestre_curricular')
        carrera_id = request.POST.get('carrera_id')

        # DEBUG
        logger.debug(f"carrera_id recibido: {carrera_id}")
        logger.debug(f"POST data: {request.POST}")

        # Validaciones
        if not nombre:
            messages.error(request, "El nombre de la materia es obligatorio.")
            return render(request, 'materias/materia_form.html', {
                'carreras': carreras,
                'user_rol': user_rol,
                'titulo': 'Crear Materia',
                'es_superuser': request.user.is_superuser,
            })

        if not carrera_id:
            messages.error(request, "Debes seleccionar una carrera.")
            return render(request, 'materias/materia_form.html', {
                'carreras': carreras,
                'user_rol': user_rol,
                'titulo': 'Crear Materia',
                'es_superuser': request.user.is_superuser,
            })

        # Obtener la carrera - Usar idCarrera en lugar de id
        try:
            carrera = CatalogoCarrera.objects.get(idCarrera=int(carrera_id))
        except CatalogoCarrera.DoesNotExist:
            messages.error(request, "La carrera seleccionada no existe.")
            return render(request, 'materias/materia_form.html', {
                'carreras': carreras,
                'user_rol': user_rol,
                'titulo': 'Crear Materia',
                'es_superuser': request.user.is_superuser,
            })
        except ValueError:
            messages.error(request, "ID de carrera inválido.")
            return render(request, 'materias/materia_form.html', {
                'carreras': carreras,
                'user_rol': user_rol,
                'titulo': 'Crear Materia',
                'es_superuser': request.user.is_superuser,
            })

        # Verificar que la carrera pertenezca a la universidad del usuario
        if not request.user.is_superuser and carrera.idUniversidad_id != universidad_id:
            messages.error(request, "La carrera seleccionada no pertenece a tu universidad.")
            return render(request, 'materias/materia_form.html', {
                'carreras': carreras,
                'user_rol': user_rol,
                'titulo': 'Crear Materia',
                'es_superuser': request.user.is_superuser,
            })

        # Verificar si ya existe una materia con ese código (si se proporcionó)
        if codigo and CatalogoMateria.objects.filter(codigo=codigo).exists():
            messages.error(request, f"Ya existe una materia con el código '{codigo}'.")
            return render(request, 'materias/materia_form.html', {
                'carreras': carreras,
                'user_rol': user_rol,
                'titulo': 'Crear Materia',
                'es_superuser': request.user.is_superuser,
            })

        # Verificar si ya existe una materia con ese nombre en la misma carrera
        if CatalogoMateria.objects.filter(nombre=nombre, idCarrera=carrera).exists():
            messages.error(request, f"Ya existe una materia con el nombre '{nombre}' en esta carrera.")
            return render(request, 'materias/materia_form.html', {
                'carreras': carreras,
                'user_rol': user_rol,
                'titulo': 'Crear Materia',
                'es_superuser': request.user.is_superuser,
            })

        # Crear materia
        try:
            materia = CatalogoMateria.objects.create(
                idCarrera=carrera,
                nombre=nombre,
                codigo=codigo if codigo else None,
                creditos=int(creditos) if creditos else 3,
                semestre_curricular=int(semestre_curricular) if semestre_curricular else None
            )
            messages.success(request, f"✅ Materia '{materia.nombre}' creada exitosamente.")
            return redirect('materia_list')
        except Exception as e:
            messages.error(request, f"Error al crear la materia: {str(e)}")
            return render(request, 'materias/materia_form.html', {
                'carreras': carreras,
                'user_rol': user_rol,
                'titulo': 'Crear Materia',
                'es_superuser': request.user.is_superuser,
            })

    context = {
        'carreras': carreras,
        'user_rol': user_rol,
        'titulo': 'Crear Materia',
        'es_superuser': request.user.is_superuser,
        'materia': None,
    }
    return render(request, 'materias/materia_form.html', context)


@login_required
def materia_detail(request, id):
    """Detalle de una materia"""
    materia = get_object_or_404(
        CatalogoMateria.objects.select_related('idCarrera__idUniversidad'),
        id=id
    )
    user_rol = request.user.rol

    # Verificar permisos
    if user_rol not in ['admin', 'profesor']:
        messages.error(request, "No tienes permiso para ver esta materia.")
        return redirect('dashboard')

    # ✅ CAMBIO: materia.idUniversidad_id NO existe → usar idCarrera.idUniversidad_id
    if not request.user.is_superuser:
        if materia.idCarrera.idUniversidad_id != request.user.idUniversidad_id:
            messages.error(request, "Esta materia no pertenece a tu universidad.")
            return redirect('dashboard')

    # ✅ CAMBIO: Estudiante.objects.filter(idMateria=materia) NO existe
    # Los estudiantes se relacionan vía HistorialAcademico
    from ..models import HistorialAcademico
    estudiantes = Estudiante.objects.filter(
        historial_academico__idMateria=materia
    ).select_related('idUsuario').distinct()

    context = {
        'materia': materia,
        'estudiantes': estudiantes,
        'total_estudiantes': estudiantes.count(),
        'user_rol': user_rol,
        'puede_editar': user_rol == 'admin',
    }
    return render(request, 'materias/materia_detail.html', context)


@login_required
def materia_edit(request, materia_id):
    """Editar materia existente (solo admin)"""
    user_rol = request.user.rol
    universidad_id = get_universidad_id(request)

    if user_rol != 'admin':
        messages.error(request, "No tienes permiso para editar materias.")
        return redirect('dashboard')

    # Obtener la materia
    try:
        materia = CatalogoMateria.objects.select_related('idCarrera__idUniversidad').get(id=materia_id)
    except CatalogoMateria.DoesNotExist:
        messages.error(request, "La materia no existe.")
        return redirect('materia_list')

    # Verificar permisos
    if not request.user.is_superuser and materia.idCarrera.idUniversidad_id != universidad_id:
        messages.error(request, "No tienes permiso para editar esta materia.")
        return redirect('materia_list')

    # Obtener carreras disponibles
    if request.user.is_superuser:
        carreras = CatalogoCarrera.objects.all().select_related('idUniversidad')
    else:
        carreras = CatalogoCarrera.objects.filter(
            idUniversidad_id=universidad_id
        ).select_related('idUniversidad')

    if request.method == 'POST':
        nombre = request.POST.get('nombre')
        codigo = request.POST.get('codigo')
        creditos = request.POST.get('creditos', 3)
        semestre_curricular = request.POST.get('semestre_curricular')
        carrera_id = request.POST.get('carrera_id')

        if not nombre:
            messages.error(request, "El nombre de la materia es obligatorio.")
            return render(request, 'materias/materia_form.html', {
                'materia': materia,
                'carreras': carreras,
                'user_rol': user_rol,
                'titulo': 'Editar Materia',
                'es_superuser': request.user.is_superuser,
            })

        if not carrera_id:
            messages.error(request, "Debes seleccionar una carrera.")
            return render(request, 'materias/materia_form.html', {
                'materia': materia,
                'carreras': carreras,
                'user_rol': user_rol,
                'titulo': 'Editar Materia',
                'es_superuser': request.user.is_superuser,
            })

        try:
            carrera = CatalogoCarrera.objects.get(idCarrera=carrera_id)
        except CatalogoCarrera.DoesNotExist:
            messages.error(request, "La carrera seleccionada no existe.")
            return render(request, 'materias/materia_form.html', {
                'materia': materia,
                'carreras': carreras,
                'user_rol': user_rol,
                'titulo': 'Editar Materia',
                'es_superuser': request.user.is_superuser,
            })

        # Verificar que la carrera pertenezca a la universidad del usuario
        if not request.user.is_superuser and carrera.idUniversidad_id != universidad_id:
            messages.error(request, "La carrera seleccionada no pertenece a tu universidad.")
            return render(request, 'materias/materia_form.html', {
                'materia': materia,
                'carreras': carreras,
                'user_rol': user_rol,
                'titulo': 'Editar Materia',
                'es_superuser': request.user.is_superuser,
            })

        # Actualizar materia
        try:
            materia.nombre = nombre
            materia.codigo = codigo if codigo else None
            materia.creditos = int(creditos) if creditos else 3
            materia.semestre_curricular = int(semestre_curricular) if semestre_curricular else None
            materia.idCarrera = carrera
            materia.save()
            messages.success(request, f"✅ Materia '{materia.nombre}' actualizada exitosamente.")
            return redirect('materia_list')
        except Exception as e:
            messages.error(request, f"Error al actualizar la materia: {str(e)}")

    context = {
        'materia': materia,
        'carreras': carreras,
        'user_rol': user_rol,
        'titulo': 'Editar Materia',
        'es_superuser': request.user.is_superuser,
    }
    return render(request, 'materias/materia_form.html', context)


@login_required
def materia_delete(request, id):
    """Eliminar materia (solo admin)"""
    materia = get_object_or_404(
        CatalogoMateria.objects.select_related('idCarrera__idUniversidad'),
        id=id
    )
    user_rol = request.user.rol

    # Verificar permisos
    if user_rol != 'admin':
        messages.error(request, "No tienes permiso para eliminar materias.")
        return redirect('dashboard')

    # ✅ CAMBIO: materia.idUniversidad_id NO existe → usar idCarrera.idUniversidad_id
    if not request.user.is_superuser:
        if materia.idCarrera.idUniversidad_id != request.user.idUniversidad_id:
            messages.error(request, "Esta materia no pertenece a tu universidad.")
            return redirect('dashboard')

    if request.method == 'POST':
        nombre = materia.nombre
        materia.delete()
        messages.success(request, f"✅ Materia '{nombre}' eliminada exitosamente.")
        return redirect('materia_list')

    context = {
        'materia': materia,
        'user_rol': user_rol,
    }
    return render(request, 'materias/materia_confirm_delete.html', context)