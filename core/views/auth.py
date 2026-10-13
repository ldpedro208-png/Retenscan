# core/views/auth.py
# ✅ VERSIÓN CORREGIDA

"""
Vistas de autenticación y sesiones
"""

from django.contrib.auth.decorators import login_required
from django.contrib.auth import login, authenticate, logout
from django.contrib.auth.forms import AuthenticationForm, PasswordChangeForm
from django.contrib.auth.views import PasswordChangeView, PasswordChangeDoneView
from django.contrib.auth import update_session_auth_hash
from django.contrib import messages
from django.shortcuts import render, redirect
from django.core.cache import cache
from django.contrib.sessions.models import Session
from django.urls import reverse_lazy
from django.http import HttpResponseRedirect
from django.utils import timezone

from ..models import Usuario
from ..middleware import SessionControlMiddleware

# ✅ CORREGIDO: Importar logger desde utils, NO desde base
from ..utils import logger


# ============================================
# LOGIN
# ============================================
def login_view(request):
    """
    Vista de login.
    ✅ Después del login, redirige según si debe cambiar contraseña.
    """
    if request.user.is_authenticated:
        if getattr(request.user, 'cambiar_password', False):
            return redirect('password_change')
        return redirect('dashboard')
    
    if request.method == 'POST':
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            username = form.cleaned_data.get('username')
            password = form.cleaned_data.get('password')
            user = authenticate(request, username=username, password=password)
            
            if user is not None:
                login(request, user)
                
                # ✅ Guardar datos de la sesión
                request.session['user_agent'] = request.META.get('HTTP_USER_AGENT', 'Desconocido')
                request.session['ip_address'] = _get_client_ip(request)
                request.session['login_time'] = timezone.now().isoformat()
                
                # ✅ Si debe cambiar contraseña, redirigir ahí primero
                if getattr(user, 'cambiar_password', False):
                    messages.warning(
                        request,
                        "⚠️ Por seguridad, debes cambiar tu contraseña temporal antes de continuar."
                    )
                    return redirect('password_change')
                
                messages.success(request, f"¡Bienvenido {user.get_full_name() or user.username}!")
                
                next_url = request.GET.get('next', 'dashboard')
                return redirect(next_url)
            else:
                messages.error(request, "Usuario o contraseña incorrectos.")
        else:
            messages.error(request, "Usuario o contraseña incorrectos.")
    else:
        form = AuthenticationForm()
    
    return render(request, 'registration/login.html', {'form': form})


def _get_client_ip(request):
    """Obtiene la IP real del cliente."""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0].strip()
    else:
        ip = request.META.get('REMOTE_ADDR', 'Desconocida')
    return ip


# ============================================
# LOGOUT
# ============================================
def logout_view(request):
    """Cerrar sesión."""
    if request.user.is_authenticated:
        username = request.user.username
        
        try:
            user_session_key = f'user_sessions_{request.user.id}'
            active_sessions = cache.get(user_session_key, [])
            current_session = request.session.session_key
            if current_session in active_sessions:
                active_sessions.remove(current_session)
                cache.set(user_session_key, active_sessions, 86400)
        except Exception as e:
            logger.warning(f"Error limpiando sesiones: {str(e)}")
        
        logout(request)
        messages.success(request, f"¡Hasta luego {username}!")
    
    return redirect('login')


# ============================================
# CAMBIAR CONTRASEÑA (Class-based view)
# ============================================
class CustomPasswordChangeView(PasswordChangeView):
    """
    Vista para cambiar contraseña.
    ✅ Desactiva el flag cambiar_password después del cambio exitoso.
    ✅ Actualiza la sesión para evitar que se cierre.
    """
    # ✅ CORREGIDO: Ruta correcta del template
    template_name = 'autenticacion/password_change.html'
    success_url = reverse_lazy('password_change_done')

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('login')
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['es_obligatorio'] = getattr(self.request.user, 'cambiar_password', False)
        context['titulo'] = (
            'Cambio de Contraseña Obligatorio' 
            if context['es_obligatorio'] 
            else 'Cambiar Contraseña'
        )
        return context

    def form_valid(self, form):
        # Actualizar sesión
        update_session_auth_hash(self.request, form.user)
        
        # ✅ Desactivar flag
        usuario = self.request.user
        usuario.cambiar_password = False
        usuario.save(update_fields=['cambiar_password'])
        
        logger.info(f"✅ Usuario @{usuario.username} cambió su contraseña exitosamente")
        
        messages.success(
            self.request,
            "✅ Contraseña cambiada exitosamente. Ya puedes navegar por el sistema."
        )
        
        return super().form_valid(form)


class CustomPasswordChangeDoneView(PasswordChangeDoneView):
    """Vista de confirmación de cambio de contraseña."""
    # ✅ CORREGIDO: Ruta correcta del template
    template_name = 'autenticacion/password_change_done.html'

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('login')
        return super().dispatch(request, *args, **kwargs)


# ============================================
# CAMBIAR CONTRASEÑA (Function-based view - alternativa)
# ============================================
@login_required
def password_change_view(request):
    """Cambiar contraseña del usuario (versión funcional)."""
    if request.method == 'POST':
        form = PasswordChangeForm(request.user, request.POST)
        if form.is_valid():
            user = form.save()
            
            update_session_auth_hash(request, user)
            
            # ✅ Desactivar flag
            user.cambiar_password = False
            user.save(update_fields=['cambiar_password'])
            
            logger.info(f"✅ Usuario @{user.username} cambió su contraseña")
            
            messages.success(request, "✅ Contraseña cambiada exitosamente.")
            return redirect('password_change_done')
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f"{field}: {error}")
    else:
        form = PasswordChangeForm(request.user)
    
    context = {
        'form': form,
        'es_obligatorio': getattr(request.user, 'cambiar_password', False),
    }
    # ✅ CORREGIDO: Ruta correcta del template
    return render(request, 'autenticacion/password_change.html', context)


# ============================================
# PREFERENCIAS DE NOTIFICACIÓN
# ============================================
@login_required
def preferencias_notificacion(request):
    """Configurar preferencias de notificación."""
    user_rol = getattr(request.user, 'rol', 'estudiante')

    if request.method == 'POST':
        notificaciones_email = request.POST.get('notificaciones_email') == 'on'
        notificaciones_whatsapp = request.POST.get('notificaciones_whatsapp') == 'on'
        whatsapp_telefono = request.POST.get('whatsapp_telefono', '').strip()

        usuario = request.user
        usuario.notificaciones_email = notificaciones_email
        usuario.notificaciones_whatsapp = notificaciones_whatsapp
        usuario.whatsapp_telefono = whatsapp_telefono if whatsapp_telefono else None
        usuario.save(update_fields=[
            'notificaciones_email',
            'notificaciones_whatsapp',
            'whatsapp_telefono'
        ])

        messages.success(request, "✅ Preferencias de notificación actualizadas.")
        return redirect('perfil')

    context = {
        'user_rol': user_rol,
        'user': request.user,
    }
    return render(request, 'core/preferencias_notificacion.html', context)


# ============================================
# SESIONES ACTIVAS
# ============================================
@login_required
def sesiones_activas(request):
    """Mostrar sesiones activas del usuario."""
    user_session_key = f'user_sessions_{request.user.id}'
    active_sessions = cache.get(user_session_key, [])
    
    sessions_info = []
    for session_key in active_sessions:
        try:
            session = Session.objects.get(session_key=session_key)
            session_data = session.get_decoded()
            
            sessions_info.append({
                'session_key': session_key,
                'user_agent': session_data.get('user_agent', 'Desconocido'),
                'ip_address': session_data.get('ip_address', 'Desconocida'),
                'login_time': session_data.get('login_time', ''),
                'last_activity': session.expire_date,
                'is_current': session_key == request.session.session_key,
            })
        except Session.DoesNotExist:
            pass
    
    max_sessions = SessionControlMiddleware.SESSION_LIMITS.get(
        getattr(request.user, 'rol', 'default'), 2
    )
    
    context = {
        'sessions': sessions_info,
        'total_sessions': len(sessions_info),
        'max_sessions': max_sessions,
        'rol': getattr(request.user, 'rol', 'default'),
    }
    
    return render(request, 'sessions/sesiones_activas.html', context)


# ============================================
# CERRAR SESIÓN REMOTA
# ============================================
@login_required
def cerrar_sesion_remota(request, session_key):
    """Cerrar una sesión remota específica."""
    user_session_key = f'user_sessions_{request.user.id}'
    active_sessions = cache.get(user_session_key, [])
    
    if session_key in active_sessions and session_key != request.session.session_key:
        try:
            Session.objects.get(session_key=session_key).delete()
            active_sessions.remove(session_key)
            cache.set(user_session_key, active_sessions, 86400)
            messages.success(request, "✅ Sesión remota cerrada exitosamente.")
        except Session.DoesNotExist:
            messages.error(request, "La sesión ya no existe.")
    else:
        messages.error(request, "No puedes cerrar esta sesión.")
    
    return redirect('sesiones_activas')


# ============================================
# CERRAR TODAS SESIONES REMOTAS
# ============================================
@login_required
def cerrar_todas_sesiones_remotas(request):
    """Cerrar todas las sesiones remotas (excepto la actual)."""
    current_session = request.session.session_key
    user_session_key = f'user_sessions_{request.user.id}'
    active_sessions = cache.get(user_session_key, [])
    
    sessions_to_remove = [s for s in active_sessions if s != current_session]
    
    count = 0
    for session_key in sessions_to_remove:
        try:
            Session.objects.get(session_key=session_key).delete()
            count += 1
        except Session.DoesNotExist:
            pass
    
    cache.set(user_session_key, [current_session], 86400)
    
    if count > 0:
        messages.success(request, f"✅ Se cerraron {count} sesiones remotas.")
    else:
        messages.info(request, "No había sesiones remotas activas.")
    
    return redirect('sesiones_activas')