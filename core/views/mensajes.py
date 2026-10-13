# core/views/mensajes.py
# ✅ VERSIÓN CORREGIDA Y LIMPIA

"""
Vistas para la gestión de mensajes del sistema
Todos los usuarios pueden enviar y recibir mensajes.
"""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.db.models import Q
from django.utils import timezone
from django.http import JsonResponse, HttpResponseRedirect
from django.urls import reverse
from urllib.parse import urlencode
from django.db import transaction

from core.models import Mensaje, Usuario, UsuarioEstudiantes

# ✅ CORREGIDO: Separar importaciones
from .base import get_universidad_id, obtener_usuarios_por_rol
from ..utils import formatear_fecha_mensaje, logger


# ============================================
# CONSTANTES
# ============================================

MENSAJES_POR_PAGINA = 20
CACHE_TIMEOUT = 300  # 5 minutos


# ============================================
# FUNCIONES AUXILIARES
# ============================================

def obtener_destinatarios_disponibles(user, universidad_id, search=None):
    """Obtiene los destinatarios disponibles con búsqueda."""
    user_rol = getattr(user, 'rol', 'estudiante')
    
    # Obtener todos los usuarios de la misma universidad (excluyendo al usuario actual)
    destinatarios = Usuario.objects.filter(
        idUniversidad_id=universidad_id
    ).exclude(id=user.id).select_related('idUniversidad')
    
    # Si es superusuario, puede ver todos los usuarios
    if user.is_superuser:
        destinatarios = Usuario.objects.exclude(id=user.id).select_related('idUniversidad')
    
    # Búsqueda por nombre, username o email
    if search:
        destinatarios = destinatarios.filter(
            Q(username__icontains=search) |
            Q(first_name__icontains=search) |
            Q(last_name__icontains=search) |
            Q(email__icontains=search)
        )
    
    # Ordenar por nombre
    destinatarios = destinatarios.order_by('first_name', 'username')
    
    return destinatarios


def obtener_usuarios_contacto(user, universidad_id):
    """Obtiene los usuarios con los que el usuario ha tenido interacción."""
    # Mensajes enviados por el usuario
    enviados = Mensaje.objects.filter(
        remitente=user
    ).values_list('destinatario_id', flat=True).distinct()
    
    # Mensajes recibidos por el usuario
    recibidos = Mensaje.objects.filter(
        destinatario=user
    ).values_list('remitente_id', flat=True).distinct()
    
    # Unir ambas listas
    contactos_ids = set(list(enviados) + list(recibidos))
    
    if contactos_ids:
        contactos = Usuario.objects.filter(
            id__in=contactos_ids,
            idUniversidad_id=universidad_id
        ).select_related('idUniversidad').order_by('first_name', 'username')
    else:
        contactos = Usuario.objects.none()
    
    return contactos


# ============================================
# PROCESAR ENVÍO DE MENSAJES
# ============================================

@login_required
def procesar_envio_mensaje_multiple(request, universidad_id):
    """Procesa el envío de mensajes a múltiples destinatarios."""
    # Obtener datos del formulario
    destinatarios_raw = request.POST.get('destinatarios', '')
    asunto = request.POST.get('asunto', '').strip()
    contenido = request.POST.get('contenido', '').strip()
    enviar_a_todos = request.POST.get('enviar_a_todos', '') == 'on'
    
    # Procesar IDs de destinatarios
    destinatarios_ids = []
    if destinatarios_raw:
        if ',' in destinatarios_raw:
            destinatarios_ids = [id.strip() for id in destinatarios_raw.split(',') if id.strip()]
        else:
            destinatarios_ids = [destinatarios_raw]
    
    # Si es administrador y marcó "enviar a todos"
    if enviar_a_todos and (request.user.is_staff or request.user.is_superuser):
        if request.user.is_superuser:
            todos_usuarios = Usuario.objects.exclude(id=request.user.id)
        else:
            todos_usuarios = Usuario.objects.filter(
                idUniversidad_id=universidad_id
            ).exclude(id=request.user.id)
        
        destinatarios_ids = list(todos_usuarios.values_list('id', flat=True))
        messages.info(request, f"📢 Enviando mensaje a TODOS los usuarios ({len(destinatarios_ids)} destinatarios)")
    
    # Validaciones
    errores = []
    if not destinatarios_ids:
        errores.append("Debes seleccionar o escribir al menos un destinatario.")
    if not asunto:
        errores.append("El asunto es obligatorio.")
    if not contenido:
        errores.append("El contenido es obligatorio.")
    
    if errores:
        for error in errores:
            messages.error(request, f"❌ {error}")
        
        destinatarios = obtener_destinatarios_disponibles(request.user, universidad_id)
        contactos = obtener_usuarios_contacto(request.user, universidad_id)
        
        return render(request, 'mensaje/mensaje_create.html', {
            'destinatarios': destinatarios,
            'contactos': contactos,
            'user_rol': getattr(request.user, 'rol', 'estudiante'),
            'destinatarios_seleccionados': destinatarios_raw,
            'asunto': asunto,
            'contenido': contenido,
            'errores': errores,
        })
    
    # Verificar que los destinatarios existan y sean válidos
    destinatarios_validos = []
    for dest_id in destinatarios_ids:
        try:
            destinatario = Usuario.objects.get(pk=dest_id)
            if (destinatario.idUniversidad_id != universidad_id and 
                not request.user.is_superuser and 
                universidad_id is not None):
                continue
            if destinatario.id == request.user.id:
                continue
            destinatarios_validos.append(destinatario)
        except Usuario.DoesNotExist:
            continue
    
    if not destinatarios_validos:
        messages.error(request, "❌ No hay destinatarios válidos para enviar el mensaje.")
        return redirect('mensaje_create')
    
    # Crear mensajes
    try:
        mensajes_creados = []
        with transaction.atomic():
            for destinatario in destinatarios_validos:
                mensaje = Mensaje.objects.create(
                    remitente=request.user,
                    destinatario=destinatario,
                    asunto=asunto,
                    contenido=contenido
                )
                mensajes_creados.append(mensaje)
        
        cantidad = len(mensajes_creados)
        if enviar_a_todos:
            messages.success(request, f"✅ Mensaje enviado exitosamente a TODOS los usuarios ({cantidad} destinatarios).")
        else:
            nombres = ', '.join([d.get_full_name() or d.username for d in destinatarios_validos[:3]])
            if cantidad > 3:
                nombres += f' y {cantidad - 3} más'
            messages.success(request, f"✅ Mensaje enviado exitosamente a {cantidad} destinatario(s): {nombres}.")
        
        return redirect('mensaje_list')
        
    except Exception as e:
        logger.error(f"Error enviando mensajes múltiples: {str(e)}")
        messages.error(request, f"❌ Error al enviar los mensajes: {str(e)}")
        return redirect('mensaje_create')


# ============================================
# VISTAS PRINCIPALES
# ============================================

@login_required
def mensaje_create(request):
    """Vista para crear mensajes con envío múltiple."""
    universidad_id = get_universidad_id(request)
    
    # Obtener todos los destinatarios disponibles
    destinatarios = obtener_destinatarios_disponibles(request.user, universidad_id)
    
    # Obtener contactos frecuentes
    contactos = obtener_usuarios_contacto(request.user, universidad_id)
    
    # Pre-cargar datos desde GET
    destinatarios_predefinidos = request.GET.get('destinatarios', '')
    asunto_predefinido = request.GET.get('asunto', '')
    mensaje_original_id = request.GET.get('mensaje_id')
    
    # Si hay un mensaje original, marcarlo como leído
    if mensaje_original_id:
        try:
            mensaje_orig = Mensaje.objects.get(pk=mensaje_original_id)
            if mensaje_orig.destinatario == request.user and not mensaje_orig.leido:
                mensaje_orig.leido = True
                mensaje_orig.fecha_lectura = timezone.now()
                mensaje_orig.save()
                if not destinatarios_predefinidos:
                    destinatarios_predefinidos = str(mensaje_orig.remitente.id)
        except Mensaje.DoesNotExist:
            pass

    if request.method == 'POST':
        return procesar_envio_mensaje_multiple(request, universidad_id)

    context = {
        'destinatarios': destinatarios,
        'contactos': contactos,
        'user_rol': getattr(request.user, 'rol', 'estudiante'),
        'destinatarios_seleccionados': destinatarios_predefinidos,
        'asunto_predefinido': asunto_predefinido,
        'puede_enviar': True,
    }
    return render(request, 'mensaje/mensaje_create.html', context)


@login_required
def mensaje_list(request):
    """Lista de mensajes con paginación, búsqueda y filtros."""
    user_rol = getattr(request.user, 'rol', 'estudiante')

    # Obtener parámetros
    busqueda = request.GET.get('busqueda', '').strip()
    filtro = request.GET.get('filtro', 'todos')
    page = request.GET.get('page', 1)
    tipo = request.GET.get('tipo', 'recibidos')

    # ============================================
    # MENSAJES RECIBIDOS (solo los no eliminados)
    # ============================================
    recibidos = Mensaje.objects.filter(
        destinatario=request.user,
        eliminado_por_destinatario=False
    ).select_related('remitente', 'remitente__idUniversidad')
    
    if busqueda:
        recibidos = recibidos.filter(
            Q(asunto__icontains=busqueda) |
            Q(contenido__icontains=busqueda) |
            Q(remitente__username__icontains=busqueda) |
            Q(remitente__first_name__icontains=busqueda) |
            Q(remitente__last_name__icontains=busqueda)
        )
    
    if filtro == 'no_leidos':
        recibidos = recibidos.filter(leido=False)
    elif filtro == 'leidos':
        recibidos = recibidos.filter(leido=True)
    elif filtro == 'archivados':
        recibidos = recibidos.filter(archivado=True)
    
    recibidos = recibidos.order_by('-fecha_envio')
    
    # ============================================
    # MENSAJES ENVIADOS (solo los no eliminados)
    # ============================================
    enviados = Mensaje.objects.filter(
        remitente=request.user,
        eliminado_por_remitente=False
    ).select_related('destinatario', 'destinatario__idUniversidad')
    
    if busqueda:
        enviados = enviados.filter(
            Q(asunto__icontains=busqueda) |
            Q(contenido__icontains=busqueda) |
            Q(destinatario__username__icontains=busqueda) |
            Q(destinatario__first_name__icontains=busqueda) |
            Q(destinatario__last_name__icontains=busqueda)
        )
    
    if filtro == 'archivados':
        enviados = enviados.filter(archivado=True)
    
    enviados = enviados.order_by('-fecha_envio')
    
    # ============================================
    # TODOS LOS MENSAJES VISIBLES
    # ============================================
    todos = Mensaje.objects.filter(
        Q(remitente=request.user, eliminado_por_remitente=False) |
        Q(destinatario=request.user, eliminado_por_destinatario=False)
    ).select_related('remitente', 'destinatario', 'remitente__idUniversidad', 'destinatario__idUniversidad')
    
    if busqueda:
        todos = todos.filter(
            Q(asunto__icontains=busqueda) |
            Q(contenido__icontains=busqueda) |
            Q(remitente__username__icontains=busqueda) |
            Q(remitente__first_name__icontains=busqueda) |
            Q(remitente__last_name__icontains=busqueda) |
            Q(destinatario__username__icontains=busqueda) |
            Q(destinatario__first_name__icontains=busqueda) |
            Q(destinatario__last_name__icontains=busqueda)
        )
    
    if filtro == 'archivados':
        todos = todos.filter(archivado=True)
    
    todos = todos.order_by('-fecha_envio').distinct()
    
    # ============================================
    # SELECCIONAR QUERYSET
    # ============================================
    if tipo == 'recibidos':
        queryset = recibidos
    elif tipo == 'enviados':
        queryset = enviados
    else:
        queryset = todos
    
    # Contar no leídos (solo los visibles)
    no_leidos = Mensaje.objects.filter(
        destinatario=request.user,
        leido=False,
        eliminado_por_destinatario=False
    ).count()
    
    # Contar archivados (solo los visibles)
    archivados_count = Mensaje.objects.filter(
        destinatario=request.user,
        archivado=True,
        eliminado_por_destinatario=False
    ).count()
    
    # Paginación
    paginator = Paginator(queryset, MENSAJES_POR_PAGINA)
    try:
        mensajes_page = paginator.page(page)
    except PageNotAnInteger:
        mensajes_page = paginator.page(1)
    except EmptyPage:
        mensajes_page = paginator.page(paginator.num_pages)

    # ============================================
    # ESTADÍSTICAS (solo mensajes visibles)
    # ============================================
    stats = {
        'total_recibidos': Mensaje.objects.filter(
            destinatario=request.user,
            eliminado_por_destinatario=False
        ).count(),
        'total_enviados': Mensaje.objects.filter(
            remitente=request.user,
            eliminado_por_remitente=False
        ).count(),
        'no_leidos': no_leidos,
        'leidos': Mensaje.objects.filter(
            destinatario=request.user,
            leido=True,
            eliminado_por_destinatario=False
        ).count(),
        'archivados': archivados_count,
        'total_todos': Mensaje.objects.filter(
            Q(remitente=request.user, eliminado_por_remitente=False) |
            Q(destinatario=request.user, eliminado_por_destinatario=False)
        ).distinct().count(),
    }

    context = {
        'mensajes': mensajes_page,
        'no_leidos': no_leidos,
        'archivados_count': archivados_count,
        'user_rol': user_rol,
        'busqueda': busqueda,
        'filtro': filtro,
        'tipo': tipo,
        'stats': stats,
        'total_registros': queryset.count(),
        'formatear_fecha': formatear_fecha_mensaje,
        'user': request.user,
    }
    return render(request, 'mensaje/mensaje_list.html', context)


@login_required
def mensaje_detail(request, pk):
    """Ver detalle de un mensaje."""
    mensaje = get_object_or_404(
        Mensaje.objects.select_related('remitente', 'destinatario'),
        pk=pk
    )

    if mensaje.destinatario != request.user and mensaje.remitente != request.user:
        messages.error(request, "❌ No tienes permiso para ver este mensaje.")
        return redirect('mensaje_list')

    if mensaje.destinatario == request.user and not mensaje.leido:
        mensaje.leido = True
        mensaje.fecha_lectura = timezone.now()
        mensaje.save()

    context = {
        'mensaje': mensaje,
        'user_rol': getattr(request.user, 'rol', 'estudiante'),
        'formatear_fecha': formatear_fecha_mensaje,
        'puede_responder': mensaje.destinatario == request.user,
        'puede_editar': mensaje.remitente == request.user and not mensaje.leido,
        'puede_eliminar': mensaje.remitente == request.user,
    }
    return render(request, 'mensaje/mensaje_detail.html', context)


@login_required
def mensaje_responder(request, pk):
    """Redirige a la vista de enviar mensaje con el destinatario pre-cargado."""
    mensaje_original = get_object_or_404(Mensaje, pk=pk)
    
    if mensaje_original.destinatario != request.user:
        messages.error(request, "❌ No tienes permiso para responder a este mensaje.")
        return redirect('mensaje_list')
    
    url = reverse('mensaje_create')
    params = urlencode({
        'destinatario': mensaje_original.remitente.id,
        'asunto': f"Re: {mensaje_original.asunto}",
        'mensaje_id': mensaje_original.pk
    })
    
    return HttpResponseRedirect(f"{url}?{params}")


@login_required
def mensaje_delete(request, pk):
    """Elimina un mensaje SOLO para el usuario actual"""
    mensaje = get_object_or_404(Mensaje, pk=pk)
    
    if request.user != mensaje.remitente and request.user != mensaje.destinatario:
        messages.error(request, 'No tienes permiso para eliminar este mensaje.')
        return redirect('mensaje_list')
    
    if mensaje.esta_eliminado_para(request.user):
        messages.warning(request, 'Este mensaje ya fue eliminado.')
        return redirect('mensaje_list')
    
    if request.method == 'POST':
        mensaje.eliminar_para_usuario(request.user)
        
        if request.user == mensaje.remitente:
            messages.success(request, 'Mensaje eliminado de tus mensajes enviados.')
        else:
            messages.success(request, 'Mensaje eliminado de tu bandeja de entrada.')
        
        return redirect('mensaje_list')
    
    return render(request, 'mensaje/mensaje_confirm_delete.html', {
        'mensaje': mensaje,
        'es_remitente': request.user == mensaje.remitente,
    })


@login_required
def mensaje_restaurar(request, pk):
    """Restaura un mensaje eliminado para el usuario actual"""
    mensaje = get_object_or_404(Mensaje, pk=pk)
    
    if request.user != mensaje.remitente and request.user != mensaje.destinatario:
        messages.error(request, 'No tienes permiso para restaurar este mensaje.')
        return redirect('mensaje_list')
    
    if request.method == 'POST':
        mensaje.restaurar_para_usuario(request.user)
        messages.success(request, 'Mensaje restaurado correctamente.')
        return redirect('mensaje_list')
    
    return redirect('mensaje_list')


@login_required
def mensaje_papelera(request):
    """Muestra los mensajes eliminados por el usuario (papelera)"""
    mensajes_eliminados = Mensaje.objects.filter(
        Q(remitente=request.user, eliminado_por_remitente=True) |
        Q(destinatario=request.user, eliminado_por_destinatario=True)
    ).distinct()
    
    return render(request, 'mensaje/mensaje_papelera.html', {
        'mensajes': mensajes_eliminados,
    })


# ============================================
# ACCIONES INDIVIDUALES
# ============================================

@login_required
def mensaje_archivar(request, pk):
    """Archiva un mensaje (solo para destinatarios)."""
    mensaje = get_object_or_404(Mensaje, pk=pk)
    
    if mensaje.destinatario != request.user:
        messages.error(request, "❌ No tienes permiso para archivar este mensaje.")
        return redirect('mensaje_list')
    
    mensaje.archivado = True
    mensaje.carpeta = 'archivados'
    mensaje.save()
    messages.success(request, "✅ Mensaje archivado exitosamente.")
    
    referer = request.META.get('HTTP_REFERER')
    if referer:
        return redirect(referer)
    return redirect('mensaje_list')


@login_required
def mensaje_desarchivar(request, pk):
    """Desarchiva un mensaje (solo para destinatarios)."""
    mensaje = get_object_or_404(Mensaje, pk=pk)
    
    if mensaje.destinatario != request.user:
        messages.error(request, "❌ No tienes permiso para desarchivar este mensaje.")
        return redirect('mensaje_list')
    
    mensaje.archivado = False
    mensaje.carpeta = 'inbox'
    mensaje.save()
    messages.success(request, "✅ Mensaje desarchivado exitosamente.")
    
    referer = request.META.get('HTTP_REFERER')
    if referer:
        return redirect(referer)
    return redirect('mensaje_list')


@login_required
def mensaje_reenviar(request, pk):
    """Reenvía un mensaje a otro destinatario."""
    mensaje_original = get_object_or_404(Mensaje, pk=pk)
    
    if mensaje_original.destinatario != request.user and mensaje_original.remitente != request.user:
        messages.error(request, "❌ No tienes permiso para reenviar este mensaje.")
        return redirect('mensaje_list')
    
    url = reverse('mensaje_create')
    params = urlencode({
        'asunto': f"Reenvío: {mensaje_original.asunto}",
        'contenido': f"\n\n--- Mensaje original de {mensaje_original.remitente.get_full_name() or mensaje_original.remitente.username} ---\n{mensaje_original.contenido}"
    })
    
    return HttpResponseRedirect(f"{url}?{params}")


@login_required
def mensaje_mover(request, pk, carpeta):
    """Mueve un mensaje a una carpeta específica."""
    mensaje = get_object_or_404(Mensaje, pk=pk)
    
    if mensaje.destinatario != request.user:
        messages.error(request, "❌ No tienes permiso para mover este mensaje.")
        return redirect('mensaje_list')
    
    carpetas_validas = ['inbox', 'archivados', 'importante', 'trabajo', 'personal']
    
    if carpeta not in carpetas_validas:
        messages.error(request, "❌ Carpeta no válida.")
        return redirect('mensaje_list')
    
    mensaje.carpeta = carpeta
    mensaje.archivado = (carpeta == 'archivados')
    mensaje.save()
    
    messages.success(request, f"✅ Mensaje movido a la carpeta '{carpeta.title()}'.")
    
    referer = request.META.get('HTTP_REFERER')
    if referer:
        return redirect(referer)
    return redirect('mensaje_list')


# ============================================
# ACCIONES DE LECTURA
# ============================================

@login_required
def mensaje_toggle_leido(request, pk):
    """Marcar/desmarcar un mensaje como leído."""
    mensaje = get_object_or_404(Mensaje, pk=pk)
    
    if mensaje.destinatario != request.user:
        messages.error(request, "❌ No tienes permiso para modificar este mensaje.")
        return redirect('mensaje_list')
    
    mensaje.leido = not mensaje.leido
    
    if mensaje.leido:
        mensaje.fecha_lectura = timezone.now()
        estado = "leído"
    else:
        mensaje.fecha_lectura = None
        estado = "no leído"
    
    mensaje.save()
    messages.success(request, f"✅ Mensaje marcado como {estado}.")
    
    referer = request.META.get('HTTP_REFERER')
    if referer:
        return redirect(referer)
    return redirect('mensaje_detail', pk=mensaje.pk)


@login_required
def mensaje_marcar_leido(request, pk):
    """Marca un mensaje como leído."""
    mensaje = get_object_or_404(Mensaje, pk=pk)
    
    if mensaje.destinatario != request.user:
        messages.error(request, "❌ No tienes permiso para modificar este mensaje.")
        return redirect('mensaje_list')
    
    if not mensaje.leido:
        mensaje.leido = True
        mensaje.fecha_lectura = timezone.now()
        mensaje.save()
        messages.success(request, "✅ Mensaje marcado como leído.")
    
    return redirect('mensaje_detail', pk=mensaje.pk)


@login_required
def mensaje_marcar_no_leido(request, pk):
    """Marca un mensaje como no leído."""
    mensaje = get_object_or_404(Mensaje, pk=pk)
    
    if mensaje.destinatario != request.user:
        messages.error(request, "❌ No tienes permiso para modificar este mensaje.")
        return redirect('mensaje_list')
    
    if mensaje.leido:
        mensaje.leido = False
        mensaje.fecha_lectura = None
        mensaje.save()
        messages.success(request, "✅ Mensaje marcado como no leído.")
    
    return redirect('mensaje_detail', pk=mensaje.pk)


# ============================================
# ACCIONES MASIVAS
# ============================================

@login_required
def mensaje_marcar_todos_leidos(request):
    """Marca todos los mensajes del usuario como leídos."""
    if request.method != 'POST':
        messages.error(request, "❌ Método no permitido.")
        return redirect('mensaje_list')
    
    mensajes = Mensaje.objects.filter(
        destinatario=request.user,
        leido=False
    )
    
    cantidad = mensajes.count()
    
    if cantidad == 0:
        messages.info(request, "ℹ️ No tienes mensajes sin leer.")
    else:
        mensajes.update(leido=True, fecha_lectura=timezone.now())
        messages.success(request, f"✅ {cantidad} mensaje(s) marcado(s) como leídos.")
    
    return redirect('mensaje_list')


@login_required
def mensaje_marcar_seleccionados_leidos(request):
    """Marca los mensajes seleccionados como leídos."""
    if request.method != 'POST':
        messages.error(request, "❌ Método no permitido.")
        return redirect('mensaje_list')
    
    mensajes_ids = request.POST.getlist('mensajes_ids')
    if not mensajes_ids:
        messages.warning(request, "⚠️ No seleccionaste ningún mensaje.")
        return redirect('mensaje_list')
    
    mensajes = Mensaje.objects.filter(
        pk__in=mensajes_ids,
        destinatario=request.user,
        leido=False
    )
    
    cantidad = mensajes.count()
    
    if cantidad == 0:
        messages.info(request, "ℹ️ Los mensajes seleccionados ya estaban leídos.")
    else:
        mensajes.update(leido=True, fecha_lectura=timezone.now())
        messages.success(request, f"✅ {cantidad} mensaje(s) marcado(s) como leídos.")
    
    return redirect('mensaje_list')


@login_required
def mensaje_marcar_seleccionados_no_leidos(request):
    """Marca los mensajes seleccionados como no leídos."""
    if request.method != 'POST':
        messages.error(request, "❌ Método no permitido.")
        return redirect('mensaje_list')
    
    mensajes_ids = request.POST.get('mensajes_ids', '').split(',')
    mensajes_ids = [id.strip() for id in mensajes_ids if id.strip()]
    
    if not mensajes_ids:
        messages.warning(request, "⚠️ No seleccionaste ningún mensaje.")
        return redirect('mensaje_list')
    
    mensajes = Mensaje.objects.filter(
        pk__in=mensajes_ids,
        destinatario=request.user,
        leido=True
    )
    
    cantidad = mensajes.count()
    
    if cantidad == 0:
        messages.info(request, "ℹ️ Los mensajes seleccionados ya estaban no leídos.")
    else:
        mensajes.update(leido=False, fecha_lectura=None)
        messages.success(request, f"✅ {cantidad} mensaje(s) marcado(s) como no leídos.")
    
    return redirect('mensaje_list')


@login_required
def mensaje_archivar_seleccionados(request):
    """Archiva los mensajes seleccionados."""
    if request.method != 'POST':
        messages.error(request, "❌ Método no permitido.")
        return redirect('mensaje_list')
    
    mensajes_ids = request.POST.get('mensajes_ids', '').split(',')
    mensajes_ids = [id.strip() for id in mensajes_ids if id.strip()]
    
    if not mensajes_ids:
        messages.warning(request, "⚠️ No seleccionaste ningún mensaje.")
        return redirect('mensaje_list')
    
    mensajes = Mensaje.objects.filter(
        pk__in=mensajes_ids,
        destinatario=request.user,
        archivado=False
    )
    
    cantidad = mensajes.count()
    
    if cantidad == 0:
        messages.info(request, "ℹ️ Los mensajes seleccionados ya estaban archivados.")
    else:
        mensajes.update(archivado=True, carpeta='archivados')
        messages.success(request, f"✅ {cantidad} mensaje(s) archivado(s).")
    
    return redirect('mensaje_list')


@login_required
def mensaje_eliminar_seleccionados(request):
    """Elimina los mensajes seleccionados."""
    if request.method != 'POST':
        messages.error(request, "❌ Método no permitido.")
        return redirect('mensaje_list')
    
    mensajes_ids = request.POST.get('mensajes_ids', '').split(',')
    mensajes_ids = [id.strip() for id in mensajes_ids if id.strip()]
    
    if not mensajes_ids:
        messages.warning(request, "⚠️ No seleccionaste ningún mensaje.")
        return redirect('mensaje_list')
    
    mensajes = Mensaje.objects.filter(
        pk__in=mensajes_ids,
        remitente=request.user
    )
    
    cantidad = mensajes.count()
    
    if cantidad == 0:
        messages.info(request, "ℹ️ No se encontraron mensajes para eliminar.")
    else:
        mensajes.delete()
        messages.success(request, f"✅ {cantidad} mensaje(s) eliminado(s).")
    
    return redirect('mensaje_list')


# ============================================
# API PARA NOTIFICACIONES
# ============================================

@login_required
def mensaje_no_leidos_api(request):
    """API que retorna el número de mensajes no leídos del usuario."""
    if not request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({'error': 'Solicitud AJAX requerida'}, status=400)
    
    no_leidos = Mensaje.objects.filter(
        destinatario=request.user,
        leido=False
    ).count()
    
    ultimos = Mensaje.objects.filter(
        destinatario=request.user,
        leido=False
    ).select_related('remitente').order_by('-fecha_envio')[:5]
    
    ultimos_mensajes = []
    for msg in ultimos:
        nombre_remitente = msg.remitente.get_full_name() or msg.remitente.username
        ultimos_mensajes.append({
            'id': msg.pk,
            'remitente': nombre_remitente,
            'asunto': msg.asunto,
            'fecha': formatear_fecha_mensaje(msg.fecha_envio),
            'url': reverse('mensaje_detail', args=[msg.pk])
        })
    
    return JsonResponse({
        'success': True,
        'no_leidos': no_leidos,
        'tiene_no_leidos': no_leidos > 0,
        'ultimos': ultimos_mensajes
    })


@login_required
def mensaje_contador_api(request):
    """API simple que solo retorna el contador de mensajes no leídos."""
    if not request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({'error': 'Solicitud AJAX requerida'}, status=400)
    
    no_leidos = Mensaje.objects.filter(
        destinatario=request.user,
        leido=False
    ).count()
    
    return JsonResponse({
        'success': True,
        'no_leidos': no_leidos,
    })


@login_required
def api_buscar_usuarios(request):
    """API para buscar usuarios por nombre, email o username."""
    if not request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({'error': 'Solicitud AJAX requerida'}, status=400)
    
    query = request.GET.get('q', '').strip()
    universidad_id = get_universidad_id(request)
    
    if len(query) < 2:
        return JsonResponse({'results': []})
    
    usuarios = Usuario.objects.filter(
        Q(username__icontains=query) |
        Q(first_name__icontains=query) |
        Q(last_name__icontains=query) |
        Q(email__icontains=query)
    ).exclude(id=request.user.id)
    
    if not request.user.is_superuser and universidad_id:
        usuarios = usuarios.filter(idUniversidad_id=universidad_id)
    
    results = []
    for user in usuarios[:20]:
        results.append({
            'id': user.id,
            'username': user.username,
            'nombre': user.get_full_name(),
            'email': user.email,
            'rol': user.rol,
            'rol_display': user.get_rol_display(),
            'rol_color': 'primary' if user.rol == 'admin' else 'info' if user.rol == 'profesor' else 'success' if user.rol == 'tutor' else 'secondary',
        })
    
    return JsonResponse({'results': results})


# ============================================
# ALIAS PARA COMPATIBILIDAD
# ============================================

mensaje_enviar = mensaje_create
mensaje_edit = mensaje_create
mensaje_confirm_delete = mensaje_delete