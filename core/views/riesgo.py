# views/riesgo.py - VERSIÓN FINAL (UNIFICADA)

"""
Vistas para la gestión de riesgos, factores e intervenciones
"""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.utils import timezone
from django.db.models import Q
from django.db import transaction

from ..models import (
    Estudiante, RiesgoEstudiante, Intervencion,
    CatalogoFactorRiesgo, UsuarioEstudiantes, Usuario
)
from ..services.alert_service import AlertaService
from .base import (
    get_universidad_id, 
    obtener_modelo_predictivo,
    obtener_servicio_prediccion, 
    logger
)


# ============================================
# SECCIÓN 1: FACTORES DE RIESGO (CRUD)
# ============================================

@login_required
def factor_riesgo_list(request):
    """
    Lista todos los factores de riesgo del catálogo
    """
    user_rol = getattr(request.user, 'rol', 'estudiante')

    if user_rol != 'admin':
        messages.error(request, "No tienes permiso para gestionar factores de riesgo.")
        return redirect('dashboard')

    factores = CatalogoFactorRiesgo.objects.all().order_by('nombre')
    
    # Estadísticas
    total_factores = factores.count()
    activos = factores.filter(activo=True).count()
    inactivos = factores.filter(activo=False).count()

    context = {
        'factores': factores,
        'total_factores': total_factores,
        'activos': activos,
        'inactivos': inactivos,
        'user_rol': user_rol,
    }
    return render(request, 'Inteligencia Art/factor_riesgo_list.html', context)


@login_required
def factor_riesgo_create(request):
    """
    Crear un nuevo factor de riesgo
    """
    user_rol = getattr(request.user, 'rol', 'estudiante')

    if user_rol != 'admin':
        messages.error(request, "No tienes permiso para crear factores de riesgo.")
        return redirect('dashboard')

    if request.method == 'POST':
        nombre = request.POST.get('nombre', '').strip()
        peso = request.POST.get('peso', 1.0)
        descripcion = request.POST.get('descripcion', '').strip()
        activo = request.POST.get('activo') == 'on'

        # Validaciones
        if not nombre:
            messages.error(request, "El nombre del factor es obligatorio.")
            context = {
                'user_rol': user_rol,
                'es_nuevo': True,
                'nombre': nombre,
                'peso': peso,
                'descripcion': descripcion,
                'activo': activo,
            }
            return render(request, 'Inteligencia Art/factor_riesgo_form.html', context)

        # Verificar duplicado
        if CatalogoFactorRiesgo.objects.filter(nombre__iexact=nombre).exists():
            messages.error(request, f"Ya existe un factor con el nombre '{nombre}'.")
            context = {
                'user_rol': user_rol,
                'es_nuevo': True,
                'nombre': nombre,
                'peso': peso,
                'descripcion': descripcion,
                'activo': activo,
            }
            return render(request, 'Inteligencia Art/factor_riesgo_form.html', context)

        try:
            with transaction.atomic():
                factor = CatalogoFactorRiesgo.objects.create(
                    nombre=nombre,
                    peso=peso,
                    descripcion=descripcion,
                    activo=activo
                )
            messages.success(request, f"✅ Factor '{factor.nombre}' creado exitosamente.")
            return redirect('factor_riesgo_list')
        except Exception as e:
            logger.error(f"Error creando factor: {str(e)}")
            messages.error(request, f"Error al crear el factor: {str(e)}")

    # GET: Mostrar formulario
    context = {
        'user_rol': user_rol,
        'es_nuevo': True,
        'nombre': '',
        'peso': 1.0,
        'descripcion': '',
        'activo': True,
    }
    return render(request, 'Inteligencia Art/factor_riesgo_form.html', context)


@login_required
def factor_riesgo_edit(request, pk):
    """
    Editar un factor de riesgo existente
    """
    user_rol = getattr(request.user, 'rol', 'estudiante')

    if user_rol != 'admin':
        messages.error(request, "No tienes permiso para editar factores de riesgo.")
        return redirect('dashboard')

    factor = get_object_or_404(CatalogoFactorRiesgo, pk=pk)

    if request.method == 'POST':
        nombre = request.POST.get('nombre', '').strip()
        peso = request.POST.get('peso', 1.0)
        descripcion = request.POST.get('descripcion', '').strip()
        activo = request.POST.get('activo') == 'on'

        # Validaciones
        if not nombre:
            messages.error(request, "El nombre del factor es obligatorio.")
            context = {
                'user_rol': user_rol,
                'factor': factor,
                'es_nuevo': False,
                'nombre': nombre,
                'peso': peso,
                'descripcion': descripcion,
                'activo': activo,
            }
            return render(request, 'Inteligencia Art/factor_riesgo_form.html', context)

        # Verificar duplicado (excluyendo el actual)
        if CatalogoFactorRiesgo.objects.filter(nombre__iexact=nombre).exclude(pk=pk).exists():
            messages.error(request, f"Ya existe otro factor con el nombre '{nombre}'.")
            context = {
                'user_rol': user_rol,
                'factor': factor,
                'es_nuevo': False,
                'nombre': nombre,
                'peso': peso,
                'descripcion': descripcion,
                'activo': activo,
            }
            return render(request, 'Inteligencia Art/factor_riesgo_form.html', context)

        try:
            with transaction.atomic():
                factor.nombre = nombre
                factor.peso = peso
                factor.descripcion = descripcion
                factor.activo = activo
                factor.save()
            messages.success(request, f"✅ Factor '{factor.nombre}' actualizado exitosamente.")
            return redirect('factor_riesgo_list')
        except Exception as e:
            logger.error(f"Error actualizando factor: {str(e)}")
            messages.error(request, f"Error al actualizar el factor: {str(e)}")

    # GET: Mostrar formulario con datos
    context = {
        'user_rol': user_rol,
        'factor': factor,
        'es_nuevo': False,
        'nombre': factor.nombre,
        'peso': factor.peso,
        'descripcion': factor.descripcion or '',
        'activo': factor.activo,
    }
    return render(request, 'Inteligencia Art/factor_riesgo_form.html', context)


@login_required
def factor_riesgo_delete(request, pk):
    """
    Eliminar un factor de riesgo (solo si no tiene riesgos asociados)
    """
    user_rol = getattr(request.user, 'rol', 'estudiante')

    if user_rol != 'admin':
        messages.error(request, "No tienes permiso para eliminar factores de riesgo.")
        return redirect('dashboard')

    factor = get_object_or_404(CatalogoFactorRiesgo, pk=pk)

    # Verificar si tiene riesgos asociados
    riesgos_asociados = RiesgoEstudiante.objects.filter(idFactor=factor).count()
    
    if riesgos_asociados > 0:
        messages.error(
            request, 
            f"No se puede eliminar el factor '{factor.nombre}' porque tiene {riesgos_asociados} riesgo(s) asociado(s)."
        )
        return redirect('factor_riesgo_list')

    if request.method == 'POST':
        nombre = factor.nombre
        factor.delete()
        messages.success(request, f"✅ Factor '{nombre}' eliminado exitosamente.")
        return redirect('factor_riesgo_list')

    # GET: Mostrar confirmación
    context = {
        'user_rol': user_rol,
        'factor': factor,
        'riesgos_asociados': riesgos_asociados,
    }
    return render(request, 'Inteligencia Art/factor_riesgo_confirm_delete.html', context)


@login_required
def factor_riesgo_toggle(request, pk):
    """
    Activar/Desactivar un factor de riesgo
    """
    user_rol = getattr(request.user, 'rol', 'estudiante')

    if user_rol != 'admin':
        messages.error(request, "No tienes permiso para modificar factores de riesgo.")
        return redirect('dashboard')

    factor = get_object_or_404(CatalogoFactorRiesgo, pk=pk)
    factor.activo = not factor.activo
    factor.save()

    estado = "activado" if factor.activo else "desactivado"
    messages.success(request, f"✅ Factor '{factor.nombre}' {estado} exitosamente.")
    return redirect('factor_riesgo_list')


# ============================================
# SECCIÓN 2: DASHBOARD DE RIESGOS (IA)
# ============================================

@login_required
def dashboard_riesgo(request):
    """
    Dashboard de riesgos con predicciones de IA
    """
    user_rol = getattr(request.user, 'rol', 'estudiante')

    if user_rol not in ['admin', 'tutor', 'profesor']:
        messages.error(request, "No tienes permiso para ver este dashboard")
        return redirect('dashboard')

    modelo = obtener_modelo_predictivo()

    if modelo is None:
        messages.warning(request, "El sistema de IA no está disponible. Contacta al administrador.")
        context = {
            'user_rol': user_rol,
            'hay_riesgos': False,
            'modelo_disponible': False,
            'necesita_entrenamiento': True,
        }
        return render(request, 'Inteligencia Art/dashboard_riesgo.html', context)

    if modelo.modelo is None:
        messages.warning(request, "El modelo no está entrenado. Ve a 'Entrenar Modelo' para entrenarlo.")
        context = {
            'user_rol': user_rol,
            'hay_riesgos': False,
            'modelo_disponible': False,
            'necesita_entrenamiento': True,
        }
        return render(request, 'Inteligencia Art/dashboard_riesgo.html', context)

    servicio = obtener_servicio_prediccion()

    try:
        estudiantes_riesgo = servicio.obtener_estudiantes_riesgo(request.user) if servicio else []
    except Exception as e:
        logger.error(f"Error obteniendo estudiantes en riesgo: {str(e)}")
        estudiantes_riesgo = []
        messages.warning(request, "Error al obtener predicciones. Intenta entrenar el modelo.")

    total = len(estudiantes_riesgo)
    criticos = sum(1 for e in estudiantes_riesgo if e.get('nivel_riesgo') == 'Crítico')
    altos = sum(1 for e in estudiantes_riesgo if e.get('nivel_riesgo') == 'Alto')
    medios = sum(1 for e in estudiantes_riesgo if e.get('nivel_riesgo') == 'Medio')
    bajos = sum(1 for e in estudiantes_riesgo if e.get('nivel_riesgo') == 'Bajo')

    context = {
        'user_rol': user_rol,
        'estudiantes_riesgo': estudiantes_riesgo[:20],  # Mostrar solo 20
        'total': total,
        'criticos': criticos,
        'altos': altos,
        'medios': medios,
        'bajos': bajos,
        'hay_riesgos': len(estudiantes_riesgo) > 0,
        'modelo_disponible': modelo is not None and modelo.modelo is not None,
        'necesita_entrenamiento': modelo is not None and modelo.modelo is None,
    }

    return render(request, 'Inteligencia Art/dashboard_riesgo.html', context)


# ============================================
# SECCIÓN 3: GESTIÓN DE RIESGOS (CRUD)
# ============================================

@login_required
def riesgo_gestion(request):
    """
    Vista unificada para gestionar riesgos:
    - Lista todos los riesgos con filtros
    - Permite crear nuevos riesgos
    - Permite editar y eliminar riesgos existentes
    """
    user_rol = getattr(request.user, 'rol', 'estudiante')
    universidad_id = get_universidad_id(request)

    if user_rol not in ['admin', 'tutor']:
        messages.error(request, "No tienes permiso para gestionar riesgos.")
        return redirect('dashboard')

    # ============================================
    # 1. OBTENER LISTA DE RIESGOS
    # ============================================
    if user_rol == 'admin':
        riesgos = RiesgoEstudiante.objects.all().select_related(
            'idEstudiante__idUsuario', 'idFactor'
        ).order_by('-fecha_deteccion')
    else:  # tutor
        estudiantes_asignados = UsuarioEstudiantes.objects.filter(
            usuario_id=request.user.id
        ).values_list('estudiante_id', flat=True)
        riesgos = RiesgoEstudiante.objects.filter(
            idEstudiante__in=estudiantes_asignados
        ).select_related(
            'idEstudiante__idUsuario', 'idFactor'
        ).order_by('-fecha_deteccion')

    # ============================================
    # 2. APLICAR FILTROS
    # ============================================
    nivel_filter = request.GET.get('nivel')
    estado_filter = request.GET.get('estado')
    estudiante_filter = request.GET.get('estudiante')
    factor_filter = request.GET.get('factor')

    if nivel_filter:
        riesgos = riesgos.filter(nivel=nivel_filter)
    if estado_filter:
        riesgos = riesgos.filter(estado=estado_filter)
    if estudiante_filter:
        riesgos = riesgos.filter(idEstudiante_id=estudiante_filter)
    if factor_filter:
        riesgos = riesgos.filter(idFactor_id=factor_filter)

    # ============================================
    # 3. OBTENER ESTUDIANTES PARA FILTRO Y CREACIÓN
    # ============================================
    if user_rol == 'admin':
        estudiantes = Estudiante.objects.all().select_related('idUsuario').order_by('idUsuario__first_name')
    else:
        estudiantes_asignados = UsuarioEstudiantes.objects.filter(
            usuario_id=request.user.id
        ).values_list('estudiante_id', flat=True)
        estudiantes = Estudiante.objects.filter(
            idEstudiante__in=estudiantes_asignados
        ).select_related('idUsuario').order_by('idUsuario__first_name')

    # ============================================
    # 4. PROCESAR FORMULARIOS (POST)
    # ============================================
    if request.method == 'POST':
        accion = request.POST.get('accion')

        if accion == 'crear':
            # Crear nuevo riesgo
            estudiante_id = request.POST.get('estudiante_id')
            if not estudiante_id:
                messages.error(request, "Debes seleccionar un estudiante.")
                return redirect('riesgo_gestion')

            estudiante = get_object_or_404(Estudiante, pk=estudiante_id)
            
            # Verificar permisos para tutor
            if user_rol == 'tutor':
                es_asignado = UsuarioEstudiantes.objects.filter(
                    usuario_id=request.user.id,
                    estudiante_id=estudiante.idEstudiante
                ).exists()
                if not es_asignado:
                    messages.error(request, "No tienes permiso para registrar riesgos de este estudiante.")
                    return redirect('riesgo_gestion')

            try:
                with transaction.atomic():
                    riesgo = RiesgoEstudiante.objects.create(
                        idEstudiante=estudiante,
                        idFactor_id=request.POST.get('idFactor'),
                        nivel=request.POST.get('nivel'),
                        fecha_deteccion=request.POST.get('fecha_deteccion') or timezone.now().date(),
                        observaciones=request.POST.get('observaciones', ''),
                        estado=request.POST.get('estado', 'Activo')
                    )

                    # Enviar alerta
                    try:
                        AlertaService.alerta_estudiante_riesgo(estudiante, riesgo)
                    except Exception as e:
                        logger.error(f"Error al enviar alerta de riesgo: {str(e)}")

                    messages.success(request, f"✅ Riesgo registrado para {estudiante.nombre}.")
            except Exception as e:
                logger.error(f"Error creando riesgo: {str(e)}")
                messages.error(request, f"Error al registrar el riesgo: {str(e)}")

            return redirect('riesgo_gestion')

        elif accion == 'editar':
            # Editar riesgo existente
            riesgo_id = request.POST.get('riesgo_id')
            riesgo = get_object_or_404(RiesgoEstudiante, pk=riesgo_id)
            
            # Verificar permisos
            if user_rol == 'tutor':
                es_asignado = UsuarioEstudiantes.objects.filter(
                    usuario_id=request.user.id,
                    estudiante_id=riesgo.idEstudiante.idEstudiante
                ).exists()
                if not es_asignado:
                    messages.error(request, "No tienes permiso para editar este riesgo.")
                    return redirect('riesgo_gestion')

            try:
                with transaction.atomic():
                    riesgo.idFactor_id = request.POST.get('idFactor')
                    riesgo.nivel = request.POST.get('nivel')
                    riesgo.fecha_deteccion = request.POST.get('fecha_deteccion')
                    riesgo.observaciones = request.POST.get('observaciones', '')
                    riesgo.estado = request.POST.get('estado')
                    riesgo.save()
                messages.success(request, "✅ Riesgo actualizado exitosamente.")
            except Exception as e:
                logger.error(f"Error editando riesgo: {str(e)}")
                messages.error(request, f"Error al actualizar el riesgo: {str(e)}")

            return redirect('riesgo_gestion')

        elif accion == 'eliminar':
            # Eliminar riesgo
            riesgo_id = request.POST.get('riesgo_id')
            riesgo = get_object_or_404(RiesgoEstudiante, pk=riesgo_id)
            
            # Verificar permisos
            if user_rol == 'tutor':
                es_asignado = UsuarioEstudiantes.objects.filter(
                    usuario_id=request.user.id,
                    estudiante_id=riesgo.idEstudiante.idEstudiante
                ).exists()
                if not es_asignado:
                    messages.error(request, "No tienes permiso para eliminar este riesgo.")
                    return redirect('riesgo_gestion')

            estudiante_nombre = riesgo.idEstudiante.nombre
            riesgo.delete()
            messages.success(request, f"✅ Riesgo eliminado para {estudiante_nombre}.")
            return redirect('riesgo_gestion')

    # ============================================
    # 5. CONTEXTO PARA LA PLANTILLA
    # ============================================
    factores = CatalogoFactorRiesgo.objects.filter(activo=True)

    context = {
        'riesgos': riesgos,
        'estudiantes': estudiantes,
        'factores': factores,
        'niveles': RiesgoEstudiante.NIVEL_CHOICES,
        'estados': RiesgoEstudiante.ESTADO_CHOICES,
        'user_rol': user_rol,
        'nivel_filter': nivel_filter,
        'estado_filter': estado_filter,
        'estudiante_filter': estudiante_filter,
        'factor_filter': factor_filter,
    }
    return render(request, 'Inteligencia Art/riesgo_gestion.html', context)


# ============================================
# SECCIÓN 4: DETALLE DE RIESGO
# ============================================

@login_required
def riesgo_detail(request, pk):
    """
    Vista para ver el detalle de un riesgo específico.
    """
    user_rol = getattr(request.user, 'rol', 'estudiante')
    universidad_id = get_universidad_id(request)

    riesgo = get_object_or_404(RiesgoEstudiante, pk=pk)

    # Verificar permisos
    if user_rol not in ['admin', 'tutor']:
        messages.error(request, "No tienes permiso para ver este riesgo.")
        return redirect('dashboard')

    # Verificar que el tutor tenga acceso al estudiante
    if user_rol == 'tutor':
        es_asignado = UsuarioEstudiantes.objects.filter(
            usuario_id=request.user.id,
            estudiante_id=riesgo.idEstudiante.idEstudiante
        ).exists()
        if not es_asignado:
            messages.error(request, "No tienes permiso para ver este riesgo.")
            return redirect('dashboard')

    # Obtener intervenciones relacionadas
    intervenciones = Intervencion.objects.filter(
        idEstudiante=riesgo.idEstudiante,
        idRiesgo=riesgo
    ).order_by('-fecha_programada')

    context = {
        'riesgo': riesgo,
        'estudiante': riesgo.idEstudiante,
        'factor': riesgo.idFactor,
        'intervenciones': intervenciones,
        'user_rol': user_rol,
    }
    return render(request, 'Inteligencia Art/riesgo_detail.html', context)


# ============================================
# SECCIÓN 5: INTERVENCIONES
# ============================================

@login_required
def intervencion_create(request, estudiante_id):
    """
    Crear una intervención para un estudiante
    """
    user_rol = getattr(request.user, 'rol', 'estudiante')
    universidad_id = get_universidad_id(request)

    if user_rol not in ['admin', 'tutor']:
        messages.error(request, "No tienes permiso para registrar intervenciones.")
        return redirect('dashboard')

    if request.user.is_superuser:
        estudiante = get_object_or_404(Estudiante, pk=estudiante_id)
    else:
        estudiante = get_object_or_404(
            Estudiante,
            pk=estudiante_id,
            idCarrera__idUniversidad_id=universidad_id
        )

    if user_rol == 'tutor':
        es_asignado = UsuarioEstudiantes.objects.filter(
            usuario_id=request.user.id,
            estudiante_id=estudiante.idEstudiante
        ).exists()
        if not es_asignado:
            messages.error(request, "No tienes permiso para intervenir con este estudiante.")
            return redirect('dashboard')

    if request.method == 'POST':
        try:
            with transaction.atomic():
                intervencion = Intervencion.objects.create(
                    idEstudiante=estudiante,
                    tipo_intervencion=request.POST.get('tipo_intervencion'),
                    fecha_programada=request.POST.get('fecha_programada'),
                    fecha_realizada=request.POST.get('fecha_realizada') or None,
                    responsable=f"{request.user.first_name} {request.user.last_name}" or request.user.username,
                    descripcion=request.POST.get('descripcion'),
                    resultado=request.POST.get('resultado'),
                    efectiva=request.POST.get('efectiva') == 'on',
                    idRiesgo=request.POST.get('idRiesgo') or None
                )
            messages.success(request, f"✅ Intervención registrada para {estudiante.nombre}.")
            return redirect('estudiante_detail', pk=estudiante.idEstudiante)
        except Exception as e:
            logger.error(f"Error creando intervención: {str(e)}")
            messages.error(request, f"Error al registrar la intervención: {str(e)}")

    riesgos = RiesgoEstudiante.objects.filter(
        idEstudiante=estudiante,
        estado='Activo'
    )

    context = {
        'estudiante': estudiante,
        'riesgos': riesgos,
        'user_rol': user_rol,
    }
    return render(request, 'tutor/intervencion_form.html', context)


# ============================================
# SECCIÓN 6: INTELIGENCIA ARTIFICIAL
# ============================================

@login_required
def entrenar_modelo_view(request):
    """
    Entrenar el modelo de IA para predicción de riesgos.
    """
    user_rol = getattr(request.user, 'rol', 'estudiante')

    if user_rol != 'admin':
        messages.error(request, "No tienes permiso para entrenar el modelo")
        return redirect('dashboard')

    if request.method == 'POST':
        try:
            # ✅ Delegamos al servicio unificado (invalida caché automáticamente)
            from ..services.ai_service import AIService

            resultado = AIService.entrenar_modelo(invalidar_cache=True)

            if resultado:
                messages.success(request, "✅ Modelo entrenado exitosamente")
            else:
                messages.warning(
                    request,
                    "No se pudo entrenar el modelo. No hay datos suficientes."
                )
        except Exception as e:
            logger.error(f"Error entrenando modelo: {str(e)}", exc_info=True)
            messages.error(request, f"Error entrenando modelo: {str(e)}")

        return redirect('dashboard_riesgo')

    # GET
    modelo = obtener_modelo_predictivo()
    context = {
        'entrenado': modelo is not None and getattr(modelo, 'modelo', None) is not None,
        'user_rol': user_rol,
    }
    return render(request, 'Inteligencia Art/entrenar_modelo.html', context)

@login_required
def predecir_estudiante(request, estudiante_id):
    """
    API para predecir el riesgo de un estudiante específico
    """
    user_rol = getattr(request.user, 'rol', 'estudiante')

    if user_rol == 'estudiante':
        try:
            estudiante = Estudiante.objects.get(idUsuario=request.user.id)
            if estudiante.idEstudiante != estudiante_id:
                return JsonResponse({'error': 'No tienes permiso'}, status=403)
        except Estudiante.DoesNotExist:
            return JsonResponse({'error': 'Estudiante no encontrado'}, status=404)

    modelo = obtener_modelo_predictivo()

    if modelo is None:
        return JsonResponse({'error': 'Modelo no disponible'}, status=503)

    if modelo.modelo is None:
        return JsonResponse({'error': 'Modelo no entrenado'}, status=503)

    try:
        resultado = modelo.predecir_estudiante(estudiante_id)
        return JsonResponse(resultado)
    except Exception as e:
        logger.error(f"Error prediciendo estudiante {estudiante_id}: {str(e)}")
        return JsonResponse({'error': str(e)}, status=500)


@login_required
def actualizar_riesgos(request):
    """
    Actualizar los riesgos de todos los estudiantes usando IA
    """
    user_rol = getattr(request.user, 'rol', 'estudiante')

    if user_rol != 'admin':
        messages.error(request, "No tienes permiso para actualizar riesgos")
        return redirect('dashboard')

    servicio = obtener_servicio_prediccion()

    if servicio is None:
        messages.warning(request, "El servicio de predicción no está disponible")
        return redirect('dashboard_riesgo')

    modelo = obtener_modelo_predictivo()

    if modelo is None or modelo.modelo is None:
        messages.warning(request, "El modelo no está entrenado. Entrena el modelo primero.")
        return redirect('dashboard_riesgo')

    if request.method == 'POST':
        try:
            actualizados, errores = servicio.actualizar_riesgos_db()
            messages.success(request, f"✅ Riesgos actualizados: {actualizados} estudiantes procesados, {errores} errores")
        except Exception as e:
            logger.error(f"Error actualizando riesgos: {str(e)}")
            messages.error(request, f"Error actualizando riesgos: {str(e)}")

        return redirect('dashboard_riesgo')

    context = {
        'user_rol': user_rol,
    }
    return render(request, 'Inteligencia Art/actualizar_riesgos.html', context)