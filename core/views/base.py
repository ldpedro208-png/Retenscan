# core/views/base.py
# ✅ VERSIÓN LIMPIA

"""
Funciones base y utilitarias para las vistas del sistema RetenScan
"""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Count, Avg, Q, Prefetch
from django.utils import timezone
from datetime import datetime, timedelta
from django.core.paginator import Paginator
from django.core.cache import cache
from django.contrib.auth.views import PasswordChangeView, PasswordChangeDoneView
from django.urls import reverse_lazy
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.hashers import make_password
from django.http import JsonResponse, HttpResponse

# ✅ CAMBIO: BecaEstudiante → Beca, BecaAsignacion
from ..models import (
    Estudiante,
    HistorialAcademico,
    Asistencia,
    RiesgoEstudiante,
    Intervencion,
    CatalogoFactorRiesgo,
    UsuarioEstudiantes,
    Encuesta,
    EncuestaAsignacion,
    EncuestaPregunta,
    EncuestaOpcion,
    EncuestaRespuesta,
    Tarea,
    TareaAsignacion,
    TareaPregunta,
    TareaOpcion,
    TareaRespuesta,
    Usuario,
    Mensaje,
    Reunion,
    Notificacion,
    CatalogoUniversidad,
    CatalogoCarrera,
    CatalogoMateria,
    CatalogoAula,
    CatalogoTipoBeca,
    Beca,
    BecaAsignacion,
)

# ✅ CAMBIO: BecaEstudianteForm → BecaAsignacionForm
from ..forms import (
    EstudianteForm,
    HistorialAcademicoForm,
    AsistenciaForm,
    BecaAsignacionForm,
    CargaMasivaEstudiantesForm
)

# ✅ IMPORTAR SOLO logger DESDE UTILS
from ..utils import logger

from ..decorators import cache_view, invalidate_cache

import random
import string
import logging
from typing import Optional
from decimal import Decimal

# ✅ Importación de reportlab
try:
    from reportlab.lib.pagesizes import letter, A4, landscape
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib import colors
    from reportlab.lib.units import inch, cm
    from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
    from io import BytesIO
    REPORTLAB_AVAILABLE = True
except ImportError:
    REPORTLAB_AVAILABLE = False

# ✅ EXPORTAR funciones y constantes
__all__ = [
    'REPORTLAB_AVAILABLE',
    'get_universidad_id',
    'get_universidad_nombre',
    'get_carreras_por_universidad',
    'filter_by_universidad',
    'get_estudiantes_por_usuario',
    '_get_estudiante_con_permisos',
    '_mostrar_resumen_carga',
    'obtener_usuarios_por_rol',
    'get_universidad_nombre_from_user',
    'get_universidad_id_from_user',
    'get_servicio_prediccion',
    'get_modelo_predictivo',
    'obtener_servicio_prediccion',
    'obtener_modelo_predictivo',
    'reset_servicio_prediccion',
    'reset_modelo_predictivo',
    'reset_all',
    'AIService',
    'mensaje_exito',
    'mensaje_error',
]

# ============================================
# FUNCIONES DE UNIVERSIDAD
# ============================================

def get_universidad_id(request):
    """
    Obtiene el ID de la universidad del usuario.
    Retorna None si el usuario es superusuario o no tiene universidad.
    """
    user = request.user

    # ✅ Si es superusuario, retorna None (acceso a todo)
    if user.is_superuser:
        return None

    # ✅ Verificar si el usuario tiene universidad directamente
    if hasattr(user, 'idUniversidad') and user.idUniversidad:
        return user.idUniversidad.idUniversidad

    # ✅ Verificar si es admin de universidad
    if hasattr(user, 'es_admin_universidad') and user.es_admin_universidad:
        if user.idUniversidad:
            return user.idUniversidad.idUniversidad

    # ✅ Verificar si tiene un perfil de estudiante
    if hasattr(user, 'estudiante') and user.estudiante:
        estudiante = user.estudiante
        if estudiante.idCarrera:
            if estudiante.idCarrera.idUniversidad:
                return estudiante.idCarrera.idUniversidad.idUniversidad

    # ✅ Buscar estudiante por si está relacionado de otra forma
    try:
        estudiante = Estudiante.objects.filter(idUsuario=user).first()
        if estudiante and estudiante.idCarrera:
            if estudiante.idCarrera.idUniversidad:
                return estudiante.idCarrera.idUniversidad.idUniversidad
    except Exception:
        pass

    # ✅ Si es admin y no tiene universidad, asignar la primera disponible
    if user.rol == 'admin':
        try:
            primera_universidad = CatalogoUniversidad.objects.first()
            if primera_universidad:
                user.idUniversidad = primera_universidad
                user.save(update_fields=['idUniversidad'])
                return primera_universidad.idUniversidad
        except Exception:
            pass

    # ✅ No se encontró universidad
    return None


def get_universidad_nombre(universidad_id):
    """Obtiene el nombre de una universidad por su ID."""
    if not universidad_id:
        return "Sin universidad"

    try:
        universidad = CatalogoUniversidad.objects.get(idUniversidad=universidad_id)
        return universidad.nombre
    except CatalogoUniversidad.DoesNotExist:
        return "Universidad no encontrada"


def get_carreras_por_universidad(universidad_id):
    """Obtiene todas las carreras de una universidad específica."""
    if not universidad_id:
        return CatalogoCarrera.objects.none()

    return CatalogoCarrera.objects.filter(
        idUniversidad_id=universidad_id
    ).order_by('nombre')


def filter_by_universidad(request, queryset, model_class):
    """Filtra un queryset por la universidad del usuario."""
    if request.user.is_superuser:
        return queryset

    universidad_id = get_universidad_id(request)
    if not universidad_id:
        return queryset.none()

    if hasattr(model_class, 'idUniversidad'):
        return queryset.filter(idUniversidad_id=universidad_id)
    elif hasattr(model_class, 'idCarrera') and hasattr(
        model_class._meta.get_field('idCarrera').related_model,
        'idUniversidad'
    ):
        return queryset.filter(idCarrera__idUniversidad_id=universidad_id)
    elif hasattr(model_class, 'idUsuario') and hasattr(
        model_class._meta.get_field('idUsuario').related_model,
        'idUniversidad'
    ):
        return queryset.filter(idUsuario__idUniversidad_id=universidad_id)

    return queryset


# ============================================
# FUNCIONES DE ESTUDIANTES
# ============================================

def get_estudiantes_por_usuario(request, include_all: bool = False):
    """Obtiene los estudiantes según el rol del usuario."""
    user_rol = getattr(request.user, 'rol', 'estudiante')
    universidad_id = get_universidad_id(request)

    if request.user.is_superuser:
        queryset = Estudiante.objects.select_related('idCarrera__idUniversidad')
    else:
        queryset = Estudiante.objects.filter(
            idCarrera__idUniversidad_id=universidad_id
        ).select_related('idCarrera__idUniversidad')

    if user_rol == 'admin' or include_all:
        return queryset
    elif user_rol == 'tutor':
        estudiantes_asignados = UsuarioEstudiantes.objects.filter(
            usuario_id=request.user.id
        ).values_list('estudiante_id', flat=True)
        return queryset.filter(idEstudiante__in=estudiantes_asignados)
    elif user_rol == 'estudiante':
        try:
            estudiante = Estudiante.objects.get(idUsuario=request.user.id)
            return queryset.filter(idEstudiante=estudiante.idEstudiante)
        except Estudiante.DoesNotExist:
            return Estudiante.objects.none()

    return queryset


def _get_estudiante_con_permisos(pk, user_rol, universidad_id, user):
    """Obtiene un estudiante verificando permisos."""
    try:
        if user.is_superuser:
            return get_object_or_404(
                Estudiante.objects.select_related('idCarrera__idUniversidad', 'idUsuario'),
                pk=pk
            )
        elif user_rol == 'tutor':
            estudiante = get_object_or_404(
                Estudiante.objects.select_related('idCarrera__idUniversidad', 'idUsuario'),
                pk=pk,
                idCarrera__idUniversidad_id=universidad_id
            )
            es_asignado = UsuarioEstudiantes.objects.filter(
                usuario_id=user.id,
                estudiante_id=estudiante.idEstudiante
            ).exists()
            if not es_asignado:
                messages.error(user, "No tienes permiso para ver este estudiante.")
                return None
            return estudiante
        else:
            return get_object_or_404(
                Estudiante.objects.select_related('idCarrera__idUniversidad', 'idUsuario'),
                pk=pk,
                idCarrera__idUniversidad_id=universidad_id
            )
    except Estudiante.DoesNotExist:
        messages.error(user, "Estudiante no encontrado.")
        return None


# ============================================
# FUNCIONES DE RESPUESTA
# ============================================

def _mostrar_resumen_carga(request, resumen):
    """Muestra los mensajes de resumen de carga."""
    if resumen['exitos'] > 0:
        messages.success(request, f"✅ {resumen['exitos']} estudiantes creados exitosamente.")
    if resumen['actualizados'] > 0:
        messages.info(request, f"🔄 {resumen['actualizados']} estudiantes actualizados.")
    if resumen['advertencias']:
        for adv in resumen['advertencias'][:5]:
            messages.warning(request, f"⚠️ {adv}")
        if len(resumen['advertencias']) > 5:
            messages.warning(request, f"⚠️ Y {len(resumen['advertencias']) - 5} advertencias más.")
    if resumen['errores']:
        for err in resumen['errores'][:5]:
            messages.error(request, f"❌ {err}")
        if len(resumen['errores']) > 5:
            messages.error(request, f"❌ Y {len(resumen['errores']) - 5} errores más.")


# ============================================
# FUNCIONES AUXILIARES
# ============================================

def obtener_usuarios_por_rol(user_rol, universidad_id, exclude_user=None):
    """
    Obtiene usuarios según el rol y universidad.

    Args:
        user_rol: Rol del usuario que hace la consulta ('admin', 'tutor', etc.)
        universidad_id: ID de la universidad
        exclude_user: Usuario a excluir de la lista (opcional)

    Returns:
        QuerySet de Usuario
    """
    from ..models import Usuario, UsuarioEstudiantes

    if user_rol == 'tutor':
        estudiantes_asignados = UsuarioEstudiantes.objects.filter(
            usuario_id=exclude_user.id if exclude_user else None
        ).values_list('estudiante_id', flat=True)

        usuarios = Usuario.objects.filter(
            estudiante__idEstudiante__in=estudiantes_asignados,
            rol='estudiante',
            idUniversidad_id=universidad_id
        ).select_related('idUniversidad')
    else:
        usuarios = Usuario.objects.filter(
            rol__in=['estudiante', 'tutor', 'profesor'],
            idUniversidad_id=universidad_id
        ).select_related('idUniversidad')

    if exclude_user:
        usuarios = usuarios.exclude(id=exclude_user.id)

    return usuarios


def mensaje_exito(request, accion, nombre, tipo="elemento"):
    """Genera un mensaje de éxito consistente."""
    messages.success(request, f"✅ {tipo.title()} '{nombre}' {accion} exitosamente.")


def mensaje_error(request, mensaje_texto):
    """Genera un mensaje de error consistente."""
    messages.error(request, f"❌ {mensaje_texto}")


def get_universidad_nombre_from_user(user):
    """Obtiene el nombre de la universidad del usuario."""
    universidad_id = None

    if hasattr(user, 'idUniversidad') and user.idUniversidad:
        universidad_id = user.idUniversidad.idUniversidad
    elif hasattr(user, 'estudiante') and user.estudiante:
        estudiante = user.estudiante
        if estudiante.idCarrera:
            universidad_id = estudiante.idCarrera.idUniversidad.idUniversidad

    if universidad_id:
        try:
            universidad = CatalogoUniversidad.objects.get(idUniversidad=universidad_id)
            return universidad.nombre
        except CatalogoUniversidad.DoesNotExist:
            pass

    return "Sin universidad"


def get_universidad_id_from_user(user):
    """Obtiene el ID de la universidad del usuario."""
    if hasattr(user, 'idUniversidad') and user.idUniversidad:
        return user.idUniversidad.idUniversidad
    elif hasattr(user, 'estudiante') and user.estudiante:
        estudiante = user.estudiante
        if estudiante.idCarrera:
            return estudiante.idCarrera.idUniversidad.idUniversidad
    return None


# ============================================
# ✅ SERVICIOS DE IA (unificados)
# ============================================
# Los servicios de IA viven en `core.services.ai_service`.
# Ahí está la caché compartida, el threading.Lock y los métodos de reset.
#
# Este bloque re-exporta las funciones para mantener compatibilidad
# con el código existente que las importa desde `views.base`.

from ..services.ai_service import (
    get_servicio_prediccion,
    get_modelo_predictivo,
    obtener_servicio_prediccion,
    obtener_modelo_predictivo,
    reset_servicio_prediccion,
    reset_modelo_predictivo,
    reset_all,
    AIService,
)


# ============================================
# RE-EXPORTAR DESDE UTILS (compatibilidad)
# ============================================
from ..utils import (
    logger,
    generar_password_temporal,
    generar_username_desde_nombre,
    parse_decimal,
    formatear_fecha_mensaje,
)