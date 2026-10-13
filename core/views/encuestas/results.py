# core/views/encuestas/results.py

"""
Vista para resultados de encuestas
"""
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.cache import cache
from django.utils import timezone

from ..base import get_universidad_id
from .base import (
    obtener_encuesta_con_permisos,
    obtener_estadisticas_respuestas,
    verificar_permisos_tutor,
    limpiar_cache_encuesta
)


@login_required
def encuesta_resultados(request, pk):
    """
    Resultados de encuesta optimizado
    """
    user_rol = getattr(request.user, 'rol', 'estudiante')
    universidad_id = get_universidad_id(request)

    if user_rol not in ['admin', 'tutor', 'profesor']:
        messages.error(request, "No tienes permiso para ver resultados.")
        return redirect('encuesta_list')

    # Clave de caché para resultados
    cache_key = f'encuesta_resultados_{pk}_{timezone.now().date()}'

    # Intentar obtener del caché
    cached_context = cache.get(cache_key)
    if cached_context:
        return render(request, 'encuesta/encuesta_resultados.html', cached_context)

    # Obtener encuesta
    encuesta = obtener_encuesta_con_permisos(pk, request.user, universidad_id)

    # Verificar permisos para profesor
    if user_rol == 'profesor' and encuesta.creador != request.user:
        messages.error(request, "Solo puedes ver resultados de tus encuestas.")
        return redirect('encuesta_list')

    # Verificar permisos para tutor
    if user_rol == 'tutor':
        if not verificar_permisos_tutor(request.user, encuesta, universidad_id):
            messages.error(request, "No tienes acceso a los resultados de esta encuesta.")
            return redirect('encuesta_list')

    # Obtener estadísticas
    estadisticas, respuestas = obtener_estadisticas_respuestas(encuesta)

    context = {
        'encuesta': encuesta,
        'estadisticas': estadisticas,
        'total_respuestas': respuestas.values('asignacion').distinct().count(),
        'user_rol': user_rol,
    }

    # Guardar en caché por 10 minutos
    cache.set(cache_key, context, 600)

    return render(request, 'encuesta/encuesta_resultados.html', context)