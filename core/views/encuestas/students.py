# core/views/encuestas/students.py

"""
Vista para ver estudiantes y sus respuestas
"""
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages

from ...models import EncuestaAsignacion, UsuarioEstudiantes
from ..base import get_universidad_id
from .base import obtener_encuesta_con_permisos


@login_required
def encuesta_estudiantes_respuestas(request, pk):
    """
    Ver estudiantes y sus respuestas
    """
    user_rol = getattr(request.user, 'rol', 'estudiante')
    universidad_id = get_universidad_id(request)

    if user_rol not in ['admin', 'tutor']:
        messages.error(request, "No tienes permiso para ver esta información.")
        return redirect('encuesta_list')

    encuesta = obtener_encuesta_con_permisos(pk, request.user, universidad_id)

    if user_rol == 'tutor':
        estudiantes_asignados = UsuarioEstudiantes.objects.filter(
            usuario_id=request.user.id
        ).values_list('estudiante_id', flat=True)

        asignaciones = EncuestaAsignacion.objects.filter(
            encuesta=encuesta,
            estudiante_id__in=estudiantes_asignados
        ).select_related('estudiante')

        if not asignaciones.exists():
            messages.error(request, "No tienes acceso a esta encuesta.")
            return redirect('encuesta_list')
    else:
        asignaciones = EncuestaAsignacion.objects.filter(
            encuesta=encuesta
        ).select_related('estudiante')

    estudiantes_respuestas = []
    for asignacion in asignaciones:
        estudiantes_respuestas.append({
            'estudiante': asignacion.estudiante,
            'completada': asignacion.completada,
            'fecha_respuesta': asignacion.fecha_respuesta,
            'fecha_asignacion': asignacion.fecha_asignacion,
        })

    context = {
        'encuesta': encuesta,
        'estudiantes_respuestas': estudiantes_respuestas,
        'total': len(estudiantes_respuestas),
        'completadas': sum(1 for e in estudiantes_respuestas if e['completada']),
        'pendientes': sum(1 for e in estudiantes_respuestas if not e['completada']),
        'user_rol': user_rol,
        'es_tutor': user_rol == 'tutor',
    }
    return render(request, 'encuesta/encuesta_estudiantes_respuestas.html', context)