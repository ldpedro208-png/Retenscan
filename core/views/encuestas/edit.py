# core/views/encuestas/edit.py

"""
Vista para editar encuestas
"""
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db import transaction
from django.core.cache import cache

from ...models import (
    Encuesta, EncuestaPregunta, EncuestaOpcion,
    EncuestaRespuesta, CatalogoPregunta
)
from ..base import get_universidad_id
from .base import obtener_encuesta_con_permisos, limpiar_cache_encuesta


@login_required
def encuesta_edit(request, pk):
    """
    Editar encuesta (permite editar activas con restricciones)
    """
    user_rol = getattr(request.user, 'rol', 'estudiante')
    universidad_id = get_universidad_id(request)

    if not universidad_id:
        messages.error(request, "Error: No se encontró una universidad asociada a tu cuenta.")
        return redirect('encuesta_list')

    if user_rol not in ['admin', 'profesor']:
        messages.error(request, "No tienes permiso para editar encuestas.")
        return redirect('encuesta_list')

    encuesta = obtener_encuesta_con_permisos(pk, request.user, universidad_id)

    # Verificar permisos adicionales para profesores
    if user_rol == 'profesor' and encuesta.creador != request.user:
        messages.error(request, "No tienes permiso para editar esta encuesta.")
        return redirect('encuesta_detail', pk=encuesta.idEncuesta)

    # No permitir editar encuestas cerradas
    if encuesta.estado == 'cerrada':
        messages.warning(request, "No puedes editar una encuesta que ya está cerrada.")
        return redirect('encuesta_detail', pk=encuesta.idEncuesta)

    es_activa = encuesta.estado == 'activa'

    # Verificar si tiene respuestas
    tiene_respuestas = EncuestaRespuesta.objects.filter(
        asignacion__encuesta=encuesta
    ).exists()

    # Obtener preguntas del catálogo
    preguntas_catalogo = CatalogoPregunta.objects.filter(activo=True)

    # Obtener IDs de preguntas del catálogo ya seleccionadas
    preguntas_catalogo_ids = encuesta.preguntas.filter(
        pregunta__in=CatalogoPregunta.objects.values_list('pregunta', flat=True)
    ).values_list('idPreguntaEncuesta', flat=True)

    if request.method == 'POST':
        titulo = request.POST.get('titulo', '').strip()
        descripcion = request.POST.get('descripcion', '').strip()
        fecha_inicio = request.POST.get('fecha_inicio')
        fecha_fin = request.POST.get('fecha_fin')
        es_obligatoria = request.POST.get('es_obligatoria') == 'on'

        if not titulo:
            messages.error(request, "El título es obligatorio.")
            return render(request, 'encuesta/encuesta_form.html', {
                'user_rol': user_rol,
                'encuesta': encuesta,
                'preguntas_catalogo': preguntas_catalogo,
                'errores': True,
                'editando_activa': es_activa,
                'tiene_respuestas': tiene_respuestas,
            })

        if not fecha_inicio or not fecha_fin:
            messages.error(request, "Las fechas de inicio y fin son obligatorias.")
            return render(request, 'encuesta/encuesta_form.html', {
                'user_rol': user_rol,
                'encuesta': encuesta,
                'preguntas_catalogo': preguntas_catalogo,
                'errores': True,
                'editando_activa': es_activa,
                'tiene_respuestas': tiene_respuestas,
            })

        # Si la encuesta está activa, solo permitir editar ciertos campos
        if es_activa:
            # Mantener valores originales
            titulo_original = encuesta.titulo
            es_obligatoria_original = encuesta.es_obligatoria
            anonima_original = getattr(encuesta, 'anonima', False)
            tiempo_estimado_original = getattr(encuesta, 'tiempo_estimado', 5)

            # Verificar si se intenta cambiar el título
            if titulo != titulo_original:
                messages.warning(request, "No puedes cambiar el título de una encuesta activa.")
                titulo = titulo_original

            # Verificar si se intenta cambiar obligatoriedad
            if es_obligatoria != es_obligatoria_original:
                messages.warning(request, "No puedes cambiar la obligatoriedad de una encuesta activa.")
                es_obligatoria = es_obligatoria_original

            # Verificar si se intenta cambiar anonimato
            anonima = request.POST.get('anonima') == 'on'
            if anonima != anonima_original:
                messages.warning(request, "No puedes cambiar el anonimato de una encuesta activa.")
                anonima = anonima_original

            # Verificar si se intenta cambiar tiempo estimado
            try:
                tiempo_estimado = int(request.POST.get('tiempo_estimado', 5))
                if tiempo_estimado != tiempo_estimado_original:
                    messages.warning(request, "No puedes cambiar el tiempo estimado de una encuesta activa.")
                    tiempo_estimado = tiempo_estimado_original
            except ValueError:
                tiempo_estimado = tiempo_estimado_original

            # Verificar si hay respuestas antes de permitir cambiar fechas
            if tiene_respuestas:
                fecha_inicio = encuesta.fecha_inicio
                fecha_fin = encuesta.fecha_fin
                messages.info(request, "No puedes cambiar las fechas porque ya hay respuestas registradas.")

            # Actualizar solo campos permitidos
            encuesta.titulo = titulo
            encuesta.descripcion = descripcion
            encuesta.fecha_inicio = fecha_inicio
            encuesta.fecha_fin = fecha_fin
            encuesta.es_obligatoria = es_obligatoria
            encuesta.anonima = anonima
            encuesta.tiempo_estimado = tiempo_estimado
            encuesta.save()

            # Procesar preguntas - SOLO AGREGAR NUEVAS
            preguntas_existentes = list(encuesta.preguntas.all())

            # Procesar preguntas del catálogo seleccionadas
            preguntas_catalogo_ids_post = request.POST.getlist('preguntas_catalogo_ids[]')

            for pregunta_id in preguntas_catalogo_ids_post:
                if pregunta_id:
                    try:
                        pregunta_catalogo = CatalogoPregunta.objects.get(idPregunta=pregunta_id)
                        existe = encuesta.preguntas.filter(
                            pregunta=pregunta_catalogo.pregunta
                        ).exists()

                        if not existe:
                            EncuestaPregunta.objects.create(
                                encuesta=encuesta,
                                pregunta=pregunta_catalogo.pregunta,
                                tipo=pregunta_catalogo.tipo_respuesta.lower(),
                                es_obligatoria=True,
                                orden=encuesta.preguntas.count()
                            )
                    except CatalogoPregunta.DoesNotExist:
                        pass

            # Procesar preguntas personalizadas (solo agregar nuevas)
            preguntas_texto = request.POST.getlist('pregunta_texto[]')
            preguntas_tipo = request.POST.getlist('pregunta_tipo[]')
            preguntas_obligatorias = request.POST.getlist('pregunta_obligatoria[]')

            for i, texto in enumerate(preguntas_texto):
                if texto.strip():
                    es_nueva = True
                    for p_existente in preguntas_existentes:
                        if p_existente.pregunta == texto.strip() and p_existente.tipo == preguntas_tipo[i]:
                            es_nueva = False
                            break

                    if es_nueva:
                        es_obligatoria_pregunta = str(i) in preguntas_obligatorias
                        tipo_pregunta = preguntas_tipo[i] if i < len(preguntas_tipo) else 'texto'

                        pregunta = EncuestaPregunta.objects.create(
                            encuesta=encuesta,
                            pregunta=texto.strip(),
                            tipo=tipo_pregunta,
                            es_obligatoria=es_obligatoria_pregunta,
                            orden=encuesta.preguntas.count()
                        )

                        if pregunta.tipo in ['opcion_unica', 'opcion_multiple']:
                            opciones = request.POST.getlist(f'opciones_{i}[]')
                            for j, opcion_texto in enumerate(opciones):
                                if opcion_texto.strip():
                                    EncuestaOpcion.objects.create(
                                        pregunta=pregunta,
                                        texto=opcion_texto.strip(),
                                        orden=j
                                    )

            messages.success(request, f"✅ Encuesta '{encuesta.titulo}' actualizada exitosamente. Se agregaron nuevas preguntas.")

        else:
            # Encuesta en BORRADOR - Edición completa
            with transaction.atomic():
                encuesta.titulo = titulo
                encuesta.descripcion = descripcion
                encuesta.fecha_inicio = fecha_inicio
                encuesta.fecha_fin = fecha_fin
                encuesta.es_obligatoria = es_obligatoria
                encuesta.anonima = request.POST.get('anonima') == 'on'
                try:
                    encuesta.tiempo_estimado = int(request.POST.get('tiempo_estimado', 5))
                except ValueError:
                    encuesta.tiempo_estimado = 5
                encuesta.save()

                # Eliminar preguntas existentes (se recrean)
                encuesta.preguntas.all().delete()

                # Procesar preguntas del catálogo seleccionadas
                preguntas_catalogo_ids_post = request.POST.getlist('preguntas_catalogo_ids[]')
                for pregunta_id in preguntas_catalogo_ids_post:
                    if pregunta_id:
                        try:
                            pregunta_catalogo = CatalogoPregunta.objects.get(idPregunta=pregunta_id)
                            EncuestaPregunta.objects.create(
                                encuesta=encuesta,
                                pregunta=pregunta_catalogo.pregunta,
                                tipo=pregunta_catalogo.tipo_respuesta.lower(),
                                es_obligatoria=True,
                                orden=len(preguntas_catalogo_ids_post)
                            )
                        except CatalogoPregunta.DoesNotExist:
                            pass

                # Procesar preguntas personalizadas
                preguntas_texto = request.POST.getlist('pregunta_texto[]')
                preguntas_tipo = request.POST.getlist('pregunta_tipo[]')
                preguntas_obligatorias = request.POST.getlist('pregunta_obligatoria[]')

                for i, texto in enumerate(preguntas_texto):
                    if texto.strip():
                        es_obligatoria_pregunta = str(i) in preguntas_obligatorias
                        tipo_pregunta = preguntas_tipo[i] if i < len(preguntas_tipo) else 'texto'

                        pregunta = EncuestaPregunta.objects.create(
                            encuesta=encuesta,
                            pregunta=texto.strip(),
                            tipo=tipo_pregunta,
                            es_obligatoria=es_obligatoria_pregunta,
                            orden=len(preguntas_catalogo_ids_post) + i
                        )

                        if pregunta.tipo in ['opcion_unica', 'opcion_multiple']:
                            opciones = request.POST.getlist(f'opciones_{i}[]')
                            for j, opcion_texto in enumerate(opciones):
                                if opcion_texto.strip():
                                    EncuestaOpcion.objects.create(
                                        pregunta=pregunta,
                                        texto=opcion_texto.strip(),
                                        orden=j
                                    )

            messages.success(request, f"✅ Encuesta '{encuesta.titulo}' actualizada exitosamente.")

        # Limpiar caché
        limpiar_cache_encuesta(encuesta.idEncuesta)
        return redirect('encuesta_detail', pk=encuesta.idEncuesta)

    # GET: Preparar formulario con datos existentes
    context = {
        'user_rol': user_rol,
        'encuesta': encuesta,
        'preguntas_catalogo': preguntas_catalogo,
        'preguntas_catalogo_seleccionadas': list(preguntas_catalogo_ids),
        'tipos_pregunta': EncuestaPregunta.TIPO_CHOICES,
        'titulo_form': encuesta.titulo,
        'descripcion_form': encuesta.descripcion,
        'fecha_inicio_form': encuesta.fecha_inicio.strftime('%Y-%m-%dT%H:%M') if encuesta.fecha_inicio else '',
        'fecha_fin_form': encuesta.fecha_fin.strftime('%Y-%m-%dT%H:%M') if encuesta.fecha_fin else '',
        'es_obligatoria_form': encuesta.es_obligatoria,
        'anonima_form': encuesta.anonima,
        'tiempo_estimado_form': encuesta.tiempo_estimado,
        'es_profesor': user_rol == 'profesor',
        'es_admin': user_rol == 'admin',
        'editando': True,
        'editando_activa': es_activa,
        'tiene_respuestas': tiene_respuestas,
    }
    return render(request, 'encuesta/encuesta_form.html', context)