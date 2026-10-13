# core/signals.py

from django.db.models.signals import post_save, post_delete, m2m_changed
from django.dispatch import receiver
from django.contrib.auth.hashers import make_password
from django.core.cache import cache
from django.utils import timezone
import logging
from .utils import generar_password_temporal
from .services.alert_service import AlertaService

logger = logging.getLogger(__name__)


# ============================================
# 1. SEÑAL PARA CREAR USUARIO DE ESTUDIANTE
# ============================================

@receiver(post_save, sender='core.Estudiante')
def crear_usuario_estudiante(sender, instance, created, **kwargs):
    """
    Señal que se ejecuta cuando se crea un estudiante.
    Crea el usuario automáticamente y envía credenciales.
    """
    if not created:
        return
    
    # ✅ Importar modelos aquí (no al inicio)
    from .models import Usuario
    from .views.base import generar_password_temporal
    
    # Si el estudiante ya tiene usuario, no hacer nada
    if instance.idUsuario:
        return
    
    # Crear usuario
    password_temporal = generar_password_temporal()
    username = instance.carnet.lower() if instance.carnet else f"estudiante_{instance.idEstudiante}"
    
    if Usuario.objects.filter(username=username).exists():
        username = f"{username}_{instance.idEstudiante}"
    
    try:
        usuario = Usuario.objects.create(
            username=username,
            email=instance.email if instance.email else f"{username}@example.com",
            first_name=instance.nombre,
            last_name=f"{instance.apellido_paterno} {instance.apellido_materno}".strip(),
            password=make_password(password_temporal),
            rol='estudiante',
            is_active=True,
            carnet=instance.carnet,
            genero=instance.genero,
            telefono=instance.telefono,
            fecha_nacimiento=instance.fecha_nacimiento,
            cambiar_password=True,
            notificaciones_email=True,
            whatsapp_telefono=instance.telefono or '',
            idUniversidad_id=instance.idUniversidad_id,
        )
        
        instance.idUsuario = usuario
        instance.save(update_fields=['idUsuario'])
        
        # ✅ Importar AlertaService aquí (no al inicio)
        try:
            from .services.alert_service import AlertaService
            AlertaService.notificar_credenciales(usuario, password_temporal, es_primera_vez=True)
            logger.info(f"✅ Credenciales enviadas para estudiante {instance.nombre_completo}")
        except ImportError as e:
            logger.warning(f"No se pudo importar AlertaService: {e}")
        except Exception as e:
            logger.error(f"Error enviando credenciales: {str(e)}")
            
    except Exception as e:
        logger.error(f"Error creando usuario para estudiante {instance.idEstudiante}: {str(e)}")


# ============================================
# 2. ⭐ SEÑAL PARA CREAR TUTOR AUTOMÁTICAMENTE
# ============================================

@receiver(post_save, sender='core.Usuario')
def crear_tutor_automatico(sender, instance, created, **kwargs):
    """
    ✅ Crea automáticamente un registro en Tutor cuando se crea 
    o se modifica un usuario con rol='tutor'.
    """
    if instance.rol != 'tutor':
        return
    
    from .models import Tutor
    
    tutor_existente = Tutor.objects.filter(usuario=instance).first()
    
    if not tutor_existente:
        try:
            tutor = Tutor.objects.create(
                usuario=instance,
                especialidad='Tutoría General',
                max_estudiantes=10,
                estudiantes_asignados=0,
                activo=True
            )
            logger.info(f"✅ Tutor creado automáticamente para: {instance.username}")
        except Exception as e:
            logger.error(f"❌ Error creando tutor para {instance.username}: {str(e)}")
    else:
        if not tutor_existente.activo:
            tutor_existente.activo = True
            tutor_existente.save(update_fields=['activo'])
            logger.info(f"✅ Tutor reactivado: {instance.username}")


# ============================================
# 3. ⭐ SEÑAL PARA CREAR SALA DE CHAT POR MATERIA
# ============================================

@receiver(post_save, sender='core.CatalogoMateria')
def crear_sala_chat_materia(sender, instance, created, **kwargs):
    """
    ✅ Crea automáticamente una SubjectChatRoom cuando se crea
    una CatalogoMateria.
    
    Esto asegura que cada materia tenga su canal de chat
    para estudiantes y profesores.
    """
    if not created:
        return
    
    try:
        # ✅ Importar aquí para evitar circular imports
        from chat.models import SubjectChatRoom
        
        # Código único de la sala
        codigo_chat = f"CHAT-{instance.codigo or instance.idMateria}"
        
        # Crear la sala
        room, room_created = SubjectChatRoom.objects.get_or_create(
            materia=instance,
            defaults={
                'name': f"Chat de {instance.nombre}",
                'code': codigo_chat,
                'is_active': True,
            }
        )
        
        if room_created:
            logger.info(f"✅ Sala de chat creada: {room.name} ({room.code})")
        else:
            logger.debug(f"ℹ️ Sala de chat ya existía: {room.name}")
            
    except ImportError:
        logger.debug("ℹ️ App 'chat' no disponible, saltando creación de sala")
    except Exception as e:
        logger.error(f"❌ Error creando sala de chat para materia {instance.nombre}: {e}")


# ============================================
# 4. SEÑALES PARA INVALIDAR CACHÉ DEL DASHBOARD
# ============================================

MODELOS_DASHBOARD = [
    'core.CatalogoMateria',
    'core.CatalogoCarrera',
    'core.CatalogoAula',
    'core.Beca',
    'core.Encuesta',
    'core.Tarea',
    'core.Estudiante',
    'core.Usuario',
    'core.Tutor',
    'core.AsignacionTutor',
    'core.Intervencion',
    'core.RiesgoEstudiante',
]


def invalidar_cache_dashboard(sender, instance, **kwargs):
    """Invalida el caché del dashboard cuando se modifican datos"""
    try:
        universidad_id = None
        
        # Intentar obtener universidad_id
        if hasattr(instance, 'idUniversidad_id') and instance.idUniversidad_id:
            universidad_id = instance.idUniversidad_id
        elif hasattr(instance, 'idUniversidad') and instance.idUniversidad:
            universidad_id = instance.idUniversidad.idUniversidad
        elif hasattr(instance, 'usuario') and instance.usuario:
            universidad_id = instance.usuario.idUniversidad_id
        elif hasattr(instance, 'estudiante') and instance.estudiante:
            universidad_id = instance.estudiante.idUniversidad_id
        
        fecha_actual = timezone.now().date()
        
        if universidad_id:
            claves = [
                f'dashboard_admin_{universidad_id}_{fecha_actual}',
                f'dashboard_admin_graficos_{universidad_id}_{fecha_actual}',
                f'dashboard_profesor_{universidad_id}_{fecha_actual}',
                f'dashboard_tutor_{universidad_id}_{fecha_actual}',
                f'dashboard_estudiante_{universidad_id}_{fecha_actual}',
            ]
            for clave in claves:
                cache.delete(clave)
            logger.debug(f"🗑️ Caché invalidado para universidad {universidad_id}")
        else:
            # Borrar todas las claves de caché del dashboard
            try:
                cache.delete_pattern('dashboard_*')
                logger.debug("🗑️ Caché de todos los dashboards invalidado")
            except AttributeError:
                # LocMemCache no soporta delete_pattern
                logger.debug("ℹ️ delete_pattern no disponible en este backend de caché")
            
    except Exception as e:
        logger.error(f"Error invalidando caché: {e}")


# ============================================
# 5. SEÑAL ESPECIAL PARA ASIGNACIONTUTOR
# ============================================

@receiver(post_save, sender='core.AsignacionTutor')
@receiver(post_delete, sender='core.AsignacionTutor')
def invalidar_cache_asignacion_tutor(sender, instance, **kwargs):
    """Invalida el caché cuando se crea, actualiza o elimina una asignación de tutor"""
    universidad_id = None
    
    if hasattr(instance, 'tutor') and instance.tutor:
        if hasattr(instance.tutor, 'usuario') and instance.tutor.usuario:
            universidad_id = instance.tutor.usuario.idUniversidad_id
    elif hasattr(instance, 'estudiante') and instance.estudiante:
        universidad_id = instance.estudiante.idUniversidad_id
    
    if universidad_id:
        fecha_actual = timezone.now().date()
        cache.delete(f'dashboard_profesor_{universidad_id}_{fecha_actual}')
        cache.delete(f'dashboard_tutor_{universidad_id}_{fecha_actual}')
        logger.debug(f"🗑️ Caché invalidado por cambio en AsignacionTutor para universidad {universidad_id}")


# ============================================
# 6. SEÑAL PARA CUANDO SE CREA UN TUTOR
# ============================================

@receiver(post_save, sender='core.Tutor')
def invalidar_cache_tutor_creado(sender, instance, created, **kwargs):
    """Invalida el caché cuando se crea un nuevo tutor"""
    if created:
        universidad_id = instance.usuario.idUniversidad_id
        if universidad_id:
            fecha_actual = timezone.now().date()
            cache.delete(f'dashboard_profesor_{universidad_id}_{fecha_actual}')
            cache.delete(f'dashboard_admin_{universidad_id}_{fecha_actual}')
            logger.debug(f"🗑️ Caché invalidado por creación de tutor: {instance.usuario.username}")


# ============================================
# 7. SEÑAL PARA CUANDO SE CREA UN ESTUDIANTE
# ============================================

@receiver(post_save, sender='core.Estudiante')
def invalidar_cache_estudiante_creado(sender, instance, created, **kwargs):
    """Invalida el caché cuando se crea un nuevo estudiante"""
    if created:
        universidad_id = instance.idUniversidad_id
        if universidad_id:
            fecha_actual = timezone.now().date()
            cache.delete(f'dashboard_admin_{universidad_id}_{fecha_actual}')
            cache.delete(f'dashboard_profesor_{universidad_id}_{fecha_actual}')
            cache.delete(f'dashboard_tutor_{universidad_id}_{fecha_actual}')
            logger.debug(f"🗑️ Caché invalidado por creación de estudiante: {instance.nombre_completo}")


# ============================================
# 8. SEÑAL PARA CUANDO SE CREA UN USUARIO
# ============================================

@receiver(post_save, sender='core.Usuario')
def invalidar_cache_usuario_creado(sender, instance, created, **kwargs):
    """Invalida el caché cuando se crea un nuevo usuario"""
    if created:
        universidad_id = instance.idUniversidad_id
        if universidad_id:
            fecha_actual = timezone.now().date()
            cache.delete(f'dashboard_admin_{universidad_id}_{fecha_actual}')
            logger.debug(f"🗑️ Caché invalidado por creación de usuario: {instance.username}")


# ============================================
# 9. REGISTRAR TODAS LAS SEÑALES
# ============================================

def registrar_senales_dashboard():
    """
    Registra las señales para todos los modelos del dashboard.
    Se ejecuta cuando la aplicación está lista.
    """
    from django.apps import apps
    
    for modelo_nombre in MODELOS_DASHBOARD:
        try:
            modelo = apps.get_model(modelo_nombre)
            
            # Post-save (creación y actualización)
            post_save.connect(
                invalidar_cache_dashboard,
                sender=modelo,
                dispatch_uid=f"invalidar_cache_{modelo_nombre.replace('.', '_')}_post_save",
                weak=False
            )
            
            # Post-delete (eliminación)
            post_delete.connect(
                invalidar_cache_dashboard,
                sender=modelo,
                dispatch_uid=f"invalidar_cache_{modelo_nombre.replace('.', '_')}_post_delete",
                weak=False
            )
            
            logger.debug(f"✅ Señales registradas para {modelo_nombre}")
            
        except LookupError:
            logger.warning(f"⚠️ Modelo no encontrado: {modelo_nombre}")
        except Exception as e:
            logger.error(f"❌ Error registrando señales para {modelo_nombre}: {e}")


def register_signals():
    """
    Registra todas las señales del sistema.
    Se llama desde apps.py cuando la aplicación está lista.
    """
    registrar_senales_dashboard()
    logger.info("✅ Señales de core cargadas correctamente")


# Función de compatibilidad para apps.py
def register():
    """Alias para register_signals (compatibilidad)"""
    register_signals()