# core/views/encuestas/delete.py

"""
Vista para eliminar encuestas
"""
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages

from ..base import get_universidad_id
from .base import obtener_encuesta_con_permisos, limpiar_cache_encuesta


@login_required
def encuesta_delete(request, pk):
    """
    Eliminar encuesta
    """
    user_rol = getattr(request.user, 'rol', 'estudiante')
    universidad_id = get_universidad_id(request)

    if user_rol not in ['admin', 'profesor']:
        messages.error(request, "No tienes permiso para eliminar encuestas.")
        return redirect('encuesta_list')

    encuesta = obtener_encuesta_con_permisos(pk, request.user, universidad_id)

    if user_rol == 'profesor' and encuesta.creador != request.user:
        messages.error(request, "Solo puedes eliminar encuestas que hayas creado.")
        return redirect('encuesta_detail', pk=pk)

    if request.method == 'POST':
        titulo = encuesta.titulo
        encuesta.delete()
        
        # Limpiar caché
        limpiar_cache_encuesta(pk)
        
        messages.success(request, f"Encuesta '{titulo}' eliminada exitosamente.")
        return redirect('encuesta_list')

    context = {
        'encuesta': encuesta,
        'user_rol': user_rol,
    }
    return render(request, 'encuesta/encuesta_confirm_delete.html', context)