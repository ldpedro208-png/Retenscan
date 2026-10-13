# core/views/tareas.py

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Prefetch
from django.utils import timezone
from ..models import (
    Estudiante, Tarea, TareaAsignacion, TareaPregunta,
    TareaOpcion, TareaRespuesta, UsuarioEstudiantes
)
from ..services.alert_service import AlertaService
from .base import get_universidad_id, logger


@login_required
def tarea_list(request):
    user_rol = getattr(request.user, 'rol', 'estudiante')
    universidad_id = get_universidad_id(request)

    if user_rol == 'admin':
        if request.user.is_superuser:
            tareas_activas = Tarea.objects.exclude(estado='archivada').order_by('-created_at')
            tareas_archivadas = Tarea.objects.filter(estado='archivada').order_by('-created_at')
        else:
            tareas_activas = Tarea.objects.filter(
                idUniversidad_id=universidad_id
            ).exclude(estado='archivada').order_by('-created_at')
            tareas_archivadas = Tarea.objects.filter(
                idUniversidad_id=universidad_id,
                estado='archivada'
            ).order_by('-created_at')
        titulo = "Todas las Tareas"

    elif user_rol == 'profesor':
        tareas_activas = Tarea.objects.filter(
            creador=request.user,
            idUniversidad_id=universidad_id
        ).exclude(estado='archivada').order_by('-created_at')
        tareas_archivadas = Tarea.objects.filter(
            creador=request.user,
            idUniversidad_id=universidad_id,
            estado='archivada'
        ).order_by('-created_at')
        titulo = "Mis Tareas"

    elif user_rol == 'tutor':
        estudiantes_asignados = UsuarioEstudiantes.objects.filter(
            usuario_id=request.user.id
        ).values_list('estudiante_id', flat=True)

        # ✅ CORREGIDO: usar 'asignaciones' en lugar de 'tareaasignacion'
        tareas_activas = Tarea.objects.filter(
            asignaciones__estudiante_id__in=estudiantes_asignados
        ).exclude(estado='archivada').distinct().order_by('-created_at')
        tareas_archivadas = Tarea.objects.filter(
            asignaciones__estudiante_id__in=estudiantes_asignados,
            estado='archivada'
        ).distinct().order_by('-created_at')
        titulo = "Tareas de Mis Estudiantes"

    else:  # ESTUDIANTE
        try:
            estudiante = Estudiante.objects.get(idUsuario=request.user.id)
            # ✅ CORREGIDO: usar 'asignaciones' en lugar de 'tareaasignacion'
            tareas_activas = Tarea.objects.filter(
                asignaciones__estudiante=estudiante
            ).exclude(estado='archivada').order_by('-created_at')
            tareas_archivadas = Tarea.objects.filter(
                asignaciones__estudiante=estudiante,
                estado='archivada'
            ).order_by('-created_at')
            titulo = "Mis Tareas"
        except Estudiante.DoesNotExist:
            messages.warning(request, "No tienes un perfil de estudiante asociado.")
            return redirect('dashboard')

    # ✅ CORREGIDO: usar 'asignaciones' en lugar de 'tareaasignacion_set'
    for tarea in tareas_archivadas:
        tarea.total_entregas = tarea.asignaciones.filter(entregada=True).count()
        tarea.total_calificadas = tarea.asignaciones.filter(calificada=True).count()

    context = {
        'tareas_activas': tareas_activas,
        'tareas_archivadas': tareas_archivadas,
        'titulo': titulo,
        'user_rol': user_rol,
    }
    return render(request, 'tarea/tarea_list.html', context)


@login_required
def tarea_create(request):
    user_rol = getattr(request.user, 'rol', 'estudiante')
    universidad_id = get_universidad_id(request)

    if user_rol not in ['admin', 'profesor']:
        messages.error(request, "No tienes permiso para crear tareas.")
        return redirect('tarea_list')

    if request.method == 'POST':
        titulo = request.POST.get('titulo', '').strip()
        descripcion = request.POST.get('descripcion', '').strip()
        instrucciones = request.POST.get('instrucciones', '').strip()
        puntaje_maximo = request.POST.get('puntaje_maximo', 100)
        fecha_publicacion = request.POST.get('fecha_publicacion')
        fecha_limite = request.POST.get('fecha_limite')

        if not titulo:
            messages.error(request, "El título es obligatorio.")
            return render(request, 'tarea/tarea_form.html', {'user_rol': user_rol})

        tarea = Tarea.objects.create(
            titulo=titulo,
            descripcion=descripcion,
            instrucciones=instrucciones,
            puntaje_maximo=puntaje_maximo,
            creador=request.user,
            fecha_publicacion=fecha_publicacion,
            fecha_limite=fecha_limite,
            estado='borrador',
            idUniversidad_id=universidad_id,
        )

        preguntas_texto = request.POST.getlist('pregunta_texto[]')
        preguntas_tipo = request.POST.getlist('pregunta_tipo[]')
        preguntas_puntaje = request.POST.getlist('pregunta_puntaje[]')

        for i, texto in enumerate(preguntas_texto):
            if texto.strip():
                pregunta = TareaPregunta.objects.create(
                    tarea=tarea,
                    pregunta=texto.strip(),
                    tipo=preguntas_tipo[i] if i < len(preguntas_tipo) else 'texto',
                    puntaje=preguntas_puntaje[i] if i < len(preguntas_puntaje) else 10,
                    orden=i
                )

                if pregunta.tipo in ['opcion_unica', 'opcion_multiple']:
                    opciones = request.POST.getlist(f'opciones_{i}[]')
                    correctas = request.POST.getlist(f'correctas_{i}[]')
                    for j, opcion_texto in enumerate(opciones):
                        if opcion_texto.strip():
                            TareaOpcion.objects.create(
                                pregunta=pregunta,
                                texto=opcion_texto.strip(),
                                es_correcta=str(j) in correctas,
                                orden=j
                            )

        messages.success(request, f"Tarea '{tarea.titulo}' creada exitosamente.")
        return redirect('tarea_detail', pk=tarea.idTarea)

    return render(request, 'tarea/tarea_form.html', {'user_rol': user_rol})


@login_required
def tarea_detail(request, pk):
    user_rol = getattr(request.user, 'rol', 'estudiante')
    universidad_id = get_universidad_id(request)

    if request.user.is_superuser:
        tarea = get_object_or_404(Tarea, pk=pk)
    else:
        tarea = get_object_or_404(
            Tarea,
            pk=pk,
            idUniversidad_id=universidad_id
        )

    puede_entregar = False
    asignacion = None

    if user_rol == 'estudiante':
        try:
            estudiante = Estudiante.objects.get(idUsuario=request.user.id)
            try:
                asignacion = TareaAsignacion.objects.get(
                    tarea=tarea,
                    estudiante=estudiante
                )
                if tarea.estado == 'archivada':
                    puede_entregar = False
                else:
                    puede_entregar = not asignacion.entregada and tarea.esta_activa()
            except TareaAsignacion.DoesNotExist:
                messages.error(request, "No tienes acceso a esta tarea.")
                return redirect('tarea_list')
        except Estudiante.DoesNotExist:
            messages.warning(request, "No tienes un perfil de estudiante asociado.")
            return redirect('dashboard')

    preguntas = tarea.preguntas.all().prefetch_related('opciones')

    # ✅ CORREGIDO: usar 'asignaciones' en lugar de 'tareaasignacion_set'
    total_entregas = tarea.asignaciones.filter(entregada=True).count()
    total_calificadas = tarea.asignaciones.filter(calificada=True).count()

    tiene_calificacion = False
    if asignacion:
        tiene_calificacion = asignacion.calificada

    context = {
        'tarea': tarea,
        'preguntas': preguntas,
        'puede_entregar': puede_entregar,
        'asignacion': asignacion,
        'user_rol': user_rol,
        'es_profesor': user_rol == 'profesor' and tarea.creador == request.user,
        'es_admin': user_rol == 'admin',
        'total_entregas': total_entregas,
        'total_calificadas': total_calificadas,
        'tiene_calificacion': tiene_calificacion,
        'es_archivada': tarea.estado == 'archivada',
    }
    return render(request, 'tarea/tarea_detail.html', context)


@login_required
def tarea_entregar(request, pk):
    user_rol = getattr(request.user, 'rol', 'estudiante')
    universidad_id = get_universidad_id(request)

    if user_rol != 'estudiante':
        messages.error(request, "No tienes permiso para entregar tareas.")
        return redirect('tarea_list')

    if request.user.is_superuser:
        tarea = get_object_or_404(Tarea, pk=pk)
    else:
        tarea = get_object_or_404(
            Tarea,
            pk=pk,
            idUniversidad_id=universidad_id
        )

    try:
        estudiante = Estudiante.objects.get(idUsuario=request.user.id)
        asignacion = TareaAsignacion.objects.get(
            tarea=tarea,
            estudiante=estudiante
        )

        if asignacion.entregada:
            messages.warning(request, "Ya has entregado esta tarea.")
            return redirect('tarea_detail', pk=pk)

        if not tarea.esta_activa():
            messages.warning(request, "Esta tarea no está disponible.")
            return redirect('tarea_detail', pk=pk)

    except (Estudiante.DoesNotExist, TareaAsignacion.DoesNotExist):
        messages.error(request, "No tienes acceso a esta tarea.")
        return redirect('tarea_list')

    if request.method == 'POST':
        preguntas = tarea.preguntas.all()

        for pregunta in preguntas:
            respuesta_key = f'pregunta_{pregunta.idPreguntaTarea}'

            if pregunta.tipo == 'opcion_unica':
                opcion_id = request.POST.get(respuesta_key)
                if opcion_id:
                    opcion = get_object_or_404(TareaOpcion, pk=opcion_id)
                    TareaRespuesta.objects.create(
                        asignacion=asignacion,
                        pregunta=pregunta,
                        opcion=opcion
                    )
            elif pregunta.tipo == 'opcion_multiple':
                opciones_ids = request.POST.getlist(respuesta_key)
                for opcion_id in opciones_ids:
                    opcion = get_object_or_404(TareaOpcion, pk=opcion_id)
                    TareaRespuesta.objects.create(
                        asignacion=asignacion,
                        pregunta=pregunta,
                        opcion=opcion
                    )
            elif pregunta.tipo == 'texto':
                texto = request.POST.get(respuesta_key)
                if texto:
                    TareaRespuesta.objects.create(
                        asignacion=asignacion,
                        pregunta=pregunta,
                        respuesta_texto=texto
                    )

        asignacion.entregada = True
        asignacion.fecha_entrega = timezone.now()
        asignacion.save()

        messages.success(request, "¡Tarea entregada exitosamente!")
        return redirect('dashboard')

    preguntas = tarea.preguntas.all().prefetch_related('opciones')

    context = {
        'tarea': tarea,
        'preguntas': preguntas,
        'asignacion': asignacion,
    }
    return render(request, 'tarea/tarea_entregar.html', context)


@login_required
def tarea_calificar(request, pk):
    user_rol = getattr(request.user, 'rol', 'estudiante')
    universidad_id = get_universidad_id(request)

    if user_rol not in ['admin', 'profesor']:
        messages.error(request, "No tienes permiso para calificar tareas.")
        return redirect('tarea_list')

    if request.user.is_superuser:
        tarea = get_object_or_404(Tarea, pk=pk)
    else:
        tarea = get_object_or_404(
            Tarea,
            pk=pk,
            idUniversidad_id=universidad_id
        )

    if user_rol == 'profesor' and tarea.creador != request.user:
        messages.error(request, "Solo puedes calificar tus propias tareas.")
        return redirect('tarea_list')

    asignaciones = TareaAsignacion.objects.filter(
        tarea=tarea,
        entregada=True
    ).select_related('estudiante').prefetch_related(
        Prefetch('respuestas', queryset=TareaRespuesta.objects.select_related('pregunta'))
    )

    if request.method == 'POST':
        for asignacion in asignaciones:
            respuestas = TareaRespuesta.objects.filter(asignacion=asignacion)
            total_puntaje = 0

            for respuesta in respuestas:
                calificacion_key = f'calificacion_{respuesta.idRespuestaTarea}'
                retro_key = f'retroalimentacion_{respuesta.idRespuestaTarea}'

                calificacion = request.POST.get(calificacion_key)
                retroalimentacion = request.POST.get(retro_key, '')

                if calificacion:
                    respuesta.calificacion = float(calificacion)
                    respuesta.retroalimentacion_pregunta = retroalimentacion
                    respuesta.save()
                    total_puntaje += float(calificacion)

            retro_general_key = f'retroalimentacion_general_{asignacion.idAsignacion}'
            retro_general = request.POST.get(retro_general_key, '')

            asignacion.puntaje_obtenido = total_puntaje
            asignacion.calificada = True
            asignacion.retroalimentacion = retro_general
            asignacion.save()

        messages.success(request, f"Tarea '{tarea.titulo}' calificada exitosamente.")
        return redirect('tarea_detail', pk=pk)

    context = {
        'tarea': tarea,
        'asignaciones': asignaciones,
        'user_rol': user_rol,
    }
    return render(request, 'tarea/tarea_calificar.html', context)


@login_required
def tarea_asignar(request, pk):
    user_rol = getattr(request.user, 'rol', 'estudiante')
    universidad_id = get_universidad_id(request)

    if user_rol not in ['admin', 'profesor']:
        messages.error(request, "No tienes permiso para asignar tareas.")
        return redirect('tarea_list')

    if request.user.is_superuser:
        tarea = get_object_or_404(Tarea, pk=pk)
    else:
        tarea = get_object_or_404(
            Tarea,
            pk=pk,
            idUniversidad_id=universidad_id
        )

    if user_rol == 'profesor' and tarea.creador != request.user:
        messages.error(request, "Solo puedes asignar tareas que hayas creado.")
        return redirect('tarea_detail', pk=pk)

    if request.method == 'POST':
        estudiantes_ids = request.POST.getlist('estudiantes')

        if not estudiantes_ids:
            messages.warning(request, "Selecciona al menos un estudiante.")
        else:
            asignados = 0

            for estudiante_id in estudiantes_ids:
                estudiante = get_object_or_404(Estudiante, pk=estudiante_id)
                if estudiante.idCarrera.idUniversidad_id != universidad_id and not request.user.is_superuser:
                    continue

                _, created = TareaAsignacion.objects.get_or_create(
                    tarea=tarea,
                    estudiante=estudiante
                )
                if created:
                    asignados += 1
                    try:
                        AlertaService.notificar_tarea_asignada(
                            estudiante=estudiante,
                            tarea=tarea,
                            asignacion=f"Nueva tarea: {tarea.titulo}"
                        )
                    except Exception as e:
                        logger.error(f"Error notificando tarea: {str(e)}")

            if asignados > 0 and tarea.estado == 'borrador':
                tarea.estado = 'publicada'
                tarea.save()

            messages.success(request, f"Tarea asignada a {asignados} estudiantes. Notificaciones enviadas.")
            return redirect('tarea_detail', pk=pk)

    estudiantes = Estudiante.objects.filter(
        estado_academico='Activo',
        idCarrera__idUniversidad_id=universidad_id
    ).order_by('idUsuario__last_name')
    
    asignados_ids = TareaAsignacion.objects.filter(
        tarea=tarea
    ).values_list('estudiante_id', flat=True)

    context = {
        'tarea': tarea,
        'estudiantes': estudiantes,
        'asignados_ids': list(asignados_ids),
        'user_rol': user_rol,
    }
    return render(request, 'tarea/tarea_asignar.html', context)


@login_required
def tarea_resultados(request, pk):
    user_rol = getattr(request.user, 'rol', 'estudiante')
    universidad_id = get_universidad_id(request)

    if request.user.is_superuser:
        tarea = get_object_or_404(Tarea, pk=pk)
    else:
        tarea = get_object_or_404(
            Tarea,
            pk=pk,
            idUniversidad_id=universidad_id
        )

    if user_rol == 'estudiante':
        try:
            estudiante = Estudiante.objects.get(idUsuario=request.user.id)
            asignacion = TareaAsignacion.objects.get(
                tarea=tarea,
                estudiante=estudiante
            )
            if not asignacion.calificada:
                messages.warning(request, "Tu tarea aún no ha sido calificada.")
                return redirect('tarea_detail', pk=pk)
        except (Estudiante.DoesNotExist, TareaAsignacion.DoesNotExist):
            messages.error(request, "No tienes acceso a esta tarea.")
            return redirect('tarea_list')
    elif user_rol == 'profesor' and tarea.creador != request.user:
        messages.error(request, "No tienes acceso a los resultados de esta tarea.")
        return redirect('tarea_list')

    context = {
        'tarea': tarea,
        'user_rol': user_rol,
    }
    return render(request, 'tarea/tarea_resultados.html', context)


@login_required
def tarea_delete(request, pk):
    user_rol = getattr(request.user, 'rol', 'estudiante')
    universidad_id = get_universidad_id(request)

    if user_rol not in ['admin', 'profesor']:
        messages.error(request, "No tienes permiso para eliminar tareas.")
        return redirect('tarea_list')

    if request.user.is_superuser:
        tarea = get_object_or_404(Tarea, pk=pk)
    else:
        tarea = get_object_or_404(
            Tarea,
            pk=pk,
            idUniversidad_id=universidad_id
        )

    if user_rol == 'profesor' and tarea.creador != request.user:
        messages.error(request, "Solo puedes eliminar tareas que hayas creado.")
        return redirect('tarea_detail', pk=pk)

    if request.method == 'POST':
        titulo = tarea.titulo
        tarea.delete()
        messages.success(request, f"Tarea '{titulo}' eliminada permanentemente.")
        return redirect('tarea_list')

    total_entregas = tarea.asignaciones.filter(entregada=True).count()
    total_calificadas = tarea.asignaciones.filter(calificada=True).count()

    context = {
        'tarea': tarea,
        'user_rol': user_rol,
        'total_entregas': total_entregas,
        'total_calificadas': total_calificadas,
        'accion': 'eliminar',
    }
    return render(request, 'tarea/tarea_confirm_delete.html', context)


@login_required
def tarea_restaurar(request, pk):
    user_rol = getattr(request.user, 'rol', 'estudiante')
    universidad_id = get_universidad_id(request)

    if user_rol not in ['admin', 'profesor']:
        messages.error(request, "No tienes permiso para restaurar tareas.")
        return redirect('tarea_list')

    if request.user.is_superuser:
        tarea = get_object_or_404(Tarea, pk=pk)
    else:
        tarea = get_object_or_404(
            Tarea,
            pk=pk,
            idUniversidad_id=universidad_id
        )

    if user_rol == 'profesor' and tarea.creador != request.user:
        messages.error(request, "Solo puedes restaurar tareas que hayas creado.")
        return redirect('tarea_list')

    if tarea.estado != 'archivada':
        messages.warning(request, "Esta tarea no está archivada.")
        return redirect('tarea_detail', pk=pk)

    if request.method == 'POST':
        tarea.estado = 'publicada'
        tarea.save()
        messages.success(request, f"Tarea '{tarea.titulo}' restaurada exitosamente.")
        return redirect('tarea_list')

    context = {
        'tarea': tarea,
        'user_rol': user_rol,
    }
    return render(request, 'tarea/tarea_restaurar.html', context)


@login_required
def tarea_archivar(request, pk):
    user_rol = getattr(request.user, 'rol', 'estudiante')
    universidad_id = get_universidad_id(request)

    if user_rol not in ['admin', 'profesor']:
        messages.error(request, "No tienes permiso para archivar tareas.")
        return redirect('tarea_list')

    if request.user.is_superuser:
        tarea = get_object_or_404(Tarea, pk=pk)
    else:
        tarea = get_object_or_404(
            Tarea,
            pk=pk,
            idUniversidad_id=universidad_id
        )

    if user_rol == 'profesor' and tarea.creador != request.user:
        messages.error(request, "Solo puedes archivar tareas que hayas creado.")
        return redirect('tarea_detail', pk=pk)

    if request.method == 'POST':
        tarea.estado = 'archivada'
        tarea.save()
        messages.success(request, f"Tarea '{tarea.titulo}' archivada exitosamente.")
        return redirect('tarea_list')

    total_entregas = tarea.asignaciones.filter(entregada=True).count()
    total_calificadas = tarea.asignaciones.filter(calificada=True).count()

    context = {
        'tarea': tarea,
        'user_rol': user_rol,
        'total_entregas': total_entregas,
        'total_calificadas': total_calificadas,
        'accion': 'archivar',
    }
    return render(request, 'tarea/tarea_confirm_archivar.html', context)


@login_required
def tarea_edit(request, pk):
    user_rol = getattr(request.user, 'rol', 'estudiante')
    universidad_id = get_universidad_id(request)

    if user_rol not in ['admin', 'profesor']:
        messages.error(request, "No tienes permiso para editar tareas.")
        return redirect('tarea_list')

    if request.user.is_superuser:
        tarea = get_object_or_404(Tarea, pk=pk)
    else:
        tarea = get_object_or_404(
            Tarea,
            pk=pk,
            idUniversidad_id=universidad_id
        )

    if user_rol == 'profesor' and tarea.creador != request.user:
        messages.error(request, "Solo puedes editar tus propias tareas.")
        return redirect('tarea_detail', pk=pk)

    if tarea.estado == 'archivada':
        messages.warning(request, "No puedes editar una tarea archivada.")
        return redirect('tarea_detail', pk=pk)

    if request.method == 'POST':
        # Código de edición
        pass

    preguntas = tarea.preguntas.all().prefetch_related('opciones')

    context = {
        'tarea': tarea,
        'preguntas': preguntas,
        'user_rol': user_rol,
    }
    return render(request, 'tarea/tarea_edit.html', context)