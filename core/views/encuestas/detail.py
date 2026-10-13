# core/views/encuestas/detail.py

"""
Vista para detalle de encuesta
"""
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.cache import cache
from django.db.models import Prefetch
from django.utils import timezone

from ...models import Estudiante, EncuestaAsignacion, EncuestaOpcion
from ..base import get_universidad_id
from .base import obtener_encuesta_con_permisos


@login_required
def encuesta_detail(request, pk):
    """
    Detalle de encuesta con optimización
    """
    user_rol = getattr(request.user, 'rol', 'estudiante')
    universidad_id = get_universidad_id(request)

    # Clave de caché para detalle de encuesta
    cache_key = f'encuesta_detail_{pk}_{request.user.id}_{timezone.now().date()}'

    # Intentar obtener del caché
    cached_context = cache.get(cache_key)
    if cached_context:
        return render(request, 'encuesta/encuesta_detail.html', cached_context)

    # Obtener encuesta con permisos
    encuesta = obtener_encuesta_con_permisos(pk, request.user, universidad_id)

    puede_responder = False
    asignacion = None

    if user_rol == 'estudiante':
        try:
            estudiante = Estudiante.objects.get(idUsuario=request.user.id)
            try:
                asignacion = EncuestaAsignacion.objects.select_related('encuesta').get(
                    encuesta=encuesta,
                    estudiante=estudiante
                )
                puede_responder = not asignacion.completada and encuesta.esta_activa()
            except EncuestaAsignacion.DoesNotExist:
                messages.error(request, "No tienes acceso a esta encuesta.")
                return redirect('encuesta_list')
        except Estudiante.DoesNotExist:
            messages.warning(request, "No tienes un perfil de estudiante asociado.")
            return redirect('dashboard')

    # Obtener preguntas con prefetch_related
    preguntas = encuesta.preguntas.all().prefetch_related(
        Prefetch('opciones', queryset=EncuestaOpcion.objects.order_by('orden'))
    ).order_by('orden')

    es_admin = user_rol == 'admin'
    es_profesor_creador = user_rol == 'profesor' and encuesta.creador == request.user

    context = {
        'encuesta': encuesta,
        'preguntas': preguntas,
        'puede_responder': puede_responder,
        'asignacion': asignacion,
        'user_rol': user_rol,
        'es_admin': es_admin,
        'es_profesor_creador': es_profesor_creador,
        'puede_asignar': es_admin or es_profesor_creador,
        'puede_ver_resultados': es_admin or es_profesor_creador or user_rol == 'tutor',
    }

    # Guardar en caché por 5 minutos
    cache.set(cache_key, context, 300)

    return render(request, 'encuesta/encuesta_detail.html', context)