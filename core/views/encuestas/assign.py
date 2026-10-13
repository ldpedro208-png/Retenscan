# core/views/encuestas/assign.py

"""
Vista para asignar encuestas a estudiantes
"""
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db import transaction
from django.shortcuts import render, redirect, get_object_or_404  
from ...models import EncuestaAsignacion, Estudiante
from ...services.alert_service import AlertaService
from ..base import get_universidad_id
from .base import obtener_encuesta_con_permisos, obtener_estudiantes_asignados
from ..base import get_universidad_id, logger 

# core/views/encuestas.py
# core/views/encuestas/asignar.py

@login_required
def encuesta_asignar(request, pk):
    """
    Asignar encuesta a estudiantes
    """
    user_rol = getattr(request.user, 'rol', 'estudiante')
    universidad_id = get_universidad_id(request)

    if user_rol not in ['admin', 'profesor']:
        messages.error(request, "No tienes permiso para asignar encuestas.")
        return redirect('encuesta_list')

    encuesta = obtener_encuesta_con_permisos(pk, request.user, universidad_id)

    if user_rol == 'profesor' and encuesta.creador != request.user:
        messages.error(request, "Solo puedes asignar encuestas que hayas creado.")
        return redirect('encuesta_detail', pk=pk)

    # Obtener estudiantes
    estudiantes, asignados_ids = obtener_estudiantes_asignados(encuesta, universidad_id, request.user)

    if request.method == 'POST':
        estudiantes_ids = request.POST.getlist('estudiantes')

        if not estudiantes_ids:
            messages.warning(request, "Selecciona al menos un estudiante.")
        else:
            asignados = 0

            with transaction.atomic():
                for estudiante_id in estudiantes_ids:
                    estudiante = get_object_or_404(Estudiante, pk=estudiante_id)
                    if estudiante.idCarrera.idUniversidad_id != universidad_id and not request.user.is_superuser:
                        continue

                    _, created = EncuestaAsignacion.objects.get_or_create(
                        encuesta=encuesta,
                        estudiante=estudiante
                    )
                    if created:
                        asignados += 1
                        try:
                            AlertaService.notificar_encuesta_asignada(
                                estudiante=estudiante,
                                encuesta=encuesta,
                                asignacion=f"Nueva encuesta: {encuesta.titulo}"
                            )
                        except Exception as e:
                            logger.error(f"Error notificando encuesta: {str(e)}")

            # ✅ IMPORTANTE: Cambiar estado de 'borrador' a 'activa' al asignar
            if asignados > 0 and encuesta.estado == 'borrador':
                encuesta.estado = 'activa'
                encuesta.save()
                messages.info(request, f"La encuesta ha sido activada automáticamente al asignarla a estudiantes.")

            messages.success(
                request, 
                f"✅ Encuesta '{encuesta.titulo}' asignada a {asignados} estudiantes. "
                f"Estado: {encuesta.get_estado_display()}"
            )
            return redirect('encuesta_detail', pk=pk)

    context = {
        'encuesta': encuesta,
        'estudiantes': estudiantes,
        'asignados_ids': asignados_ids,
        'user_rol': user_rol,
    }
    return render(request, 'encuesta/encuesta_asignar.html', context)