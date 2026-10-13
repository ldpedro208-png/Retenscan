# core/middleware.py

from django.shortcuts import render, redirect
from django.urls import reverse, resolve, Resolver404
from django.utils.deprecation import MiddlewareMixin
from django.contrib.sessions.models import Session
from django.core.cache import cache
import re
from django.conf import settings
from django.core.mail import get_connection
from django.core.mail.backends.smtp import EmailBackend
import logging
from core.models import ConfiguracionSistema

logger = logging.getLogger(__name__)


class ForzarCambioPasswordMiddleware(MiddlewareMixin):

    EXEMPT_URLS = [
        r'^/admin/',                          # Admin de Django
        r'^/logout/',                         # Logout
        r'^/password_change/',                # Cambio de contraseña
        r'^/password_change/done/',           # Confirmación de cambio
        r'^/password_reset/',                 # Reset de contraseña
        r'^/password_reset/done/',            # Reset completado
        r'^/reset/',                          # Reset (Django auth)
        r'^/static/',                         # Archivos estáticos
        r'^/media/',                          # Archivos media
        r'^/favicon.ico$',                    # Favicon
        r'^/accounts/logout/',                # Logout alternativo
        r'^/accounts/password_change/',       # Cambio de contraseña alternativo
    ]
    
    # URLs de login que SÍ deben ser accesibles para autenticarse
    LOGIN_URLS = [
        r'^/login/',
        r'^/accounts/login/',
    ]
    
    def process_request(self, request):
        # 1. Si no está autenticado, no hacer nada
        if not request.user.is_authenticated:
            return None
        
        # 2. Si no debe cambiar contraseña, no hacer nada
        if not getattr(request.user, 'cambiar_password', False):
            return None
        
        path = request.path_info
        
        # 3. Verificar si es una URL exenta (password_change, logout, etc.)
        for pattern in self.EXEMPT_URLS:
            if re.match(pattern, path):
                return None
        
        # 4. Verificar si es una URL de login
        for pattern in self.LOGIN_URLS:
            if re.match(pattern, path):
                return None
        
        # 5. Verificar si es una URL de la API (opcional)
        if path.startswith('/api/'):
            return None
        
        # 6. Verificar si es un archivo estático/media (redundante con EXEMPT_URLS)
        if path.startswith('/static/') or path.startswith('/media/'):
            return None
        
        # 7. Redirigir al cambio de contraseña
        password_change_url = reverse('password_change')
        
        # ⚠️ IMPORTANTE: Evitar bucle infinito
        # Si ya estamos en password_change, no redirigir
        if path == password_change_url:
            return None
        
        logger.info(
            f"🔒 Usuario @{request.user.username} debe cambiar contraseña. "
            f"Redirigiendo de '{path}' a '{password_change_url}'"
        )
        
        return redirect(password_change_url)


class SessionControlMiddleware(MiddlewareMixin):
    """
    Middleware para controlar sesiones activas por usuario.
    """

    SESSION_LIMITS = {
        'admin': 3,
        'tutor': 2,
        'profesor': 2,
        'estudiante': 1,
        'default': 2
    }

    def process_request(self, request):
        if not request.user.is_authenticated:
            return None

        rol = getattr(request.user, 'rol', 'default')
        max_sessions = self.SESSION_LIMITS.get(rol, self.SESSION_LIMITS['default'])
        user_session_key = f'user_sessions_{request.user.id}'
        active_sessions = cache.get(user_session_key, [])
        current_session_key = request.session.session_key

        if current_session_key and current_session_key not in active_sessions:
            active_sessions.append(current_session_key)

        if len(active_sessions) > max_sessions:
            sessions_to_remove = active_sessions[:-max_sessions]
            for session_key in sessions_to_remove:
                if session_key != current_session_key:
                    try:
                        Session.objects.get(session_key=session_key).delete()
                    except Session.DoesNotExist:
                        pass

            active_sessions = [s for s in active_sessions if s == current_session_key or s in active_sessions]
            active_sessions = active_sessions[-max_sessions:]

        cache.set(user_session_key, active_sessions, 86400)
        return None


class ConfiguracionDinamicaMiddleware:
    """
    Middleware que aplica configuración dinámica desde la base de datos.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        try:
            self._aplicar_configuracion(request)
        except Exception as e:
            logger.error(f"Error en ConfiguracionDinamicaMiddleware: {str(e)}")

        response = self.get_response(request)
        return response

    def _aplicar_configuracion(self, request):
        try:
            from core.models import ConfiguracionSistema

            config_key = 'configuracion_sistema_activa'
            config = cache.get(config_key)

            if config is None:
                if hasattr(request, 'user') and request.user.is_authenticated:
                    universidad_id = getattr(request.user, 'idUniversidad_id', None)
                    if universidad_id:
                        config = ConfiguracionSistema.objects.filter(
                            idUniversidad_id=universidad_id
                        ).first()

                if not config:
                    config = ConfiguracionSistema.objects.filter(
                        idUniversidad__isnull=True
                    ).first()

                cache.set(config_key, config, 300)

            if config:
                self._aplicar_settings(config, request)

        except Exception as e:
            logger.error(f"Error aplicando configuración dinámica: {str(e)}")

    def _aplicar_settings(self, config, request):
        try:
            if config.sitio_url:
                settings.SITE_URL = config.sitio_url

            if config.email_host_user and config.email_host_password:
                settings.EMAIL_HOST = config.email_host
                settings.EMAIL_PORT = config.email_port
                settings.EMAIL_USE_TLS = config.email_use_tls
                settings.EMAIL_HOST_USER = config.email_host_user
                settings.EMAIL_HOST_PASSWORD = config.email_host_password
                settings.DEFAULT_FROM_EMAIL = config.email_from or config.email_host_user

                if hasattr(settings, '_email_backend'):
                    delattr(settings, '_email_backend')

            if config.twilio_enabled:
                settings.TWILIO_ENABLED = True
                settings.TWILIO_ACCOUNT_SID = config.twilio_account_sid
                settings.TWILIO_AUTH_TOKEN = config.twilio_auth_token
                settings.TWILIO_WHATSAPP_NUMBER = config.twilio_whatsapp_number
            else:
                settings.TWILIO_ENABLED = False

            if config.require_https:
                settings.SESSION_COOKIE_SECURE = True
                settings.CSRF_COOKIE_SECURE = True
                settings.SECURE_SSL_REDIRECT = True
            else:
                settings.SESSION_COOKIE_SECURE = False
                settings.CSRF_COOKIE_SECURE = False
                settings.SECURE_SSL_REDIRECT = False

            if config.allowed_hosts:
                hosts = [h.strip() for h in config.allowed_hosts.split(',') if h.strip()]
                if hosts:
                    settings.ALLOWED_HOSTS = hosts

            if config.session_timeout_minutes:
                settings.SESSION_COOKIE_AGE = config.session_timeout_minutes * 60

            if config.cache_timeout:
                settings.CACHE_MIDDLEWARE_SECONDS = config.cache_timeout

            if hasattr(config, 'mante_sistema'):
                request.mante_sistema = bool(config.mante_sistema)

        except Exception as e:
            logger.error(f"Error aplicando configuración a settings: {str(e)}")


class SistemaMantenimientoMiddleware:
    """
    Middleware que bloquea el acceso cuando el sistema está en mantenimiento.
    """

    def __init__(self, get_response):
        self.get_response = get_response
        self.exempt_paths = [
            '/admin/',
            '/login/',
            '/logout/',
            '/configuracion/',
            '/static/',
            '/media/',
        ]

    def __call__(self, request):
        try:
            mante_sistema = getattr(request, 'mante_sistema', False)

            if mante_sistema:
                path = request.path_info
                for exempt_path in self.exempt_paths:
                    if path.startswith(exempt_path):
                        return self.get_response(request)

                if hasattr(request, 'user') and request.user.is_authenticated:
                    rol = getattr(request.user, 'rol', '')
                    if rol == 'admin' or request.user.is_superuser:
                        return self.get_response(request)

                return render(request, 'mantenimiento.html', status=503)

        except Exception as e:
            logger.error(f"Error en SistemaMantenimientoMiddleware: {str(e)}")

        return self.get_response(request)