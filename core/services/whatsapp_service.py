# core/services/whatsapp_service.py
"""
Servicio de envío de mensajes por WhatsApp usando Twilio
"""
import logging
from django.conf import settings
from .base import BaseService

logger = logging.getLogger(__name__)

TWILIO_AVAILABLE = False
TWILIO_ERROR = None

try:
    from twilio.rest import Client
    # Verificar configuración ANTES de marcar como disponible
    if hasattr(settings, 'TWILIO_ACCOUNT_SID') and settings.TWILIO_ACCOUNT_SID:
        if hasattr(settings, 'TWILIO_AUTH_TOKEN') and settings.TWILIO_AUTH_TOKEN:
            TWILIO_AVAILABLE = True
            logger.info("Twilio disponible para WhatsApp")
        else:
            logger.warning("Twilio instalado pero TWILIO_AUTH_TOKEN no configurado")
    else:
        logger.warning("Twilio instalado pero TWILIO_ACCOUNT_SID no configurado")
except ImportError:
    logger.info("Twilio no está instalado. Las notificaciones por WhatsApp no estarán disponibles.")
except Exception as e:
    TWILIO_ERROR = str(e)
    logger.warning(f"Error cargando Twilio: {str(e)}")


class WhatsAppService(BaseService):
    """Servicio para enviar mensajes por WhatsApp usando Twilio"""
    
    @staticmethod
    def _limpiar_numero(numero):
        """Limpia y formatea el número de teléfono"""
        if not numero:
            return None
        
        # Limpiar número
        numero = numero.replace(' ', '').replace('-', '').replace('(', '').replace(')', '')
        if not numero.startswith('+'):
            numero = f'+{numero}'
        
        if len(numero) < 10:
            logger.warning(f"Número inválido: {numero}")
            return None
        
        return numero
    
    @staticmethod
    def _verificar_configuracion():
        """Verifica que la configuración de Twilio esté completa"""
        if not TWILIO_AVAILABLE:
            logger.warning("Twilio no está disponible")
            return False
        
        if not hasattr(settings, 'TWILIO_ACCOUNT_SID') or not settings.TWILIO_ACCOUNT_SID:
            logger.warning("TWILIO_ACCOUNT_SID no configurado")
            return False
        
        if not hasattr(settings, 'TWILIO_AUTH_TOKEN') or not settings.TWILIO_AUTH_TOKEN:
            logger.warning("TWILIO_AUTH_TOKEN no configurado")
            return False
        
        if not hasattr(settings, 'TWILIO_WHATSAPP_FROM') or not settings.TWILIO_WHATSAPP_FROM:
            logger.warning("TWILIO_WHATSAPP_FROM no configurado")
            return False
        
        return True
    
    @classmethod
    def enviar_mensaje(cls, destinatario, mensaje):
        """
        Envía un mensaje por WhatsApp
        """
        if not cls._verificar_configuracion():
            return False
        
        if not destinatario:
            logger.warning("Intento de enviar WhatsApp sin destinatario")
            return False
        
        try:
            # Limpiar número
            destinatario = cls._limpiar_numero(destinatario)
            if not destinatario:
                return False
            
            client = Client(
                settings.TWILIO_ACCOUNT_SID,
                settings.TWILIO_AUTH_TOKEN
            )
            
            message = client.messages.create(
                from_=settings.TWILIO_WHATSAPP_FROM,
                body=mensaje,
                to=f'whatsapp:{destinatario}'
            )
            
            logger.info(f"WhatsApp enviado a {destinatario}: {message.sid}")
            return True
            
        except Exception as e:
            logger.error(f"Error al enviar WhatsApp a {destinatario}: {str(e)}")
            return False
    
    @classmethod
    def enviar_mensaje_con_enlace(cls, destinatario, mensaje, enlace):
        """
        Envía mensaje con enlace por WhatsApp
        """
        texto_completo = f"{mensaje}\n\nEnlace: {enlace}"
        return cls.enviar_mensaje(destinatario, texto_completo)