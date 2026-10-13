# core/views/encuestas/debug.py

from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from ...models import Encuesta, EncuestaAsignacion, Estudiante

@login_required
def debug_encuestas(request):
    """Vista de depuración para verificar estado de encuestas"""
    try:
        estudiante = Estudiante.objects.get(idUsuario=request.user.id)
        ahora = timezone.now()
        
        encuestas_asignadas = EncuestaAsignacion.objects.filter(
            estudiante=estudiante
        ).select_related('encuesta')
        
        data = {
            'usuario': request.user.username,
            'estudiante_id': estudiante.idEstudiante,
            'ahora': ahora.isoformat(),
            'total_asignaciones': encuestas_asignadas.count(),
            'encuestas': []
        }
        
        for asignacion in encuestas_asignadas:
            encuesta = asignacion.encuesta
            data['encuestas'].append({
                'id': encuesta.idEncuesta,
                'titulo': encuesta.titulo,
                'estado': encuesta.estado,
                'fecha_inicio': encuesta.fecha_inicio.isoformat(),
                'fecha_fin': encuesta.fecha_fin.isoformat(),
                'completada': asignacion.completada,
                'dentro_periodo': encuesta.fecha_inicio <= ahora <= encuesta.fecha_fin,
                'puede_responder': (
                    encuesta.estado == 'activa' and
                    encuesta.fecha_inicio <= ahora <= encuesta.fecha_fin and
                    not asignacion.completada
                ),
                'fechas': {
                    'inicio': encuesta.fecha_inicio.strftime('%Y-%m-%d %H:%M'),
                    'fin': encuesta.fecha_fin.strftime('%Y-%m-%d %H:%M'),
                    'ahora': ahora.strftime('%Y-%m-%d %H:%M')
                }
            })
        
        return JsonResponse(data, safe=False)
        
    except Estudiante.DoesNotExist:
        return JsonResponse({'error': 'Estudiante no encontrado'}, status=404)