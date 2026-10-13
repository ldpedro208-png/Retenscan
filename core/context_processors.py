# core/context_processors.py

from .models import Usuario
from django.conf import settings
from django.core.cache import cache
import logging

logger = logging.getLogger(__name__)


def user_rol(request):
    """Context processor para agregar el rol del usuario a todas las plantillas"""
    # ✅ Verificar que request y request.user existen
    if hasattr(request, 'user') and request.user.is_authenticated:
        try:
            usuario = Usuario.objects.get(id=request.user.id)
            return {
                'user_rol': usuario.rol,
                'rol': usuario.rol,  # ✅ Agregar 'rol' para consistencia
                'user_is_admin': usuario.rol == 'admin' or request.user.is_superuser,
                'user_is_tutor': usuario.rol == 'tutor',
                'user_is_profesor': usuario.rol == 'profesor',
                'user_is_estudiante': usuario.rol == 'estudiante',
                'user_full_name': usuario.get_full_name() or usuario.username,
                'user_carnet': getattr(usuario, 'carnet', None),
            }
        except Usuario.DoesNotExist:
            pass
        except Exception as e:
            logger.error(f"Error en user_rol context processor: {str(e)}")
    
    return {
        'user_rol': None,
        'rol': 'invitado',  # ✅ Valor por defecto
        'user_is_admin': False,
        'user_is_tutor': False,
        'user_is_profesor': False,
        'user_is_estudiante': False,
        'user_full_name': None,
        'user_carnet': None,
    }


def configuracion_sistema(request):
    """
    Context processor que inyecta la configuración del sistema en todos los templates.
    """
    # ✅ Verificar que request existe y tiene atributos
    if not hasattr(request, 'user'):
        return _default_config()
    
    try:
        # ✅ IMPORTAR CORRECTAMENTE
        from .models import ConfiguracionSistema
        
        # Intentar obtener configuración de la caché
        config_key = 'configuracion_sistema_activa'
        config = cache.get(config_key)
        
        if config is None:
            # ✅ Obtener universidad_id de forma segura
            universidad_id = None
            if request.user.is_authenticated:
                # ✅ Intentar diferentes formas de obtener la universidad
                if hasattr(request.user, 'idUniversidad_id'):
                    universidad_id = request.user.idUniversidad_id
                elif hasattr(request.user, 'idUniversidad'):
                    universidad_id = request.user.idUniversidad.id if request.user.idUniversidad else None
            
            if universidad_id:
                config = ConfiguracionSistema.objects.filter(
                    idUniversidad_id=universidad_id
                ).first()
            
            if not config:
                config = ConfiguracionSistema.objects.filter(
                    idUniversidad__isnull=True
                ).first()
            
            if config:
                cache.set(config_key, config, 300)
        
        if config:
            return {
                'config_sistema': config,
                'SITE_URL': config.sitio_url or getattr(settings, 'SITE_URL', 'http://localhost:8000'),
                'SITE_NAME': config.sitio_nombre or getattr(settings, 'SITE_NAME', 'RetenScan'),
                'SITE_DESCRIPTION': config.sitio_descripcion,
                'SITE_LOGO': config.sitio_logo.url if config.sitio_logo else None,
                'UNIVERSIDAD_NOMBRE': config.nombre_completo,
                'UNIVERSIDAD_SIGLAS': config.siglas,
                'COLOR_PRIMARIO': config.color_primario,
                'COLOR_SECUNDARIO': config.color_secundario,
                'COLOR_FONDO': config.color_fondo,
                'MANTENIMIENTO_SISTEMA': config.mante_sistema,
                'NOTIFICACIONES_EMAIL': config.notificaciones_email,
                'NOTIFICACIONES_WHATSAPP': config.notificaciones_whatsapp,
                'TWILIO_ENABLED': config.twilio_enabled,
                'SESSION_TIMEOUT_MINUTES': config.session_timeout_minutes,
                'LIMITE_INTENTOS_LOGIN': config.limite_intentos_login,
                'MOSTRAR_ESTADISTICAS': config.mostrar_estadisticas,
                'PERMITE_REGISTRO': config.permite_registro,
            }
    except Exception as e:
        # Si hay error, usar valores por defecto
        logger.error(f"Error en context processor configuracion_sistema: {str(e)}")
    
    # Valores por defecto
    return _default_config()


def _default_config():
    """Retorna valores por defecto para la configuración"""
    return {
        'config_sistema': None,
        'SITE_URL': getattr(settings, 'SITE_URL', 'http://localhost:8000'),
        'SITE_NAME': getattr(settings, 'SITE_NAME', 'RetenScan'),
        'SITE_DESCRIPTION': None,
        'SITE_LOGO': None,
        'UNIVERSIDAD_NOMBRE': None,
        'UNIVERSIDAD_SIGLAS': None,
        'COLOR_PRIMARIO': '#4e73df',
        'COLOR_SECUNDARIO': '#1cc88a',
        'COLOR_FONDO': '#f8f9fc',
        'MANTENIMIENTO_SISTEMA': False,
        'NOTIFICACIONES_EMAIL': True,
        'NOTIFICACIONES_WHATSAPP': False,
        'TWILIO_ENABLED': False,
        'SESSION_TIMEOUT_MINUTES': 240,
        'LIMITE_INTENTOS_LOGIN': 5,
        'MOSTRAR_ESTADISTICAS': True,
        'PERMITE_REGISTRO': True,
    }


def mensajes_no_leidos(request):
    """
    Context processor para agregar el contador de mensajes no leídos.
    """
    # ✅ Verificar que request y request.user existen
    if hasattr(request, 'user') and request.user.is_authenticated:
        try:
            from .models import Mensaje
            
            no_leidos = Mensaje.objects.filter(
                destinatario=request.user,
                leido=False
            ).count()
            
            return {
                'mensajes_no_leidos': no_leidos,
                'tiene_mensajes_no_leidos': no_leidos > 0,
            }
        except Exception as e:
            logger.error(f"Error en mensajes_no_leidos context processor: {str(e)}")
    
    return {
        'mensajes_no_leidos': 0,
        'tiene_mensajes_no_leidos': False,
    }

