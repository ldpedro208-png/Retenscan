# core/views/usuarios.py
"""
Vistas para la gestión de usuarios en el sistema RetenScan
"""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Q, Count
from django.contrib.auth.hashers import make_password
from django.utils import timezone
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile
import os
import uuid
from ..forms import UsuarioCreateForm

from ..models import (
    Usuario,
    Estudiante,
    UsuarioEstudiantes,
    CatalogoUniversidad,
    CatalogoCarrera,
    Tutor,
    AsignacionTutor,
)
from ..services.alert_service import AlertaService

# ✅ CORREGIDO: get_universidad_id desde base, el resto desde utils
from .base import get_universidad_id
from ..utils import generar_password_temporal, logger


# ============================================
# 1. LISTAR USUARIOS
# ============================================
@login_required
def usuario_list(request):
    """
    Vista para listar todos los usuarios del sistema.
    Permite filtrar por rol, estado y búsqueda.
    ✅ Los usuarios se filtran por universidad del usuario actual.
    """
    user = request.user
    user_rol = getattr(user, 'rol', 'estudiante')
    universidad_id = get_universidad_id(request)

    # Verificar permisos
    if user_rol not in ['admin', 'tutor', 'profesor']:
        messages.error(request, "No tienes permiso para ver la lista de usuarios.")
        return redirect('dashboard')

    # Obtener parámetros de filtro
    rol_filter = request.GET.get('rol', '')
    estado_filter = request.GET.get('estado', '')
    busqueda = request.GET.get('busqueda', '').strip()

    # ✅ Construir queryset base según rol
    if user_rol == 'admin':
        usuarios = Usuario.objects.filter(
            idUniversidad_id=universidad_id
        ).select_related('idUniversidad')

    elif user_rol == 'tutor':
        estudiantes_ids = UsuarioEstudiantes.objects.filter(
            usuario=user
        ).values_list('estudiante__idUsuario', flat=True)

        usuarios = Usuario.objects.filter(
            Q(id__in=estudiantes_ids) | 
            Q(rol='tutor') | 
            Q(rol='admin')
        ).filter(
            idUniversidad_id=universidad_id
        ).select_related('idUniversidad')

    else:  # profesor
        usuarios = Usuario.objects.filter(
            idUniversidad_id=universidad_id
        ).select_related('idUniversidad')

    # Aplicar filtros
    if rol_filter:
        usuarios = usuarios.filter(rol=rol_filter)

    if estado_filter:
        if estado_filter == 'activo':
            usuarios = usuarios.filter(is_active=True)
        elif estado_filter == 'inactivo':
            usuarios = usuarios.filter(is_active=False)

    if busqueda:
        usuarios = usuarios.filter(
            Q(username__icontains=busqueda) |
            Q(email__icontains=busqueda) |
            Q(first_name__icontains=busqueda) |
            Q(last_name__icontains=busqueda) |
            Q(carnet__icontains=busqueda)
        )

    usuarios = usuarios.order_by('first_name', 'last_name', 'username')

    paginator = Paginator(usuarios, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    total_usuarios = usuarios.count()
    total_activos = usuarios.filter(is_active=True).count()
    total_inactivos = usuarios.filter(is_active=False).count()

    roles_count = {
        'admin': usuarios.filter(rol='admin').count(),
        'tutor': usuarios.filter(rol='tutor').count(),
        'profesor': usuarios.filter(rol='profesor').count(),
        'estudiante': usuarios.filter(rol='estudiante').count(),
    }

    roles_disponibles = [
        ('admin', 'Administrador'),
        ('tutor', 'Tutor'),
        ('profesor', 'Profesor'),
        ('estudiante', 'Estudiante'),
    ]

    context = {
        'usuarios': page_obj,
        'page_obj': page_obj,
        'total_usuarios': total_usuarios,
        'total_activos': total_activos,
        'total_inactivos': total_inactivos,
        'roles_count': roles_count,
        'rol_filter': rol_filter,
        'estado_filter': estado_filter,
        'busqueda': busqueda,
        'user_rol': user_rol,
        'roles_disponibles': roles_disponibles,
        'universidad_nombre': user.idUniversidad.nombre if user.idUniversidad else 'Sin universidad',
    }

    return render(request, 'usuarios/usuario_list.html', context)


# ============================================
# 2. DETALLE DE USUARIO
# ============================================
@login_required
def usuario_detail(request, pk):
    """
    Vista para ver el detalle de un usuario específico.
    """
    user = request.user
    user_rol = getattr(user, 'rol', 'estudiante')
    universidad_id = get_universidad_id(request)

    usuario = get_object_or_404(
        Usuario.objects.select_related('idUniversidad'),
        pk=pk
    )

    if user_rol not in ['admin', 'tutor', 'profesor']:
        if usuario.id != user.id:
            messages.error(request, "No tienes permiso para ver este usuario.")
            return redirect('dashboard')

    if user_rol == 'admin':
        if usuario.idUniversidad_id != universidad_id and not user.is_superuser:
            messages.error(request, "Este usuario no pertenece a tu universidad.")
            return redirect('usuario_list')

    if user_rol == 'tutor':
        es_asignado = UsuarioEstudiantes.objects.filter(
            usuario=user,
            estudiante__idUsuario=usuario
        ).exists()

        if not es_asignado and usuario.rol not in ['tutor', 'admin']:
            messages.error(request, "No tienes permiso para ver este usuario.")
            return redirect('usuario_list')

    if user_rol == 'profesor':
        if usuario.idUniversidad_id != universidad_id and usuario.rol != 'admin':
            messages.error(request, "No tienes permiso para ver este usuario.")
            return redirect('usuario_list')

    info_adicional = None

    if usuario.rol == 'estudiante':
        try:
            estudiante = Estudiante.objects.select_related(
                'idCarrera', 'idCarrera__idUniversidad'
            ).get(idUsuario=usuario)
            info_adicional = {
                'tipo': 'estudiante',
                'objeto': estudiante,
                'carrera': estudiante.idCarrera.nombre if estudiante.idCarrera else 'Sin carrera',
                'estado': estudiante.estado_academico,
            }
        except Estudiante.DoesNotExist:
            info_adicional = None

    elif usuario.rol == 'tutor':
        estudiantes_asignados = UsuarioEstudiantes.objects.filter(
            usuario=usuario
        ).select_related('estudiante__idUsuario', 'estudiante__idCarrera')

        info_adicional = {
            'tipo': 'tutor',
            'estudiantes_asignados': estudiantes_asignados,
            'total_estudiantes': estudiantes_asignados.count(),
        }

    context = {
        'usuario': usuario,
        'info_adicional': info_adicional,
        'user_rol': user_rol,
        'puede_editar': user_rol == 'admin' or (user_rol == 'tutor' and usuario.rol == 'estudiante'),
        'puede_eliminar': user_rol == 'admin' and usuario.id != user.id,
        'puede_cambiar_estado': user_rol in ['admin', 'tutor'] and usuario.id != user.id,
        'universidad_nombre': usuario.idUniversidad.nombre if usuario.idUniversidad else 'Sin universidad',
    }

    return render(request, 'usuarios/usuario_detail.html', context)


# ============================================
# 3. CREAR USUARIO
# ============================================

@login_required
def usuario_create(request):
    """
    Vista para crear un nuevo usuario (admin, tutor, profesor).
    ✅ Solo administradores pueden crear usuarios.
    ✅ Username generado desde nombre + apellido.
    ✅ Contraseña automática o manual.
    ✅ Envío de credenciales por correo con la MISMA contraseña.
    """
    user = request.user
    user_rol = getattr(user, 'rol', 'estudiante')
    universidad_id = get_universidad_id(request)

    # ✅ Verificar permisos
    if user_rol != 'admin':
        messages.error(request, "No tienes permiso para crear usuarios.")
        return redirect('dashboard')

    # ✅ Verificar universidad
    if not universidad_id:
        messages.error(request, "Error: No se encontró una universidad asociada a tu cuenta.")
        return redirect('dashboard')

    try:
        universidad = CatalogoUniversidad.objects.get(idUniversidad=universidad_id)
    except CatalogoUniversidad.DoesNotExist:
        messages.error(request, "Error: Universidad no encontrada.")
        return redirect('dashboard')

    # ✅ POST: procesar formulario
    if request.method == 'POST':
        form = UsuarioCreateForm(request.POST, request.FILES)
        
        if form.is_valid():
            try:
                with transaction.atomic():
                    # ✅ Guardar usuario (maneja username, contraseña, correo)
                    usuario = form.save(commit=True, request=request)
                    
                    messages.success(
                        request,
                        f"✅ Usuario '{usuario.get_full_name()}' creado exitosamente "
                        f"con username: @{usuario.username}. "
                        f"Rol: {usuario.get_rol_display()}"
                    )
                    return redirect('usuario_detail', pk=usuario.pk)

            except Exception as e:
                logger.error(f"Error creando usuario: {str(e)}", exc_info=True)
                messages.error(request, f"Error al crear el usuario: {str(e)}")
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f"{field}: {error}")

    else:
        # ✅ GET: formulario vacío
        form = UsuarioCreateForm()

    # ✅ Contexto para el template
    context = {
        'form': form,
        'user_rol': user_rol,
        'universidad': universidad,
        'universidad_nombre': universidad.nombre,
        'titulo': 'Crear Usuario',
        'roles_disponibles': [
            ('admin', 'Administrador'),
            ('tutor', 'Tutor'),
            ('profesor', 'Profesor'),
        ],
        'es_creacion': True,
    }
    return render(request, 'usuarios/usuario_form.html', context)

# ============================================
# 4. EDITAR USUARIO
# ============================================
# core/views/usuarios.py
# ✅ ACTUALIZADO - Usa UsuarioCreateForm

from ..forms import UsuarioCreateForm  # ✅ Importar


@login_required
def usuario_edit(request, pk):
    """
    Vista para editar un usuario existente.
    ✅ Solo admin puede editar usuarios.
    ✅ Carga todos los datos actuales del usuario (modificables y no modificables).
    ✅ Maneja correctamente la actualización del Tutor (no duplica).
    ✅ El username y rol NO se pueden modificar.
    """
    user = request.user
    user_rol = getattr(user, 'rol', 'estudiante')
    universidad_id = get_universidad_id(request)

    usuario = get_object_or_404(Usuario, pk=pk)

    # ✅ Verificar permisos
    if user_rol != 'admin':
        messages.error(request, "No tienes permiso para editar usuarios.")
        return redirect('usuario_list')

    # ✅ Verificar universidad
    if usuario.idUniversidad_id != universidad_id and not user.is_superuser:
        messages.error(request, "Este usuario no pertenece a tu universidad.")
        return redirect('usuario_list')

    # ✅ No permitir editar su propio usuario desde aquí
    if usuario.id == user.id:
        messages.warning(request, "Para editar tu propio perfil, usa la opción 'Mi Perfil'.")
        return redirect('perfil')

    # ✅ Obtener Tutor si aplica
    tutor_obj = None
    if usuario.rol == 'tutor':
        from ..models import Tutor
        tutor_obj = Tutor.objects.filter(usuario=usuario).first()

    if request.method == 'POST':
        form = UsuarioCreateForm(request.POST, request.FILES, instance=usuario)
        
        if form.is_valid():
            try:
                with transaction.atomic():
                    # ✅ Guardar el usuario (no modifica username ni rol)
                    usuario = form.save(commit=False, request=request)
                    
                    # ✅ Preservar username y rol originales (no modificables)
                    # (El form ya no los toca, pero por si acaso)
                    
                    # ✅ Manejar is_active desde el POST
                    usuario.is_active = request.POST.get('is_active') == 'on'
                    usuario.save()
                    
                    # ✅ Actualizar Tutor si aplica
                    if usuario.rol == 'tutor':
                        from ..models import Tutor
                        Tutor.objects.update_or_create(
                            usuario=usuario,
                            defaults={
                                'especialidad': form.cleaned_data.get('especialidad', '').strip(),
                                'max_estudiantes': int(form.cleaned_data.get('max_estudiantes') or 10),
                                'activo': form.cleaned_data.get('tutor_activo', True),
                            }
                        )
                        logger.info(f"✅ Tutor actualizado para @{usuario.username}")

                    messages.success(
                        request,
                        f"✅ Usuario '{usuario.get_full_name()}' actualizado exitosamente."
                    )
                    return redirect('usuario_detail', pk=usuario.pk)

            except Exception as e:
                logger.error(f"Error editando usuario: {str(e)}", exc_info=True)
                messages.error(request, f"Error al actualizar el usuario: {str(e)}")
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f"{field}: {error}")

    else:
        # ✅ GET: Cargar formulario con datos actuales
        form = UsuarioCreateForm(instance=usuario)

    # ✅ Contexto para el template
    context = {
        'form': form,
        'usuario': usuario,
        'user_rol': user_rol,
        'tutor_obj': tutor_obj,
        'universidad_nombre': usuario.idUniversidad.nombre if usuario.idUniversidad else 'Sin universidad',
        'titulo': f'Editar Usuario: {usuario.get_full_name()}',
        'roles_disponibles': [
            ('admin', 'Administrador'),
            ('tutor', 'Tutor'),
            ('profesor', 'Profesor'),
        ],
        'es_edicion': True,
    }
    return render(request, 'usuarios/usuario_form.html', context)


# ============================================
# 5. ELIMINAR USUARIO
# ============================================
@login_required
def usuario_delete(request, pk):
    """
    Vista para eliminar un usuario.
    ✅ Solo admin puede eliminar usuarios.
    """
    user = request.user
    user_rol = getattr(user, 'rol', 'estudiante')
    universidad_id = get_universidad_id(request)

    if user_rol != 'admin':
        messages.error(request, "No tienes permiso para eliminar usuarios.")
        return redirect('dashboard')

    usuario = get_object_or_404(Usuario, pk=pk)

    if usuario.idUniversidad_id != universidad_id and not user.is_superuser:
        messages.error(request, "Este usuario no pertenece a tu universidad.")
        return redirect('usuario_list')

    if usuario.id == user.id:
        messages.error(request, "No puedes eliminar tu propio usuario.")
        return redirect('usuario_list')

    if request.method == 'POST':
        username = usuario.username
        if usuario.foto:
            default_storage.delete(usuario.foto.name)
        usuario.delete()
        messages.success(request, f"✅ Usuario '{username}' eliminado exitosamente.")
        return redirect('usuario_list')

    context = {
        'usuario': usuario,
        'user_rol': user_rol,
        'universidad_nombre': usuario.idUniversidad.nombre if usuario.idUniversidad else 'Sin universidad',
    }

    return render(request, 'usuarios/usuario_confirm_delete.html', context)


# ============================================
# 6. CAMBIAR ESTADO DE USUARIO (ACTIVAR/DESACTIVAR)
# ============================================
@login_required
def usuario_toggle_active(request, pk):
    """
    Vista para activar/desactivar un usuario.
    ✅ Solo admin puede cambiar el estado.
    """
    user = request.user
    user_rol = getattr(user, 'rol', 'estudiante')
    universidad_id = get_universidad_id(request)

    if user_rol != 'admin':
        messages.error(request, "No tienes permiso para cambiar el estado de usuarios.")
        return redirect('dashboard')

    usuario = get_object_or_404(Usuario, pk=pk)

    if usuario.idUniversidad_id != universidad_id and not user.is_superuser:
        messages.error(request, "Este usuario no pertenece a tu universidad.")
        return redirect('usuario_list')

    if usuario.id == user.id:
        messages.error(request, "No puedes cambiar el estado de tu propio usuario.")
        return redirect('usuario_list')

    usuario.is_active = not usuario.is_active
    usuario.save()

    estado = "activado" if usuario.is_active else "desactivado"
    messages.success(request, f"✅ Usuario '{usuario.username}' {estado} exitosamente.")

    return redirect('usuario_list')


# ============================================
# 7. PERFIL DE USUARIO
# ============================================
@login_required
def perfil_view(request):
    """
    Vista para ver y editar el perfil del usuario actual.
    """
    usuario = request.user
    user_rol = getattr(usuario, 'rol', 'estudiante')
    universidad_id = get_universidad_id(request)

    if request.method == 'POST':
        first_name = request.POST.get('first_name', '').strip()
        last_name = request.POST.get('last_name', '').strip()
        email = request.POST.get('email', '').strip().lower()
        telefono = request.POST.get('telefono', '').strip()
        whatsapp_telefono = request.POST.get('whatsapp_telefono', '').strip()
        notificaciones_email = request.POST.get('notificaciones_email') == 'on'
        notificaciones_whatsapp = request.POST.get('notificaciones_whatsapp') == 'on'
        foto = request.FILES.get('foto')

        errores = []

        if not first_name:
            errores.append("El nombre es obligatorio.")
        if not last_name:
            errores.append("El apellido es obligatorio.")
        if not email:
            errores.append("El email es obligatorio.")
        elif '@' not in email:
            errores.append("El email no es válido.")

        if Usuario.objects.filter(email=email).exclude(pk=usuario.pk).exists():
            errores.append(f"El email '{email}' ya está registrado.")

        if foto:
            if foto.size > 5 * 1024 * 1024:
                errores.append("La foto no puede superar los 5MB.")
            if not foto.content_type.startswith('image/'):
                errores.append("El archivo debe ser una imagen.")

        if errores:
            for error in errores:
                messages.error(request, error)
            return redirect('perfil')

        try:
            with transaction.atomic():
                usuario.first_name = first_name
                usuario.last_name = last_name
                usuario.email = email
                usuario.telefono = telefono if telefono else None
                usuario.whatsapp_telefono = whatsapp_telefono if whatsapp_telefono else None
                usuario.notificaciones_email = notificaciones_email
                usuario.notificaciones_whatsapp = notificaciones_whatsapp

                if foto:
                    if usuario.foto:
                        default_storage.delete(usuario.foto.name)
                    extension = os.path.splitext(foto.name)[1]
                    filename = f'usuarios/fotos/{uuid.uuid4()}{extension}'
                    saved_path = default_storage.save(filename, ContentFile(foto.read()))
                    usuario.foto = saved_path

                usuario.save()
                messages.success(request, "✅ Perfil actualizado exitosamente.")
                return redirect('perfil')

        except Exception as e:
            logger.error(f"Error actualizando perfil: {str(e)}")
            messages.error(request, f"Error al actualizar el perfil: {str(e)}")

    info_adicional = None
    if user_rol == 'estudiante':
        try:
            estudiante = Estudiante.objects.select_related('idCarrera').get(idUsuario=usuario)
            info_adicional = {
                'estudiante': estudiante,
                'carrera': estudiante.idCarrera.nombre if estudiante.idCarrera else 'Sin carrera',
                'semestre': estudiante.semestre_actual,
                'estado': estudiante.estado_academico,
            }
        except Estudiante.DoesNotExist:
            info_adicional = None

    context = {
        'usuario': usuario,
        'user_rol': user_rol,
        'info_adicional': info_adicional,
        'universidad_nombre': usuario.idUniversidad.nombre if usuario.idUniversidad else 'Sin universidad',
        'es_estudiante': user_rol == 'estudiante',
    }

    return render(request, 'layout/perfil.html', context)


# ============================================
# 8. ASIGNAR ESTUDIANTES A TUTOR
# ============================================
@login_required
def usuario_asignar_estudiantes(request, pk):
    """
    Vista para asignar estudiantes a un tutor.
    ✅ Solo admin puede asignar estudiantes.
    """
    user = request.user
    user_rol = getattr(user, 'rol', 'estudiante')
    universidad_id = get_universidad_id(request)

    if user_rol != 'admin':
        messages.error(request, "No tienes permiso para asignar estudiantes.")
        return redirect('dashboard')

    tutor = get_object_or_404(Usuario, pk=pk, rol='tutor')

    if tutor.idUniversidad_id != universidad_id and not user.is_superuser:
        messages.error(request, "Este tutor no pertenece a tu universidad.")
        return redirect('usuario_list')

    if request.method == 'POST':
        estudiantes_ids = request.POST.getlist('estudiantes')

        if not estudiantes_ids:
            messages.warning(request, "Selecciona al menos un estudiante.")
        else:
            UsuarioEstudiantes.objects.filter(usuario=tutor).delete()

            asignados = 0
            for estudiante_id in estudiantes_ids:
                estudiante = get_object_or_404(Estudiante, pk=estudiante_id)
                if estudiante.idCarrera.idUniversidad_id == universidad_id or user.is_superuser:
                    UsuarioEstudiantes.objects.create(
                        usuario=tutor,
                        estudiante=estudiante
                    )
                    asignados += 1

            messages.success(request, f"✅ {asignados} estudiantes asignados a {tutor.get_full_name()}.")

        return redirect('usuario_detail', pk=tutor.pk)

    estudiantes = Estudiante.objects.filter(
        estado_academico='Activo',
        idCarrera__idUniversidad_id=universidad_id
    ).select_related('idUsuario', 'idCarrera')

    asignados_ids = UsuarioEstudiantes.objects.filter(
        usuario=tutor
    ).values_list('estudiante_id', flat=True)

    context = {
        'tutor': tutor,
        'estudiantes': estudiantes,
        'asignados_ids': list(asignados_ids),
        'user_rol': user_rol,
        'universidad_nombre': tutor.idUniversidad.nombre if tutor.idUniversidad else 'Sin universidad',
    }

    return render(request, 'usuarios/usuario_asignar_estudiantes.html', context)