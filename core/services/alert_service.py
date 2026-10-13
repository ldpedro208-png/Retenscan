# core/services/alert_service.py

"""
Sistema de alertas y notificaciones
"""
import logging
from django.conf import settings

# ✅ Importar logger desde logging_config
from ..logging_config import logger

# ✅ Importar servicios directamente
from .email_service import EmailService
from .whatsapp_service import WhatsAppService


class AlertaService:
    """
    Servicio para gestionar alertas y notificaciones.
    """
    
    @classmethod
    def _enviar_notificacion(cls, usuario, asunto, mensaje, enlace, template_html=None, template_texto=None, contexto=None):
        """Envía notificación por todos los canales configurados"""
        resultados = []
        
        # Enviar por email
        if usuario.notificaciones_email and usuario.email:
            logger.info(f"Enviando email a: {usuario.email} - {asunto}")
            
            if template_html and template_texto and contexto:
                resultado = EmailService.enviar_email(
                    destinatario=usuario.email,
                    asunto=asunto,
                    template_html=template_html,
                    template_texto=template_texto,
                    contexto=contexto
                )
                resultados.append(('email', resultado))
            else:
                resultado = EmailService.enviar_email_simple(
                    destinatario=usuario.email,
                    asunto=asunto,
                    mensaje=mensaje
                )
                resultados.append(('email', resultado))
        
        # Enviar por WhatsApp
        if usuario.notificaciones_whatsapp and usuario.whatsapp_telefono:
            logger.info(f"Enviando WhatsApp a: {usuario.whatsapp_telefono}")
            
            mensaje_whatsapp = f"{mensaje}\n\nEnlace: {enlace}"
            resultado = WhatsAppService.enviar_mensaje(usuario.whatsapp_telefono, mensaje_whatsapp)
            resultados.append(('whatsapp', resultado))
        
        return resultados
    
    @classmethod
    def _crear_notificacion_interna(cls, usuario, titulo, mensaje, tipo='info', url=None):
        """Crea una notificación interna en la base de datos"""
        try:
            from core.models import Notificacion
            
            notificacion = Notificacion.objects.create(
                usuario=usuario,
                titulo=titulo,
                mensaje=mensaje,
                tipo=tipo,
                url=url or '/'
            )
            logger.info(f"Notificación interna creada para {usuario.username}: {titulo}")
            return notificacion
        except Exception as e:
            logger.error(f"Error creando notificación interna: {str(e)}")
            return None
    
    # ============================================
    # NOTIFICACIONES DE CREDENCIALES
    # ============================================
    
    @classmethod
    def notificar_credenciales(cls, usuario, password_temporal, es_primera_vez=True):
        """Envía email con las credenciales al usuario"""
        if not usuario:
            logger.warning("Intento de notificar credenciales sin usuario")
            return False
        
        if not usuario.email:
            logger.warning(f"Usuario {usuario.username} no tiene email")
            return False
        
        if not usuario.notificaciones_email:
            logger.info(f"Usuario {usuario.username} tiene notificaciones email desactivadas")
            return False
        
        logger.info(f"Intentando enviar credenciales a: {usuario.email} - Usuario: {usuario.username}")
        
        # Obtener el nombre del rol
        roles_dict = dict(getattr(usuario.__class__, 'ROL_CHOICES', []))
        rol_display = roles_dict.get(usuario.rol, usuario.rol)
        
        # Obtener la URL del sitio
        site_url = getattr(settings, 'SITE_URL', 'http://localhost:8000')
        
        contexto = {
            'usuario': usuario,
            'password_temporal': password_temporal,
            'es_primera_vez': es_primera_vez,
            'rol_display': rol_display,
            'site_name': 'RetenScan',
            'url_login': f"{site_url}/accounts/login/",
            'url_cambiar_password': f"{site_url}/password_change/",
        }
        
        asunto = f"Bienvenido a RetenScan - Tus credenciales de acceso"
        
        resultado = EmailService.enviar_email(
            destinatario=usuario.email,
            asunto=asunto,
            template_html='emails/credenciales_usuario.html',
            template_texto='emails/credenciales_usuario.txt',
            contexto=contexto
        )
        
        if resultado:
            logger.info(f"Credenciales enviadas exitosamente a: {usuario.email}")
        else:
            logger.error(f"Falló el envío de credenciales a: {usuario.email}")
        
        return resultado
    
    @classmethod
    def notificar_credenciales_usuario(cls, usuario, password_temporal, request=None):
        """Envía credenciales a un usuario (alias para notificar_credenciales)"""
        return cls.notificar_credenciales(usuario, password_temporal, es_primera_vez=True)
    
    # ============================================
    # ALERTAS DE RIESGO
    # ============================================
    
    @classmethod
    def alerta_estudiante_riesgo(cls, estudiante, riesgo):
        """Envía alerta cuando un estudiante entra en riesgo"""
        from core.models import Usuario
        
        logger.info(f"Alertando sobre estudiante en riesgo: {estudiante.nombre}")
        
        # Obtener tutores del estudiante
        tutores = Usuario.objects.filter(
            usuarioestudiantes__estudiante=estudiante,
            rol='tutor'
        )
        
        resultados = []
        for tutor in tutores:
            contexto = {
                'estudiante': estudiante,
                'riesgo': riesgo,
                'tutor': tutor,
                'url_estudiante': f"{settings.SITE_URL}/estudiantes/{estudiante.idEstudiante}/",
                'site_name': 'RetenScan',
            }
            
            asunto = f"Alerta de Riesgo - {estudiante.nombre} {estudiante.apellido_paterno}"
            mensaje = f"Alerta: {estudiante.nombre} {estudiante.apellido_paterno} ha sido identificado con riesgo de deserción.\n\nFactor: {riesgo.idFactor.nombre}\nNivel: {riesgo.nivel}"
            enlace = f"{settings.SITE_URL}/estudiantes/{estudiante.idEstudiante}/"
            
            resultado = cls._enviar_notificacion(
                usuario=tutor,
                asunto=asunto,
                mensaje=mensaje,
                enlace=enlace,
                template_html='emails/alerta_riesgo.html',
                template_texto='emails/alerta_riesgo.txt',
                contexto=contexto
            )
            resultados.extend(resultado)
            
            # Crear notificación interna
            cls._crear_notificacion_interna(
                usuario=tutor,
                titulo=asunto,
                mensaje=mensaje,
                tipo='riesgo',
                url=enlace
            )
        
        return resultados
    
    # ============================================
    # NOTIFICACIONES DE TAREAS
    # ============================================
    
    @classmethod
    def notificar_tarea_asignada(cls, estudiante, tarea, asignacion):
        """Notifica a un estudiante cuando se le asigna una tarea"""
        usuario = estudiante.idUsuario
        if not usuario:
            logger.warning(f"Estudiante {estudiante.nombre} no tiene usuario asociado")
            return False
        
        if not usuario.email and not usuario.whatsapp_telefono:
            logger.warning(f"Usuario {usuario.username} no tiene email ni WhatsApp")
            return False
        
        logger.info(f"Notificando tarea '{tarea.titulo}' a {usuario.username}")
        
        site_url = getattr(settings, 'SITE_URL', 'http://localhost:8000')
        
        contexto = {
            'estudiante': estudiante,
            'tarea': tarea,
            'asignacion': asignacion,
            'url_tarea': f"{site_url}/tareas/{tarea.idTarea}/",
            'site_name': 'RetenScan',
        }
        
        asunto = f"Nueva Tarea Asignada - {tarea.titulo}"
        mensaje = f"Nueva Tarea: {tarea.titulo}\n\nFecha límite: {tarea.fecha_limite.strftime('%d/%m/%Y %H:%M')}"
        enlace = f"{site_url}/tareas/{tarea.idTarea}/"
        
        resultados = cls._enviar_notificacion(
            usuario=usuario,
            asunto=asunto,
            mensaje=mensaje,
            enlace=enlace,
            template_html='emails/tarea_asignada.html',
            template_texto='emails/tarea_asignada.txt',
            contexto=contexto
        )
        
        # Crear notificación interna
        cls._crear_notificacion_interna(
            usuario=usuario,
            titulo=asunto,
            mensaje=mensaje,
            tipo='tarea',
            url=enlace
        )
        
        return resultados
    
    @classmethod
    def notificar_recordatorio_tarea(cls, estudiante, tarea, dias_restantes):
        """Envía recordatorio de tarea pendiente"""
        try:
            usuario = estudiante.idUsuario
            
            if not usuario:
                logger.warning(f"Estudiante {estudiante.idEstudiante} no tiene usuario asociado")
                return False
            
            mensaje = (
                f"📝 RECORDATORIO DE TAREA\n\n"
                f"Estimado(a) {usuario.first_name},\n\n"
                f"Tienes una tarea pendiente por entregar:\n"
                f"📚 {tarea.titulo}\n\n"
                f"⏰ Vence en {dias_restantes} días ({tarea.fecha_limite.strftime('%d/%m/%Y')})\n\n"
                f"Por favor, entrega la tarea a la brevedad posible."
            )
            
            asunto = f"⏰ Recordatorio: {tarea.titulo}"
            enlace = f"{settings.SITE_URL}/tareas/{tarea.idTarea}/"
            
            # Enviar notificación
            resultados = cls._enviar_notificacion(
                usuario=usuario,
                asunto=asunto,
                mensaje=mensaje,
                enlace=enlace
            )
            
            # Crear notificación interna
            cls._crear_notificacion_interna(
                usuario=usuario,
                titulo=asunto,
                mensaje=mensaje,
                tipo='recordatorio',
                url=enlace
            )
            
            logger.info(f"Recordatorio de tarea enviado a {usuario.email}")
            return resultados
            
        except Exception as e:
            logger.error(f"Error enviando recordatorio de tarea: {str(e)}")
            return False
    
    # ============================================
    # NOTIFICACIONES DE ENCUESTAS
    # ============================================
    
    @classmethod
    def notificar_encuesta_asignada(cls, estudiante, encuesta, asignacion):
        """Notifica a un estudiante cuando se le asigna una encuesta"""
        usuario = estudiante.idUsuario
        if not usuario:
            logger.warning(f"Estudiante {estudiante.nombre} no tiene usuario asociado")
            return False
        
        if not usuario.email and not usuario.whatsapp_telefono:
            logger.warning(f"Usuario {usuario.username} no tiene email ni WhatsApp")
            return False
        
        logger.info(f"Notificando encuesta '{encuesta.titulo}' a {usuario.username}")
        
        site_url = getattr(settings, 'SITE_URL', 'http://localhost:8000')
        
        contexto = {
            'estudiante': estudiante,
            'encuesta': encuesta,
            'asignacion': asignacion,
            'url_encuesta': f"{site_url}/encuestas/{encuesta.idEncuesta}/",
            'site_name': 'RetenScan',
        }
        
        asunto = f"Nueva Encuesta Asignada - {encuesta.titulo}"
        mensaje = f"Nueva Encuesta: {encuesta.titulo}\n\nFecha límite: {encuesta.fecha_fin.strftime('%d/%m/%Y %H:%M')}"
        enlace = f"{site_url}/encuestas/{encuesta.idEncuesta}/"
        
        resultados = cls._enviar_notificacion(
            usuario=usuario,
            asunto=asunto,
            mensaje=mensaje,
            enlace=enlace,
            template_html='emails/encuesta_asignada.html',
            template_texto='emails/encuesta_asignada.txt',
            contexto=contexto
        )
        
        # Crear notificación interna
        cls._crear_notificacion_interna(
            usuario=usuario,
            titulo=asunto,
            mensaje=mensaje,
            tipo='encuesta',
            url=enlace
        )
        
        return resultados
    
    @classmethod
    def notificar_recordatorio_encuesta(cls, estudiante, encuesta, dias_restantes):
        """Envía recordatorio de encuesta pendiente"""
        try:
            usuario = estudiante.idUsuario
            
            if not usuario:
                logger.warning(f"Estudiante {estudiante.idEstudiante} no tiene usuario asociado")
                return False
            
            mensaje = (
                f"📋 RECORDATORIO DE ENCUESTA\n\n"
                f"Estimado(a) {usuario.first_name},\n\n"
                f"Tienes una encuesta pendiente por completar:\n"
                f"📝 {encuesta.titulo}\n\n"
                f"⏰ Vence en {dias_restantes} días ({encuesta.fecha_fin.strftime('%d/%m/%Y')})\n\n"
                f"Por favor, completa la encuesta a la brevedad posible."
            )
            
            asunto = f"⏰ Recordatorio: {encuesta.titulo}"
            enlace = f"{settings.SITE_URL}/encuestas/{encuesta.idEncuesta}/"
            
            # Enviar notificación
            resultados = cls._enviar_notificacion(
                usuario=usuario,
                asunto=asunto,
                mensaje=mensaje,
                enlace=enlace
            )
            
            # Crear notificación interna
            cls._crear_notificacion_interna(
                usuario=usuario,
                titulo=asunto,
                mensaje=mensaje,
                tipo='recordatorio',
                url=enlace
            )
            
            logger.info(f"Recordatorio de encuesta enviado a {usuario.email}")
            return resultados
            
        except Exception as e:
            logger.error(f"Error enviando recordatorio de encuesta: {str(e)}")
            return False
    
    # ============================================
    # NOTIFICACIONES DE REUNIONES
    # ============================================
    
    @classmethod
    def notificar_reunion_programada(cls, tutor, estudiante, reunion):
        """Notifica al tutor y al estudiante cuando se programa una reunión"""
        logger.info(f"Notificando reunión '{reunion.titulo}' programada")
        resultados = []
        
        site_url = getattr(settings, 'SITE_URL', 'http://localhost:8000')
        
        # Obtener fecha formateada de manera segura
        try:
            if hasattr(reunion.fecha_programada, 'strftime'):
                fecha_formateada = reunion.fecha_programada.strftime('%d/%m/%Y %H:%M')
            else:
                fecha_formateada = str(reunion.fecha_programada)
        except Exception as e:
            logger.error(f"Error al formatear fecha: {str(e)}")
            fecha_formateada = "Fecha no disponible"
        
        # Notificar al tutor
        if tutor and (tutor.email or tutor.whatsapp_telefono):
            logger.info(f"Notificando al tutor: {tutor.username}")
            
            contexto_tutor = {
                'estudiante': estudiante,
                'reunion': reunion,
                'fecha_formateada': fecha_formateada,
                'url_reunion': f"{site_url}/reuniones/{reunion.idReunion}/",
                'site_name': 'RetenScan',
                'es_tutor': True,
            }
            
            asunto_tutor = f"Reunión Programada - {estudiante.nombre} {estudiante.apellido_paterno}"
            mensaje_tutor = f"Reunión programada con {estudiante.nombre} {estudiante.apellido_paterno}\n\nTítulo: {reunion.titulo}\nFecha: {fecha_formateada}\nUbicación: {reunion.ubicacion or 'Por definir'}"
            enlace = f"{site_url}/reuniones/{reunion.idReunion}/"
            
            resultados.extend(
                cls._enviar_notificacion(
                    usuario=tutor,
                    asunto=asunto_tutor,
                    mensaje=mensaje_tutor,
                    enlace=enlace,
                    template_html='emails/reunion_programada_tutor.html',
                    template_texto='emails/reunion_programada_tutor.txt',
                    contexto=contexto_tutor
                )
            )
            
            # Crear notificación interna para el tutor
            cls._crear_notificacion_interna(
                usuario=tutor,
                titulo=asunto_tutor,
                mensaje=mensaje_tutor,
                tipo='reunion',
                url=enlace
            )
        
        # Notificar al estudiante
        usuario_estudiante = estudiante.idUsuario
        if usuario_estudiante and (usuario_estudiante.email or usuario_estudiante.whatsapp_telefono):
            logger.info(f"Notificando al estudiante: {usuario_estudiante.username}")
            
            contexto_estudiante = {
                'estudiante': estudiante,
                'reunion': reunion,
                'fecha_formateada': fecha_formateada,
                'url_reunion': f"{site_url}/reuniones/{reunion.idReunion}/",
                'site_name': 'RetenScan',
                'es_tutor': False,
            }
            
            asunto_estudiante = f"Reunión Programada - {reunion.titulo}"
            mensaje_estudiante = f"Reunión programada con tu tutor\n\nTítulo: {reunion.titulo}\nFecha: {fecha_formateada}\nUbicación: {reunion.ubicacion or 'Por definir'}"
            enlace = f"{site_url}/reuniones/{reunion.idReunion}/"
            
            resultados.extend(
                cls._enviar_notificacion(
                    usuario=usuario_estudiante,
                    asunto=asunto_estudiante,
                    mensaje=mensaje_estudiante,
                    enlace=enlace,
                    template_html='emails/reunion_programada_estudiante.html',
                    template_texto='emails/reunion_programada_estudiante.txt',
                    contexto=contexto_estudiante
                )
            )
            
            # Crear notificación interna para el estudiante
            cls._crear_notificacion_interna(
                usuario=usuario_estudiante,
                titulo=asunto_estudiante,
                mensaje=mensaje_estudiante,
                tipo='reunion',
                url=enlace
            )
        
        return resultados
    
    @classmethod
    def notificar_recordatorio_reunion(cls, tutor, estudiante, reunion):
        """Envía recordatorio de una reunión"""
        logger.info(f"Enviando recordatorio de reunión '{reunion.titulo}'")
        
        site_url = getattr(settings, 'SITE_URL', 'http://localhost:8000')
        
        # Obtener fecha formateada
        try:
            if hasattr(reunion.fecha_programada, 'strftime'):
                fecha_formateada = reunion.fecha_programada.strftime('%d/%m/%Y %H:%M')
            else:
                fecha_formateada = str(reunion.fecha_programada)
        except:
            fecha_formateada = "Fecha no disponible"
        
        # Notificar al tutor
        if tutor and (tutor.email or tutor.whatsapp_telefono):
            mensaje_tutor = f"Recordatorio: Reunión con {estudiante.nombre} {estudiante.apellido_paterno}\n\nTítulo: {reunion.titulo}\nFecha: {fecha_formateada}\nUbicación: {reunion.ubicacion or 'Por definir'}"
            enlace = f"{site_url}/reuniones/{reunion.idReunion}/"
            asunto = f"Recordatorio: Reunión con {estudiante.nombre}"
            
            cls._enviar_notificacion(
                usuario=tutor,
                asunto=asunto,
                mensaje=mensaje_tutor,
                enlace=enlace
            )
            
            # Crear notificación interna
            cls._crear_notificacion_interna(
                usuario=tutor,
                titulo=asunto,
                mensaje=mensaje_tutor,
                tipo='recordatorio',
                url=enlace
            )
        
        # Notificar al estudiante
        usuario_estudiante = estudiante.idUsuario
        if usuario_estudiante and (usuario_estudiante.email or usuario_estudiante.whatsapp_telefono):
            mensaje_estudiante = f"Recordatorio: Reunión con tu tutor\n\nTítulo: {reunion.titulo}\nFecha: {fecha_formateada}\nUbicación: {reunion.ubicacion or 'Por definir'}"
            enlace = f"{site_url}/reuniones/{reunion.idReunion}/"
            asunto = f"Recordatorio: {reunion.titulo}"
            
            cls._enviar_notificacion(
                usuario=usuario_estudiante,
                asunto=asunto,
                mensaje=mensaje_estudiante,
                enlace=enlace
            )
            
            # Crear notificación interna
            cls._crear_notificacion_interna(
                usuario=usuario_estudiante,
                titulo=asunto,
                mensaje=mensaje_estudiante,
                tipo='recordatorio',
                url=enlace
            )

    # ============================================
    # NOTIFICACIONES DE INTERVENCIONES
    # ============================================
    
    @classmethod
    def notificar_intervencion_creada(cls, estudiante, intervencion):
        """
        Notifica cuando se crea una intervención para un estudiante
        """
        try:
            usuario = estudiante.idUsuario
            if not usuario:
                logger.warning(f"Estudiante {estudiante.idEstudiante} no tiene usuario asociado")
                return False
            
            site_url = getattr(settings, 'SITE_URL', 'http://localhost:8000')
            
            # Obtener tipo de intervención
            tipo_display = dict(intervencion.TIPO_CHOICES).get(intervencion.tipo_intervencion, intervencion.tipo_intervencion)
            
            mensaje = (
                f"🤝 NUEVA INTERVENCIÓN REGISTRADA\n\n"
                f"Estimado(a) {usuario.first_name},\n\n"
                f"Se ha registrado una intervención para ti:\n"
                f"📋 Tipo: {tipo_display}\n"
                f"📅 Fecha programada: {intervencion.fecha_programada}\n"
                f"👤 Responsable: {intervencion.responsable}\n\n"
                f"Descripción: {intervencion.descripcion}\n\n"
                f"Por favor, mantente atento a las indicaciones."
            )
            
            asunto = f"🤝 Nueva Intervención - {tipo_display}"
            enlace = f"{site_url}/estudiantes/{estudiante.idEstudiante}/"
            
            resultados = cls._enviar_notificacion(
                usuario=usuario,
                asunto=asunto,
                mensaje=mensaje,
                enlace=enlace
            )
            
            # Crear notificación interna
            cls._crear_notificacion_interna(
                usuario=usuario,
                titulo=asunto,
                mensaje=mensaje,
                tipo='intervencion',
                url=enlace
            )
            
            return resultados
            
        except Exception as e:
            logger.error(f"Error notificando intervención creada: {str(e)}")
            return False

    @classmethod
    def notificar_riesgo_resuelto(cls, estudiante, riesgo):
        """
        Notifica cuando un riesgo es resuelto
        """
        try:
            usuario = estudiante.idUsuario
            if not usuario:
                logger.warning(f"Estudiante {estudiante.idEstudiante} no tiene usuario asociado")
                return False
            
            site_url = getattr(settings, 'SITE_URL', 'http://localhost:8000')
            
            mensaje = (
                f"✅ RIESGO RESUELTO\n\n"
                f"Estimado(a) {usuario.first_name},\n\n"
                f"Nos complace informarte que el riesgo detectado ha sido resuelto:\n"
                f"📋 Factor: {riesgo.idFactor.nombre}\n"
                f"📊 Nivel anterior: {riesgo.get_nivel_display()}\n\n"
                f"¡Sigue así! Continúa con tu buen desempeño académico."
            )
            
            asunto = f"✅ Riesgo Resuelto - {riesgo.idFactor.nombre}"
            enlace = f"{site_url}/estudiantes/{estudiante.idEstudiante}/"
            
            resultados = cls._enviar_notificacion(
                usuario=usuario,
                asunto=asunto,
                mensaje=mensaje,
                enlace=enlace
            )
            
            # Crear notificación interna
            cls._crear_notificacion_interna(
                usuario=usuario,
                titulo=asunto,
                mensaje=mensaje,
                tipo='riesgo_resuelto',
                url=enlace
            )
            
            return resultados
            
        except Exception as e:
            logger.error(f"Error notificando riesgo resuelto: {str(e)}")
            return False