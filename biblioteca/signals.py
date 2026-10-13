# biblioteca/signals.py
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone
from datetime import timedelta
from .models import AccesoRecurso


@receiver(post_save, sender=AccesoRecurso)
def detectar_desmotivacion_por_caida(sender, instance, created, **kwargs):
    """
    Si un estudiante antes activo deja de acceder, se genera alerta.
    Se ejecuta en cada acceso para mantener el chequeo liviano.
    """
    if not created:
        return

    estudiante = instance.idEstudiante
    ahora = timezone.now()

    # Solo revisar si tiene historial previo
    accesos_previos = AccesoRecurso.objects.filter(
        idEstudiante=estudiante,
        created_at__gte=ahora - timedelta(days=60),
        created_at__lt=ahora - timedelta(days=15)
    ).count()

    if accesos_previos < 5:
        return

    accesos_recientes = AccesoRecurso.objects.filter(
        idEstudiante=estudiante,
        created_at__gte=ahora - timedelta(days=15)
    ).count()

    # Antes activo, ahora sin accesos
    if accesos_recientes <= 1:
        try:
            from core.models import Alerta, CatalogoFactorRiesgo, UsuarioEstudiantes
            from core.services.alert_service import AlertaService

            factor = CatalogoFactorRiesgo.objects.filter(
                nombre__icontains='Desmotivaci', activo=True
            ).first()

            alerta, creada = Alerta.objects.get_or_create(
                idEstudiante=estudiante,
                idFactor=factor,
                estado='Activa',
                defaults={
                    'nivel': 'Medio',
                    'descripcion': 'Sin actividad en biblioteca digital en los últimos 15 días.'
                }
            )

            if creada:
                # Notificar a los tutores
                tutores = UsuarioEstudiantes.objects.filter(
                    estudiante=estudiante
                ).select_related('usuario')
                for t in tutores:
                    AlertaService._crear_notificacion_interna(
                        usuario=t.usuario,
                        titulo=f"Posible desmotivación: {estudiante.nombre_completo}",
                        mensaje="El estudiante dejó de usar la biblioteca digital. Revísalo.",
                        tipo='alerta',
                        url=f"/estudiantes/{estudiante.idEstudiante}/",
                    )
        except Exception:
            pass  # No romper el guardado por errores en el signal