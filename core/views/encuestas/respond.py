# core/views/encuestas/respond.py

"""
Vista para responder encuestas
"""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db import transaction
from django.core.cache import cache
from django.utils import timezone

from ...models import (
    Estudiante,
    EncuestaAsignacion,
    EncuestaRespuesta,
    EncuestaOpcion
)
from ..base import get_universidad_id
from .base import obtener_encuesta_con_permisos, limpiar_cache_encuesta


@login_required
def encuesta_responder(request, pk):
    """
    Responder encuesta (sin caché, porque es transaccional)
    """
    user_rol = getattr(request.user, 'rol', 'estudiante')
    universidad_id = get_universidad_id(request)

    # ============================================
    # 1. VERIFICAR PERMISOS
    # ============================================
    if user_rol != 'estudiante':
        messages.error(request, "No tienes permiso para responder encuestas.")
        return redirect('encuesta_list')

    # ============================================
    # 2. OBTENER ENCUESTA
    # ============================================
    encuesta = obtener_encuesta_con_permisos(pk, request.user, universidad_id)

    # ============================================
    # 3. VERIFICAR ASIGNACIÓN Y DISPONIBILIDAD
    # ============================================
    try:
        estudiante = Estudiante.objects.get(idUsuario=request.user.id)
        asignacion = EncuestaAsignacion.objects.select_related('encuesta').get(
            encuesta=encuesta,
            estudiante=estudiante
        )

        # Verificar si ya respondió
        if asignacion.completada:
            messages.warning(request, "Ya has respondido esta encuesta.")
            return redirect('encuesta_detail', pk=pk)

        # Verificar si la encuesta está activa
        if not encuesta.esta_activa():
            messages.warning(request, "Esta encuesta no está disponible.")
            return redirect('encuesta_detail', pk=pk)

        # ✅ Verificar que la encuesta esté dentro del período de fechas
        ahora = timezone.now()
        if not (encuesta.fecha_inicio <= ahora <= encuesta.fecha_fin):
            if encuesta.fecha_fin < ahora:
                messages.error(request, "Esta encuesta ha vencido.")
            else:
                messages.error(request, "Esta encuesta aún no está disponible.")
            return redirect('encuesta_detail', pk=pk)

    except Estudiante.DoesNotExist:
        messages.error(request, "No tienes un perfil de estudiante asociado.")
        return redirect('encuesta_list')
    except EncuestaAsignacion.DoesNotExist:
        messages.error(request, "No tienes acceso a esta encuesta.")
        return redirect('encuesta_list')

    # ============================================
    # 4. PROCESAR RESPUESTAS (POST)
    # ============================================
    if request.method == 'POST':
        with transaction.atomic():
            preguntas = encuesta.preguntas.all().prefetch_related('opciones')

            for pregunta in preguntas:
                respuesta_key = f'pregunta_{pregunta.idPreguntaEncuesta}'

                if pregunta.tipo == 'opcion_unica':
                    opcion_id = request.POST.get(respuesta_key)
                    if opcion_id:
                        opcion = get_object_or_404(EncuestaOpcion, pk=opcion_id)
                        EncuestaRespuesta.objects.create(
                            asignacion=asignacion,
                            pregunta=pregunta,
                            opcion=opcion
                        )

                elif pregunta.tipo == 'opcion_multiple':
                    opciones_ids = request.POST.getlist(respuesta_key)
                    for opcion_id in opciones_ids:
                        opcion = get_object_or_404(EncuestaOpcion, pk=opcion_id)
                        EncuestaRespuesta.objects.create(
                            asignacion=asignacion,
                            pregunta=pregunta,
                            opcion=opcion
                        )

                elif pregunta.tipo == 'escala':
                    valor = request.POST.get(respuesta_key)
                    if valor:
                        EncuestaRespuesta.objects.create(
                            asignacion=asignacion,
                            pregunta=pregunta,
                            respuesta_escala=int(valor)
                        )

                elif pregunta.tipo == 'texto':
                    texto = request.POST.get(respuesta_key)
                    if texto:
                        EncuestaRespuesta.objects.create(
                            asignacion=asignacion,
                            pregunta=pregunta,
                            respuesta_texto=texto
                        )

                elif pregunta.tipo == 'si_no':
                    valor = request.POST.get(respuesta_key)
                    if valor is not None:
                        EncuestaRespuesta.objects.create(
                            asignacion=asignacion,
                            pregunta=pregunta,
                            respuesta_booleana=valor == 'True'
                        )

            # Marcar como completada
            asignacion.completada = True
            asignacion.fecha_respuesta = timezone.now()
            asignacion.save()

        # Limpiar caché de resultados después de responder
        limpiar_cache_encuesta(encuesta.idEncuesta)

        messages.success(request, "✅ ¡Encuesta respondida exitosamente!")
        return redirect('dashboard')

    # ============================================
    # 5. MOSTRAR FORMULARIO (GET)
    # ============================================
    preguntas = encuesta.preguntas.all().prefetch_related('opciones').order_by('orden')

    context = {
        'encuesta': encuesta,
        'preguntas': preguntas,
        'asignacion': asignacion,
        'user_rol': user_rol,
        'now': timezone.now(),
    }

    return render(request, 'encuesta/encuesta_responder.html', context)