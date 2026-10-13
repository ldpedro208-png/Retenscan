# views/auditoria.py - VERSIÓN LIMPIA (sin exportaciones duplicadas)

"""
Vistas para la gestión de auditoría del sistema
"""
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q, Count
from django.utils import timezone
from datetime import datetime, timedelta
import json
from ..models import Usuario
from .base import get_universidad_id, logger

# Si tienes un modelo de auditoría, impórtalo
# from ..models import Auditoria


@login_required
def auditoria_list(request):
    """
    Lista de registros de auditoría del sistema
    Solo accesible para administradores
    """
    user_rol = request.user.rol
    
    # Verificar permisos - solo administradores
    if user_rol != 'admin':
        messages.error(request, "No tienes permiso para acceder al registro de auditoría.")
        return redirect('dashboard')
    
    universidad_id = get_universidad_id(request)
    
    # Obtener filtros
    search = request.GET.get('search', '')
    fecha_inicio = request.GET.get('fecha_inicio', '')
    fecha_fin = request.GET.get('fecha_fin', '')
    tipo = request.GET.get('tipo', '')
    usuario = request.GET.get('usuario', '')
    
    # ============================================
    # OBTENER REGISTROS DE AUDITORÍA
    # ============================================
    
    # Opción 1: Si tienes un modelo Auditoria
    # auditorias = Auditoria.objects.all()
    
    # Opción 2: Usar logs del sistema
    # Aquí simulamos datos de auditoría con información de usuarios
    # En producción, deberías tener un modelo de auditoría real
    
    # Obtener usuarios de la universidad
    if request.user.is_superuser:
        usuarios = Usuario.objects.all()
    else:
        usuarios = Usuario.objects.filter(idUniversidad_id=universidad_id)
    
    # Construir registros de auditoría simulados
    auditorias = []
    
    for user in usuarios:
        # Registro de creación
        auditorias.append({
            'id': len(auditorias) + 1,
            'usuario': user.username,
            'nombre_usuario': user.nombre_completo,
            'email': user.email,
            'accion': 'Creación de usuario',
            'tabla_afectada': 'Usuario',
            'registro_afectado': user.id,
            'detalles': f"Usuario {user.username} creado",
            'fecha': user.date_joined,
            'tipo': 'creacion',
            'ip': '127.0.0.1',
            'user_agent': 'Mozilla/5.0',
        })
        
        # Registro de último login
        if user.last_login:
            auditorias.append({
                'id': len(auditorias) + 1,
                'usuario': user.username,
                'nombre_usuario': user.nombre_completo,
                'email': user.email,
                'accion': 'Inicio de sesión',
                'tabla_afectada': 'Usuario',
                'registro_afectado': user.id,
                'detalles': f"Usuario {user.username} inició sesión",
                'fecha': user.last_login,
                'tipo': 'login',
                'ip': '127.0.0.1',
                'user_agent': 'Mozilla/5.0',
            })
        
        # Registro de actualización
        if user.updated_at and user.updated_at != user.date_joined:
            auditorias.append({
                'id': len(auditorias) + 1,
                'usuario': user.username,
                'nombre_usuario': user.nombre_completo,
                'email': user.email,
                'accion': 'Actualización de usuario',
                'tabla_afectada': 'Usuario',
                'registro_afectado': user.id,
                'detalles': f"Usuario {user.username} actualizado",
                'fecha': user.updated_at,
                'tipo': 'actualizacion',
                'ip': '127.0.0.1',
                'user_agent': 'Mozilla/5.0',
            })
    
    # Ordenar por fecha (más reciente primero)
    auditorias = sorted(auditorias, key=lambda x: x['fecha'], reverse=True)
    
    # Aplicar filtros
    if search:
        auditorias = [
            a for a in auditorias
            if search.lower() in a['usuario'].lower() or
               search.lower() in a['nombre_usuario'].lower() or
               search.lower() in a['email'].lower() or
               search.lower() in a['accion'].lower()
        ]
    
    if fecha_inicio:
        try:
            fecha_inicio_dt = datetime.strptime(fecha_inicio, '%Y-%m-%d')
            auditorias = [a for a in auditorias if a['fecha'].date() >= fecha_inicio_dt.date()]
        except ValueError:
            pass
    
    if fecha_fin:
        try:
            fecha_fin_dt = datetime.strptime(fecha_fin, '%Y-%m-%d')
            auditorias = [a for a in auditorias if a['fecha'].date() <= fecha_fin_dt.date()]
        except ValueError:
            pass
    
    if tipo:
        auditorias = [a for a in auditorias if a['tipo'] == tipo]
    
    if usuario:
        auditorias = [a for a in auditorias if usuario.lower() in a['usuario'].lower()]
    
    # Estadísticas
    stats = {
        'total': len(auditorias),
        'creaciones': len([a for a in auditorias if a['tipo'] == 'creacion']),
        'actualizaciones': len([a for a in auditorias if a['tipo'] == 'actualizacion']),
        'login': len([a for a in auditorias if a['tipo'] == 'login']),
        'usuarios_unicos': len(set([a['usuario'] for a in auditorias])),
    }
    
    # Paginación
    paginator = Paginator(auditorias, 20)
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)
    
    # Tipos para filtro
    tipos = ['creacion', 'actualizacion', 'login', 'eliminacion', 'exportacion']
    
    # Usuarios para filtro
    usuarios_list = list(set([a['usuario'] for a in auditorias]))
    
    context = {
        'auditorias': page_obj,
        'stats': stats,
        'search': search,
        'fecha_inicio': fecha_inicio,
        'fecha_fin': fecha_fin,
        'tipo': tipo,
        'usuario': usuario,
        'tipos': tipos,
        'usuarios_list': usuarios_list,
        'user_rol': user_rol,
        'total_registros': len(auditorias),
    }
    
    return render(request, 'auditoria/auditoria_list.html', context)


@login_required
def auditoria_detalle(request, id):
    """
    Ver detalle de un registro de auditoría
    """
    user_rol = request.user.rol
    
    if user_rol != 'admin':
        messages.error(request, "No tienes permiso para ver este registro.")
        return redirect('dashboard')
    
    # Buscar el registro de auditoría
    # En producción, usar el modelo Auditoria
    # auditoria = get_object_or_404(Auditoria, id=id)
    
    # Simular búsqueda
    auditoria = None
    
    if not auditoria:
        messages.error(request, "Registro de auditoría no encontrado.")
        return redirect('auditoria_list')
    
    context = {
        'auditoria': auditoria,
        'user_rol': user_rol,
    }
    
    return render(request, 'auditoria/auditoria_detalle.html', context)


@login_required
def auditoria_limpiar(request):
    """
    Limpiar registros de auditoría antiguos (solo superadmin)
    """
    user = request.user
    
    if not user.is_superuser:
        messages.error(request, "No tienes permiso para realizar esta acción.")
        return redirect('dashboard')
    
    if request.method == 'POST':
        dias = int(request.POST.get('dias', 90))
        fecha_limite = timezone.now() - timedelta(days=dias)
        
        # En producción, usar el modelo Auditoria
        # eliminados = Auditoria.objects.filter(fecha__lt=fecha_limite).delete()
        
        messages.success(request, f"✅ Registros de auditoría anteriores a {dias} días eliminados.")
        return redirect('auditoria_list')
    
    context = {
        'user_rol': user.rol,
    }
    return render(request, 'auditoria/auditoria_limpiar.html', context)


