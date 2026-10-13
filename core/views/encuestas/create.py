# core/views/encuestas/create.py

"""
Vista para crear encuestas
"""
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db import transaction
from django.utils import timezone

from ...models import (
    Encuesta, EncuestaPregunta, EncuestaOpcion,
    CatalogoPregunta
)
from ..base import get_universidad_id
from .base import limpiar_cache_encuesta


@login_required
def encuesta_create(request):
    """
    Crear una nueva encuesta
    """
    user_rol = getattr(request.user, 'rol', 'estudiante')
    universidad_id = get_universidad_id(request)

    if not universidad_id:
        messages.error(request, "Error: No se encontró una universidad asociada a tu cuenta.")
        return redirect('encuesta_list')

    if user_rol not in ['admin', 'profesor']:
        messages.error(request, "No tienes permiso para crear encuestas.")
        return redirect('encuesta_list')

    # Obtener preguntas del catálogo
    preguntas_catalogo = CatalogoPregunta.objects.filter(activo=True)

    if request.method == 'POST':
        titulo = request.POST.get('titulo', '').strip()
        descripcion = request.POST.get('descripcion', '').strip()
        fecha_inicio = request.POST.get('fecha_inicio')
        fecha_fin = request.POST.get('fecha_fin')
        es_obligatoria = request.POST.get('es_obligatoria') == 'on'
        anonima = request.POST.get('anonima') == 'on'

        try:
            tiempo_estimado = int(request.POST.get('tiempo_estimado', 5))
        except ValueError:
            tiempo_estimado = 5

        # Validaciones
        errores = []
        if not titulo:
            errores.append("El título es obligatorio.")
        if not fecha_inicio or not fecha_fin:
            errores.append("Las fechas de inicio y fin son obligatorias.")
        
        if errores:
            for error in errores:
                messages.error(request, f"❌ {error}")
            return render(request, 'encuesta/encuesta_form.html', {
                'user_rol': user_rol,
                'preguntas_catalogo': preguntas_catalogo,
                'errores': True,
                'titulo_form': titulo,
                'descripcion_form': descripcion,
                'fecha_inicio_form': fecha_inicio,
                'fecha_fin_form': fecha_fin,
                'es_profesor': user_rol == 'profesor',
                'es_admin': user_rol == 'admin',
            })

        # Crear la encuesta
        with transaction.atomic():
            encuesta = Encuesta.objects.create(
                titulo=titulo,
                descripcion=descripcion,
                creador=request.user,
                fecha_inicio=fecha_inicio,
                fecha_fin=fecha_fin,
                es_obligatoria=es_obligatoria,
                anonima=anonima,
                tiempo_estimado=tiempo_estimado,
                estado='borrador',
                idUniversidad_id=universidad_id,
            )

            # Procesar preguntas del catálogo seleccionadas
            preguntas_catalogo_ids = request.POST.getlist('preguntas_catalogo_ids[]')
            for pregunta_id in preguntas_catalogo_ids:
                if pregunta_id:
                    try:
                        pregunta_catalogo = CatalogoPregunta.objects.get(idPregunta=pregunta_id)
                        EncuestaPregunta.objects.create(
                            encuesta=encuesta,
                            pregunta=pregunta_catalogo.pregunta,
                            tipo=pregunta_catalogo.tipo_respuesta.lower(),
                            es_obligatoria=True,
                            orden=len(preguntas_catalogo_ids)
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
                        orden=len(preguntas_catalogo_ids) + i
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

        messages.success(request, f"✅ Encuesta '{encuesta.titulo}' creada exitosamente.")

        if user_rol == 'profesor':
            return redirect('encuesta_asignar', pk=encuesta.idEncuesta)
        else:
            return redirect('encuesta_detail', pk=encuesta.idEncuesta)

    context = {
        'user_rol': user_rol,
        'preguntas_catalogo': preguntas_catalogo,
        'tipos_pregunta': EncuestaPregunta.TIPO_CHOICES,
        'es_profesor': user_rol == 'profesor',
        'es_admin': user_rol == 'admin',
    }
    return render(request, 'encuesta/encuesta_form.html', context)