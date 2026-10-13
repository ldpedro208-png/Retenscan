# core/views/dashboard/__init__.py

"""
Módulo de dashboards para el sistema RetenScan
Cada rol tiene su propio dashboard optimizado
"""

from django.shortcuts import render, redirect
from django.contrib import messages
from django.http import HttpResponse
import logging

from .admin import dashboard_admin
from .tutor import dashboard_tutor
from .profesor import dashboard_profesor
from .estudiante import dashboard_estudiante
from .asignacion_tutores import (
    asignacion_tutores_lista,
    asignacion_tutores_crear,
    asignacion_tutores_individual,
    asignacion_tutores_masiva,
    asignacion_tutores_confirmar,
    asignacion_tutores_cancelar,
    asignacion_tutores_estadisticas,
)

logger = logging.getLogger(__name__)

# ✅ Mapeo de roles a funciones de dashboard
DASHBOARD_MAP = {
    'admin': dashboard_admin,
    'tutor': dashboard_tutor,
    'profesor': dashboard_profesor,
    'estudiante': dashboard_estudiante,
}


# ✅ Función router que redirige según el rol
def dashboard(request):
    """
    Dashboard principal que redirige según el rol del usuario.
    Maneja correctamente superusuarios.
    """
    try:
        # ✅ Verificar autenticación
        if not request.user.is_authenticated:
            from django.urls import reverse
            return redirect(reverse('login'))

        # ✅ CASO 1: Superusuario → dashboard_admin
        if request.user.is_superuser:
            logger.info(f"Superusuario {request.user.username} → dashboard_admin")
            return dashboard_admin(request)

        # ✅ Obtener el rol de forma segura
        user_rol = getattr(request.user, 'rol', None)

        # ✅ Si no tiene rol, intentar inferirlo
        if not user_rol:
            # Intentar inferir rol por grupos o por tipo de usuario
            if request.user.groups.filter(name='admin').exists():
                user_rol = 'admin'
            elif request.user.groups.filter(name='tutor').exists():
                user_rol = 'tutor'
            elif request.user.groups.filter(name='profesor').exists():
                user_rol = 'profesor'
            else:
                user_rol = 'estudiante'

        # ✅ Buscar función de dashboard
        dashboard_func = DASHBOARD_MAP.get(user_rol)

        if dashboard_func:
            logger.info(f"Usuario {request.user.username} (rol={user_rol}) → dashboard_{user_rol}")
            response = dashboard_func(request)

            # ✅ Verificar que la respuesta es HttpResponse
            if isinstance(response, dict):
                logger.error(f"ERROR: La función {user_rol} retornó un diccionario")
                return render(request, 'layout/base.html', {
                    'error': 'Error en el dashboard',
                    'rol': user_rol
                })

            return response
        else:
            # ✅ Si el rol no existe, usar dashboard de estudiante
            logger.warning(f"Rol '{user_rol}' no reconocido. Usando dashboard de estudiante.")
            messages.warning(request, f"Rol '{user_rol}' no reconocido. Usando dashboard de estudiante.")
            response = DASHBOARD_MAP['estudiante'](request)

            if isinstance(response, dict):
                return render(request, 'estudiante/dashboard_estudiante.html', response)
            return response

    except Exception as e:
        logger.error(f"Error en dashboard router: {str(e)}")
        import traceback
        traceback.print_exc()

        context = {
            'error': str(e),
            'traceback': traceback.format_exc(),
            'rol': 'estudiante',
        }
        return render(request, 'layout/base.html', context)


# ✅ Exportar todo
__all__ = [
    'dashboard_admin',
    'dashboard_tutor',
    'dashboard_profesor',
    'dashboard_estudiante',
    'dashboard',
    'DASHBOARD_MAP',
    'asignacion_tutores_lista',
    'asignacion_tutores_crear',
    'asignacion_tutores_individual',
    'asignacion_tutores_masiva',
    'asignacion_tutores_confirmar',
    'asignacion_tutores_cancelar',
    'asignacion_tutores_estadisticas',
]