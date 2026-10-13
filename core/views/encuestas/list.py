# core/views/encuestas/list.py

"""
Vista para listar encuestas
"""
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.cache import cache
from django.utils import timezone

from ...models import Estudiante
from ..base import get_universidad_id
from .base import obtener_contexto_encuesta_list


@login_required
def encuesta_list(request):
    """
    Lista de encuestas con caché y optimización
    """
    user_rol = getattr(request.user, 'rol', 'estudiante')
    universidad_id = get_universidad_id(request)

    # ✅ Obtener fecha/hora actual para comparaciones
    ahora = timezone.now()

    # Clave de caché por usuario, rol y universidad
    cache_key = f'encuesta_list_{user_rol}_{request.user.id}_{universidad_id}_{timezone.now().date()}'

    # Intentar obtener del caché
    cached_context = cache.get(cache_key)
    if cached_context:
        # ✅ Agregar 'now' al contexto cacheado
        cached_context['now'] = ahora
        return render(request, 'encuesta/encuesta_list.html', cached_context)

    # Obtener contexto según el rol
    encuestas, titulo = obtener_contexto_encuesta_list(user_rol, request.user, universidad_id)

    # Verificar si el usuario es estudiante sin perfil
    if user_rol == 'estudiante' and not encuestas:
        try:
            Estudiante.objects.get(idUsuario=request.user.id)
        except Estudiante.DoesNotExist:
            messages.warning(request, "No tienes un perfil de estudiante asociado.")
            return redirect('dashboard')

    # Contexto
    context = {
        'encuestas': encuestas,
        'titulo': titulo,
        'user_rol': user_rol,
        'es_tutor': user_rol == 'tutor',
        'es_admin': user_rol == 'admin',
        'es_profesor': user_rol == 'profesor',
        'es_estudiante': user_rol == 'estudiante',
        'now': ahora,  # ✅ IMPORTANTE: Pasar la fecha/hora actual
    }

    # Guardar en caché por 5 minutos
    cache.set(cache_key, context, 300)

    return render(request, 'encuesta/encuesta_list.html', context)