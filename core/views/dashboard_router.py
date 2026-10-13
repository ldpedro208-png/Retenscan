# core/views/dashboard_router.py  (NUEVO ARCHIVO)

"""
Router del dashboard - Redirige según el rol del usuario
"""
from django.shortcuts import redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages

from .dashboard import DASHBOARD_MAP


@login_required
def dashboard(request):
    """
    Dashboard principal que redirige según el rol del usuario.
    """
    user_rol = getattr(request.user, 'rol', 'estudiante')
    
    dashboard_func = DASHBOARD_MAP.get(user_rol)
    
    if dashboard_func:
        return dashboard_func(request)
    else:
        messages.warning(request, f"Rol '{user_rol}' no reconocido. Usando dashboard de estudiante.")
        return DASHBOARD_MAP['estudiante'](request)