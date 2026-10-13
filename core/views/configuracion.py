# core/views/configuracion.py

from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.db.models import Count
from django.core.cache import cache
from django.core.mail import send_mail, get_connection
from django.http import JsonResponse, HttpResponse
from django.conf import settings
from datetime import datetime
import json
import logging

from ..models import CatalogoUniversidad, Usuario, ConfiguracionSistema
from ..forms import ConfiguracionSistemaForm
from .base import get_universidad_id, logger

logger = logging.getLogger(__name__)


# ============================================
# VISTA PRINCIPAL - CONFIGURACIÓN DEL SISTEMA
# ============================================

@login_required
def configuracion_sistema(request):
    """
    Panel de configuración unificado del sistema.
    Incluye configuración de red, email, WhatsApp, universidad, etc.
    Solo administradores pueden acceder.
    """
    user_rol = request.user.rol
    
    # Verificar permisos - solo administradores
    if user_rol != 'admin' and not request.user.is_superuser:
        messages.error(request, "No tienes permiso para acceder a la configuración.")
        return redirect('dashboard')
    
    universidad_id = get_universidad_id(request)
    
    # Obtener la universidad del usuario
    if request.user.is_superuser:
        universidad_id_param = request.GET.get('universidad_id')
        if universidad_id_param:
            universidad = get_object_or_404(CatalogoUniversidad, idUniversidad=universidad_id_param)
            universidad_id = universidad.idUniversidad
        else:
            universidad = request.user.idUniversidad
    else:
        universidad = request.user.idUniversidad
    
    if not universidad:
        messages.error(request, "No tienes una universidad asignada.")
        return redirect('dashboard')
    
    # Obtener o crear configuración
    config, created = ConfiguracionSistema.objects.get_or_create(
        idUniversidad=universidad
    )
    
    # Si es nueva configuración, establecer valores por defecto
    if created:
        config.sitio_nombre = universidad.nombre or 'RetenScan'
        config.nombre_completo = universidad.nombre
        config.sitio_url = getattr(settings, 'SITE_URL', 'http://localhost:8000')
        config.save()
        messages.info(request, "Configuración inicial creada. Revisa los valores por defecto.")
    
    # Obtener estadísticas de la universidad
    stats = {
        'total_estudiantes': universidad.estudiantes.count() if hasattr(universidad, 'estudiantes') else 0,
        'total_profesores': Usuario.objects.filter(idUniversidad=universidad, rol='profesor').count(),
        'total_tutores': Usuario.objects.filter(idUniversidad=universidad, rol='tutor').count(),
        'total_admins': Usuario.objects.filter(idUniversidad=universidad, rol='admin').count(),
        'total_usuarios': Usuario.objects.filter(idUniversidad=universidad).count(),
        'total_materias': universidad.materias_catalogo.count() if hasattr(universidad, 'materias_catalogo') else 0,
        'total_aulas': universidad.aulas_negocio.count() if hasattr(universidad, 'aulas_negocio') else 0,
        'total_carreras': universidad.carreras_catalogo.count() if hasattr(universidad, 'carreras_catalogo') else 0,
    }
    
    if request.method == 'POST':
        form = ConfiguracionSistemaForm(request.POST, request.FILES, instance=config)
        
        if form.is_valid():
            try:
                config = form.save(commit=False)
                config.idUniversidad = universidad
                config.actualizado_por = request.user
                config.save()
                
                # Si se envió un email de prueba
                if 'test_email' in request.POST and config.email_test_recipient:
                    test_result = _test_email_configuration(config, request)
                    if test_result['success']:
                        messages.success(request, f"✅ Configuración guardada. Email de prueba enviado exitosamente a {config.email_test_recipient}.")
                    else:
                        messages.warning(request, f"⚠️ Configuración guardada, pero falló el envío del email de prueba: {test_result['error']}")
                
                # Si se envió un test de WhatsApp
                elif 'test_whatsapp' in request.POST and config.twilio_enabled:
                    test_result = _test_whatsapp_configuration(config, request)
                    if test_result['success']:
                        messages.success(request, "✅ Configuración guardada. Mensaje de WhatsApp enviado exitosamente.")
                    else:
                        messages.warning(request, f"⚠️ Configuración guardada, pero falló el envío de WhatsApp: {test_result['error']}")
                
                else:
                    messages.success(request, '✅ Configuración guardada exitosamente.')
                
                # Limpiar cache relacionado
                _clear_config_cache()
                
                # Registrar en auditoría
                _log_config_change(request.user, config, 'actualización')
                
                return redirect('configuracion_sistema')
                
            except Exception as e:
                logger.error(f"Error al guardar configuración: {str(e)}")
                messages.error(request, f"Error al guardar la configuración: {str(e)}")
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f"{field}: {error}")
    else:
        form = ConfiguracionSistemaForm(instance=config)
    
    # Obtener todas las universidades para superuser
    universidades = CatalogoUniversidad.objects.all() if request.user.is_superuser else []
    
    context = {
        'form': form,
        'config': config,
        'universidad': universidad,
        'universidades': universidades,
        'stats': stats,
        'user_rol': user_rol,
        'is_superuser': request.user.is_superuser,
        'titulo': 'Configuración del Sistema',
        'SITE_URL': getattr(settings, 'SITE_URL', 'http://localhost:8000'),
        'SITE_NAME': getattr(settings, 'SITE_NAME', 'RetenScan'),
    }
    
    return render(request, 'configuracion/configuracion_sistema.html', context)


# ============================================
# FUNCIONES AUXILIARES
# ============================================

def _test_email_configuration(config, request):
    """Prueba la configuración de email."""
    try:
        connection = get_connection(
            host=config.email_host,
            port=config.email_port,
            username=config.email_host_user,
            password=config.email_host_password,
            use_tls=config.email_use_tls,
            fail_silently=False,
        )
        
        connection.open()
        connection.close()
        
        send_mail(
            subject=f'Prueba de configuración - {config.sitio_nombre}',
            message=f'✅ Esta es una prueba exitosa de configuración de email.\n\n'
                    f'Sitio: {config.sitio_nombre}\n'
                    f'URL: {config.sitio_url}\n'
                    f'Universidad: {config.nombre_completo}\n'
                    f'Fecha: {datetime.now().strftime("%d/%m/%Y %H:%M:%S")}\n\n'
                    f'Si recibiste este correo, la configuración es correcta.',
            from_email=config.email_from or config.email_host_user,
            recipient_list=[config.email_test_recipient],
            fail_silently=False,
            connection=connection,
        )
        
        return {'success': True}
    except Exception as e:
        logger.error(f"Error en prueba de email: {str(e)}")
        return {'success': False, 'error': str(e)}


def _test_whatsapp_configuration(config, request):
    """Prueba la configuración de WhatsApp (Twilio)."""
    if not config.twilio_enabled:
        return {'success': False, 'error': 'WhatsApp no está habilitado'}
    
    if not config.twilio_account_sid or not config.twilio_auth_token:
        return {'success': False, 'error': 'Credenciales de Twilio no configuradas'}
    
    try:
        from twilio.rest import Client
        
        client = Client(config.twilio_account_sid, config.twilio_auth_token)
        
        user_phone = request.user.whatsapp_telefono or request.user.telefono
        
        if not user_phone:
            return {'success': False, 'error': 'El usuario no tiene un número de teléfono configurado'}
        
        if not user_phone.startswith('whatsapp:'):
            if not user_phone.startswith('+'):
                user_phone = '+' + user_phone
            user_phone = f'whatsapp:{user_phone}'
        
        message = client.messages.create(
            body=f'✅ Prueba de configuración exitosa desde {config.sitio_nombre}\n'
                 f'Universidad: {config.nombre_completo}\n'
                 f'Fecha: {datetime.now().strftime("%d/%m/%Y %H:%M")}\n\n'
                 f'Si recibiste este mensaje, la configuración es correcta.',
            from_=config.twilio_whatsapp_number,
            to=user_phone
        )
        
        return {'success': True, 'sid': message.sid}
    except Exception as e:
        logger.error(f"Error en prueba de WhatsApp: {str(e)}")
        return {'success': False, 'error': str(e)}


def _clear_config_cache():
    """Limpia todas las cachés relacionadas con configuración."""
    try:
        cache.delete('configuracion_sistema_activa')
        cache.delete_pattern('config_*')
        cache.delete_pattern('universidad_*')
        cache.delete_pattern('*configuracion*')
        logger.info("Caché de configuración limpiada exitosamente")
    except Exception as e:
        logger.error(f"Error al limpiar caché: {str(e)}")


def _log_config_change(user, config, action):
    """Registra cambios de configuración en el sistema de auditoría."""
    try:
        from ..models import Auditoria
        
        Auditoria.objects.create(
            usuario=user,
            accion=f"Configuración {action}",
            tipo='actualizacion',
            tabla_afectada='configuracion_sistema',
            registro_afectado=config.id,
            detalles={
                'universidad_id': config.idUniversidad_id if config.idUniversidad else None,
                'sitio_nombre': config.sitio_nombre,
                'sitio_url': config.sitio_url,
                'email_host_user': config.email_host_user,
                'twilio_enabled': config.twilio_enabled,
                'session_timeout_minutes': config.session_timeout_minutes,
                'require_https': config.require_https,
                'updated_at': datetime.now().isoformat(),
            }
        )
    except Exception as e:
        logger.error(f"Error al registrar auditoría: {str(e)}")


# ============================================
# VISTAS DE COMPATIBILIDAD (LEGACY)
# ============================================

@login_required
def configuracion_universidad(request):
    """
    Vista de compatibilidad - Redirige a configuracion_sistema.
    """
    return redirect('configuracion_sistema')


@login_required
def configuracion_universidad_editar(request):
    """
    Vista de compatibilidad - Redirige a configuracion_sistema.
    """
    return redirect('configuracion_sistema')


@login_required
def configuracion_reset_cache(request):
    """
    Reiniciar la caché de configuración.
    """
    if request.user.rol != 'admin' and not request.user.is_superuser:
        messages.error(request, "No tienes permiso para realizar esta acción.")
        return redirect('dashboard')
    
    _clear_config_cache()
    messages.success(request, "✅ Caché de configuración reiniciada exitosamente.")
    return redirect('configuracion_sistema')


@login_required
def configuracion_universidad_exportar(request):
    """
    Exportar la configuración completa.
    """
    if request.user.rol != 'admin' and not request.user.is_superuser:
        messages.error(request, "No tienes permiso para exportar la configuración.")
        return redirect('dashboard')
    
    universidad_id = get_universidad_id(request)
    config = ConfiguracionSistema.objects.filter(idUniversidad_id=universidad_id).first()
    
    if not config:
        messages.error(request, "No hay configuración para exportar.")
        return redirect('configuracion_sistema')
    
    data = {
        'universidad_id': universidad_id,
        'fecha_exportacion': datetime.now().isoformat(),
        'configuracion': {
            'sitio_nombre': config.sitio_nombre,
            'sitio_url': config.sitio_url,
            'sitio_descripcion': config.sitio_descripcion,
            'nombre_completo': config.nombre_completo,
            'siglas': config.siglas,
            'telefono': config.telefono,
            'email_contacto': config.email_contacto,
            'direccion': config.direccion,
            'sitio_web': config.sitio_web,
            'fecha_fundacion': str(config.fecha_fundacion) if config.fecha_fundacion else None,
            'rector': config.rector,
            'mision': config.mision,
            'vision': config.vision,
            'valores': config.valores,
            'email_host': config.email_host,
            'email_port': config.email_port,
            'email_use_tls': config.email_use_tls,
            'email_host_user': config.email_host_user,
            'twilio_enabled': config.twilio_enabled,
            'session_timeout_minutes': config.session_timeout_minutes,
            'limite_intentos_login': config.limite_intentos_login,
            'require_https': config.require_https,
            'allowed_hosts': config.allowed_hosts,
            'notificaciones_email': config.notificaciones_email,
            'notificaciones_whatsapp': config.notificaciones_whatsapp,
            'color_primario': config.color_primario,
            'color_secundario': config.color_secundario,
            'color_fondo': config.color_fondo,
            'mostrar_estadisticas': config.mostrar_estadisticas,
            'cache_timeout': config.cache_timeout,
            'cache_max_entries': config.cache_max_entries,
            'mante_sistema': config.mante_sistema,
            'permite_registro': config.permite_registro,
        },
    }
    
    response = HttpResponse(
        json.dumps(data, indent=2, ensure_ascii=False),
        content_type='application/json'
    )
    filename = f"configuracion_completa_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response


@login_required
def configuracion_test_email(request):
    """
    API para probar configuración de email vía AJAX.
    """
    if request.user.rol != 'admin' and not request.user.is_superuser:
        return JsonResponse({'error': 'No autorizado'}, status=403)
    
    universidad_id = get_universidad_id(request)
    config = ConfiguracionSistema.objects.filter(idUniversidad_id=universidad_id).first()
    
    if not config:
        return JsonResponse({'error': 'Configuración no encontrada'}, status=404)
    
    if not config.email_host_user or not config.email_host_password:
        return JsonResponse({'error': 'Credenciales de email no configuradas'}, status=400)
    
    result = _test_email_configuration(config, request)
    
    if result['success']:
        return JsonResponse({'success': True, 'message': 'Email de prueba enviado exitosamente'})
    else:
        return JsonResponse({'success': False, 'error': result['error']}, status=500)


@login_required
def configuracion_test_whatsapp(request):
    """
    API para probar configuración de WhatsApp vía AJAX.
    """
    if request.user.rol != 'admin' and not request.user.is_superuser:
        return JsonResponse({'error': 'No autorizado'}, status=403)
    
    universidad_id = get_universidad_id(request)
    config = ConfiguracionSistema.objects.filter(idUniversidad_id=universidad_id).first()
    
    if not config:
        return JsonResponse({'error': 'Configuración no encontrada'}, status=404)
    
    result = _test_whatsapp_configuration(config, request)
    
    if result['success']:
        return JsonResponse({'success': True, 'message': 'Mensaje de WhatsApp enviado exitosamente'})
    else:
        return JsonResponse({'success': False, 'error': result['error']}, status=500)


@login_required
def configuracion_importar(request):
    """
    Importar configuración desde archivo JSON.
    """
    if request.user.rol != 'admin' and not request.user.is_superuser:
        messages.error(request, "No tienes permiso para importar configuración.")
        return redirect('dashboard')
    
    if request.method == 'POST' and request.FILES.get('archivo_config'):
        try:
            archivo = request.FILES['archivo_config']
            data = json.loads(archivo.read().decode('utf-8'))
            
            universidad_id = get_universidad_id(request)
            config, _ = ConfiguracionSistema.objects.get_or_create(
                idUniversidad_id=universidad_id
            )
            
            for key, value in data.get('configuracion', {}).items():
                if hasattr(config, key):
                    setattr(config, key, value)
            
            config.actualizado_por = request.user
            config.save()
            
            _clear_config_cache()
            messages.success(request, "✅ Configuración importada exitosamente.")
            
        except json.JSONDecodeError:
            messages.error(request, "Error: El archivo no es un JSON válido.")
        except Exception as e:
            messages.error(request, f"Error al importar configuración: {str(e)}")
    
    return redirect('configuracion_sistema')


@login_required
def configuracion_restaurar_default(request):
    """
    Restaurar configuración a valores por defecto.
    """
    if request.user.rol != 'admin' and not request.user.is_superuser:
        messages.error(request, "No tienes permiso para restaurar la configuración.")
        return redirect('dashboard')
    
    if request.method == 'POST':
        try:
            universidad_id = get_universidad_id(request)
            config, _ = ConfiguracionSistema.objects.get_or_create(
                idUniversidad_id=universidad_id
            )
            
            # Restaurar valores por defecto
            config.sitio_nombre = 'RetenScan'
            config.sitio_url = 'http://localhost:8000'
            config.sitio_descripcion = ''
            config.nombre_completo = config.idUniversidad.nombre if config.idUniversidad else ''
            config.siglas = ''
            config.email_host = 'smtp.gmail.com'
            config.email_port = 587
            config.email_use_tls = True
            config.email_host_user = ''
            config.email_host_password = ''
            config.twilio_enabled = False
            config.session_timeout_minutes = 240
            config.limite_intentos_login = 5
            config.require_https = False
            config.allowed_hosts = 'localhost,127.0.0.1'
            config.notificaciones_email = True
            config.notificaciones_whatsapp = False
            config.color_primario = '#4e73df'
            config.color_secundario = '#1cc88a'
            config.color_fondo = '#f8f9fc'
            config.mostrar_estadisticas = True
            config.cache_timeout = 300
            config.cache_max_entries = 1000
            config.mante_sistema = False
            config.permite_registro = True
            
            config.actualizado_por = request.user
            config.save()
            
            _clear_config_cache()
            messages.success(request, "✅ Configuración restaurada a valores por defecto.")
            
        except Exception as e:
            messages.error(request, f"Error al restaurar configuración: {str(e)}")
    
    return redirect('configuracion_sistema')