# core/services/email_service.py
"""
Servicio de envío de correos electrónicos
"""
import logging
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from django.conf import settings
from .base import BaseService

logger = logging.getLogger(__name__)


class EmailService(BaseService):
    """Servicio para enviar correos electrónicos"""
    
    @staticmethod
    def enviar_email(destinatario, asunto, template_html, template_texto=None, contexto=None):
        """
        Envía un correo electrónico con versión HTML y texto plano
        """
        if not destinatario:
            logger.warning("Intento de enviar email sin destinatario")
            return False
        
        if '@' not in destinatario:
            logger.warning(f"Email inválido: {destinatario}")
            return False
        
        if contexto is None:
            contexto = {}
        
        try:
            from django.template.exceptions import TemplateDoesNotExist
            
            try:
                html_content = render_to_string(template_html, contexto)
            except TemplateDoesNotExist:
                logger.error(f"Plantilla no encontrada: {template_html}")
                return False
            
            if template_texto:
                try:
                    text_content = render_to_string(template_texto, contexto)
                except TemplateDoesNotExist:
                    text_content = strip_tags(html_content)
            else:
                text_content = strip_tags(html_content)
            
            email = EmailMultiAlternatives(
                subject=asunto,
                body=text_content,
                from_email=settings.DEFAULT_FROM_EMAIL,
                to=[destinatario]
            )
            email.attach_alternative(html_content, "text/html")
            email.send()
            
            logger.info(f"Email enviado exitosamente a: {destinatario} - Asunto: {asunto}")
            return True
            
        except Exception as e:
            logger.error(f"Error al enviar email a {destinatario}: {str(e)}")
            return False
    
    @staticmethod
    def enviar_email_simple(destinatario, asunto, mensaje):
        """
        Envía un correo electrónico simple sin plantilla
        """
        if not destinatario:
            logger.warning("Intento de enviar email sin destinatario")
            return False
        
        try:
            from django.core.mail import send_mail
            
            send_mail(
                subject=asunto,
                message=mensaje,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[destinatario],
                fail_silently=False,
            )
            logger.info(f"Email simple enviado a: {destinatario}")
            return True
        except Exception as e:
            logger.error(f"Error enviando email simple a {destinatario}: {str(e)}")
            return False