# core/views/reuniones.py

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from datetime import datetime
from ..models import Estudiante, Reunion, UsuarioEstudiantes
from ..services.alert_service import AlertaService
from .base import get_universidad_id, logger


@login_required
def reunion_list(request):
    user_rol = getattr(request.user, 'rol', 'estudiante')
    universidad_id = get_universidad_id(request)

    if user_rol not in ['admin', 'tutor']:
        messages.error(request, "No tienes permiso para ver reuniones.")
        return redirect('dashboard')

    if user_rol == 'tutor':
        reuniones = Reunion.objects.filter(tutor=request.user).order_by('fecha_programada')
    else:
        if request.user.is_superuser:
            reuniones = Reunion.objects.all().order_by('fecha_programada')
        else:
            reuniones = Reunion.objects.filter(
                idUniversidad_id=universidad_id
            ).order_by('fecha_programada')

    programadas = reuniones.filter(estado='programada')
    completadas = reuniones.filter(estado='completada')
    canceladas = reuniones.filter(estado='cancelada')

    context = {
        'reuniones': reuniones,
        'programadas': programadas,
        'completadas': completadas,
        'canceladas': canceladas,
        'user_rol': user_rol,
        'es_tutor': user_rol == 'tutor',
    }
    return render(request, 'reunion/reunion_list.html', context)


@login_required
def reunion_create(request):
    user_rol = getattr(request.user, 'rol', 'estudiante')
    universidad_id = get_universidad_id(request)

    if user_rol not in ['admin', 'tutor']:
        messages.error(request, "No tienes permiso para crear reuniones.")
        return redirect('dashboard')

    if user_rol == 'tutor':
        estudiantes_asignados = UsuarioEstudiantes.objects.filter(
            usuario_id=request.user.id
        ).values_list('estudiante_id', flat=True)
        estudiantes = Estudiante.objects.filter(
            idEstudiante__in=estudiantes_asignados,
            idCarrera__idUniversidad_id=universidad_id
        ).order_by('idUsuario__last_name')
    else:
        if request.user.is_superuser:
            estudiantes = Estudiante.objects.all().order_by('idUsuario__last_name')
        else:
            estudiantes = Estudiante.objects.filter(
                idCarrera__idUniversidad_id=universidad_id
            ).order_by('idUsuario__last_name')

    if request.method == 'POST':
        estudiante_id = request.POST.get('estudiante')
        titulo = request.POST.get('titulo')
        descripcion = request.POST.get('descripcion')
        fecha_programada = request.POST.get('fecha_programada')
        duracion = request.POST.get('duracion', 60)
        ubicacion = request.POST.get('ubicacion')

        if not estudiante_id or not titulo or not fecha_programada:
            messages.error(request, "Los campos obligatorios deben ser completados.")
            return render(request, 'reunion/reunion_form.html', {
                'estudiantes': estudiantes,
                'user_rol': user_rol,
            })

        estudiante = get_object_or_404(Estudiante, pk=estudiante_id)

        try:
            if isinstance(fecha_programada, str):
                if 'T' in fecha_programada:
                    fecha_programada = datetime.strptime(fecha_programada, '%Y-%m-%dT%H:%M')
                else:
                    fecha_programada = datetime.strptime(fecha_programada, '%Y-%m-%d %H:%M')
                fecha_programada = timezone.make_aware(fecha_programada)
            elif isinstance(fecha_programada, datetime):
                if timezone.is_naive(fecha_programada):
                    fecha_programada = timezone.make_aware(fecha_programada)
        except Exception as e:
            logger.error(f"Error al convertir fecha: {str(e)}")
            messages.error(request, "Formato de fecha inválido. Usa el formato YYYY-MM-DD HH:MM")
            return render(request, 'reunion/reunion_form.html', {
                'estudiantes': estudiantes,
                'user_rol': user_rol,
            })

        reunion = Reunion.objects.create(
            tutor=request.user,
            estudiante=estudiante,
            titulo=titulo,
            descripcion=descripcion,
            fecha_programada=fecha_programada,
            duracion=int(duracion),
            ubicacion=ubicacion,
            estado='programada',
            idUniversidad_id=universidad_id,
        )

        AlertaService.notificar_reunion_programada(
            tutor=request.user,
            estudiante=estudiante,
            reunion=reunion
        )

        messages.success(request, f"Reunión '{titulo}' programada exitosamente.")
        return redirect('reunion_list')

    context = {
        'estudiantes': estudiantes,
        'user_rol': user_rol,
        'es_tutor': user_rol == 'tutor',
    }
    return render(request, 'reunion/reunion_form.html', context)


@login_required
def reunion_detail(request, pk):
    reunion = get_object_or_404(Reunion, pk=pk)
    user_rol = getattr(request.user, 'rol', 'estudiante')

    if user_rol not in ['admin', 'tutor']:
        messages.error(request, "No tienes permiso para ver esta reunión.")
        return redirect('dashboard')

    if user_rol == 'tutor' and reunion.tutor != request.user:
        messages.error(request, "No tienes permiso para ver esta reunión.")
        return redirect('reunion_list')

    context = {
        'reunion': reunion,
        'user_rol': user_rol,
    }
    return render(request, 'reunion/reunion_detail.html', context)


@login_required
def reunion_completar(request, pk):
    reunion = get_object_or_404(Reunion, pk=pk)
    user_rol = getattr(request.user, 'rol', 'estudiante')

    if user_rol not in ['admin', 'tutor']:
        messages.error(request, "No tienes permiso para modificar esta reunión.")
        return redirect('dashboard')

    if user_rol == 'tutor' and reunion.tutor != request.user:
        messages.error(request, "No tienes permiso para modificar esta reunión.")
        return redirect('reunion_list')

    if request.method == 'POST':
        notas = request.POST.get('notas')
        reunion.estado = 'completada'
        reunion.notas = notas
        reunion.save()
        messages.success(request, f"Reunión '{reunion.titulo}' marcada como completada.")
        return redirect('reunion_list')

    context = {
        'reunion': reunion,
        'user_rol': user_rol,
    }
    return render(request, 'reunion/reunion_completar.html', context)


@login_required
def reunion_cancelar(request, pk):
    reunion = get_object_or_404(Reunion, pk=pk)
    user_rol = getattr(request.user, 'rol', 'estudiante')

    if user_rol not in ['admin', 'tutor']:
        messages.error(request, "No tienes permiso para modificar esta reunión.")
        return redirect('dashboard')

    if user_rol == 'tutor' and reunion.tutor != request.user:
        messages.error(request, "No tienes permiso para modificar esta reunión.")
        return redirect('reunion_list')

    if request.method == 'POST':
        reunion.estado = 'cancelada'
        reunion.save()
        messages.success(request, f"Reunión '{reunion.titulo}' cancelada.")
        return redirect('reunion_list')

    context = {
        'reunion': reunion,
        'user_rol': user_rol,
    }
    return render(request, 'reunion/reunion_cancelar.html', context)