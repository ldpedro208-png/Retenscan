# core/views/estudiantes.py
# ✅ VERSIÓN COMPLETA Y CORREGIDA

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.paginator import Paginator
from django.http import HttpResponse
from django.db import transaction
from django.db.models import Q, Count, Avg, Prefetch
from django.contrib.auth.hashers import make_password

# ✅ CAMBIO: BecaEstudiante → BecaAsignacion, agregado CatalogoTipoBeca
from ..models import (
    Estudiante,
    Usuario,
    CatalogoCarrera,
    CatalogoUniversidad,
    HistorialAcademico,
    Asistencia,
    Beca,
    BecaAsignacion,
    CatalogoTipoBeca,
    RiesgoEstudiante,
    UsuarioEstudiantes,
)
# ✅ CAMBIO: BecaEstudianteForm → BecaAsignacionForm
from ..forms import (
    EstudianteForm,
    HistorialAcademicoForm,
    AsistenciaForm,
    BecaAsignacionForm,
    CargaMasivaEstudiantesForm,
)
from ..services.importador_estudiantes import ImportadorEstudiantes
from ..services.alert_service import AlertaService
from .base import (
    get_universidad_id,
    get_estudiantes_por_usuario,
    get_carreras_por_universidad,
    _get_estudiante_con_permisos,
    _mostrar_resumen_carga,
)
from ..utils import (
    generar_password_temporal,
    generar_username_desde_nombre,
    logger
)


@login_required
def estudiante_list(request):
    """
    Lista de estudiantes con búsqueda y filtros
    """
    user_rol = getattr(request.user, 'rol', 'estudiante')
    
    if user_rol == 'estudiante':
        try:
            estudiante = Estudiante.objects.get(idUsuario=request.user.id)
            return redirect('estudiante_detail', pk=estudiante.idEstudiante)
        except Estudiante.DoesNotExist:
            messages.warning(request, "No tienes un perfil de estudiante asociado.")
            return redirect('dashboard')
    
    estudiantes_qs = get_estudiantes_por_usuario(request, include_all=(user_rol == 'admin'))
    estudiantes_qs = estudiantes_qs.select_related(
        'idCarrera',
        'idCarrera__idUniversidad',
        'idUsuario'
    )
    
    search_query = request.GET.get('search', '').strip()
    if search_query:
        estudiantes_qs = estudiantes_qs.filter(
            Q(idUsuario__first_name__icontains=search_query) |
            Q(idUsuario__last_name__icontains=search_query) |
            Q(idUsuario__carnet__icontains=search_query) |
            Q(idUsuario__email__icontains=search_query)
        )
    
    carrera_filter = request.GET.get('carrera')
    if carrera_filter:
        estudiantes_qs = estudiantes_qs.filter(idCarrera_id=carrera_filter)
    
    estado_filter = request.GET.get('estado')
    if estado_filter:
        estudiantes_qs = estudiantes_qs.filter(estado_academico=estado_filter)
    
    estudiantes_qs = estudiantes_qs.order_by('idUsuario__first_name', 'idUsuario__last_name')
    
    titulos = {
        'admin': "Todos los Estudiantes",
        'tutor': "Mis Estudiantes Asignados",
        'profesor': "Estudiantes de Mis Cursos",
    }
    
    paginator = Paginator(estudiantes_qs, 20)
    page_number = request.GET.get('page', 1)
    estudiantes = paginator.get_page(page_number)
    
    carreras = CatalogoCarrera.objects.all().select_related('idUniversidad')
    
    context = {
        'estudiantes': estudiantes,
        'titulo': titulos.get(user_rol, "Estudiantes"),
        'user_rol': user_rol,
        'total_estudiantes': estudiantes_qs.count(),
        'search_query': search_query,
        'carrera_filter': carrera_filter,
        'estado_filter': estado_filter,
        'carreras': carreras,
        'estados': Estudiante.ESTADO_CHOICES,
    }
    
    return render(request, 'estudiante/estudiante_list.html', context)


@login_required
def estudiante_create(request):
    """
    Crear un nuevo estudiante (solo admin y profesor)
    ✅ Delega la creación al form.save() que maneja:
       - Contraseña automática o manual
       - Notificación por correo con la MISMA contraseña que se guarda
       - Generación de username desde nombre + apellido
    """
    user_rol = getattr(request.user, 'rol', 'estudiante')
    universidad_id = get_universidad_id(request)

    # ✅ Validación: usuario debe tener universidad
    if not universidad_id:
        if user_rol == 'admin':
            primera_universidad = CatalogoUniversidad.objects.first()
            if primera_universidad:
                request.user.idUniversidad = primera_universidad
                request.user.save()
                universidad_id = primera_universidad.idUniversidad
                messages.info(
                    request, 
                    f"Se te ha asignado automáticamente la universidad: {primera_universidad.nombre}"
                )
            else:
                messages.error(request, "Error: No hay universidades registradas en el sistema.")
                return redirect('estudiante_list')
        else:
            messages.error(request, "Error: No se encontró una universidad asociada a tu cuenta.")
            return redirect('estudiante_list')

    # ✅ Obtener nombre de universidad
    universidad_nombre = "Sin universidad asignada"
    try:
        universidad = CatalogoUniversidad.objects.get(idUniversidad=universidad_id)
        universidad_nombre = universidad.nombre
    except CatalogoUniversidad.DoesNotExist:
        messages.error(request, "Error: Universidad no encontrada.")
        return redirect('estudiante_list')

    # ✅ Validar permisos
    if user_rol not in ['admin', 'profesor']:
        messages.error(request, "No tienes permiso para crear estudiantes.")
        return redirect('estudiante_list')

    # ✅ Verificar que haya carreras disponibles
    carreras = CatalogoCarrera.objects.filter(
        idUniversidad_id=universidad_id
    ).order_by('nombre')
    
    if not carreras.exists():
        messages.warning(
            request, 
            "No hay carreras registradas en tu universidad. "
            "Crea una carrera primero antes de registrar estudiantes."
        )
        return redirect('carrera_create')

    # ✅ Manejar POST
    if request.method == 'POST':
        form = EstudianteForm(request.POST, request.FILES)
        
        if form.is_valid():
            try:
                with transaction.atomic():
                    # ✅ Guardar estudiante usando form.save()
                    estudiante = form.save(commit=True, request=request)
                    
                    # ✅ Asegurar universidad asignada (por si acaso)
                    if not estudiante.idUsuario.idUniversidad_id:
                        estudiante.idUsuario.idUniversidad_id = universidad_id
                        estudiante.idUsuario.save()
                    
                    if not estudiante.idUniversidad_id:
                        estudiante.idUniversidad_id = universidad_id
                        estudiante.save()
                    
                    messages.success(
                        request,
                        f"✅ Estudiante '{estudiante.idUsuario.get_full_name()}' creado exitosamente "
                        f"con username: @{estudiante.idUsuario.username}. "
                        f"Universidad: {universidad_nombre}"
                    )
                    return redirect('estudiante_detail', pk=estudiante.idEstudiante)

            except Exception as e:
                logger.error(f"Error creando estudiante: {str(e)}", exc_info=True)
                messages.error(request, f"Error al crear el estudiante: {str(e)}")
                context = {
                    'form': form,
                    'carreras': carreras,
                    'user_rol': user_rol,
                    'titulo': 'Registrar Estudiante',
                    'universidad_nombre': universidad_nombre,
                    'es_creacion': True,
                }
                return render(request, 'estudiante/estudiante_form.html', context)
        else:
            # ✅ Formulario con errores
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f"{field}: {error}")
            
            context = {
                'form': form,
                'carreras': carreras,
                'user_rol': user_rol,
                'titulo': 'Registrar Estudiante',
                'universidad_nombre': universidad_nombre,
                'es_creacion': True,
            }
            return render(request, 'estudiante/estudiante_form.html', context)

    # ✅ GET: Mostrar formulario vacío
    form = EstudianteForm()
    form.fields['idCarrera'].queryset = carreras
    
    context = {
        'form': form,
        'carreras': carreras,
        'user_rol': user_rol,
        'titulo': 'Registrar Estudiante',
        'universidad_nombre': universidad_nombre,
        'es_creacion': True,
    }
    return render(request, 'estudiante/estudiante_form.html', context)


@login_required
def estudiante_detail(request, pk):
    user_rol = getattr(request.user, 'rol', 'estudiante')
    universidad_id = get_universidad_id(request)

    if user_rol == 'estudiante':
        try:
            mi_estudiante = Estudiante.objects.get(idUsuario=request.user.id)
            if mi_estudiante.idEstudiante != pk:
                messages.error(request, "No tienes permiso para ver este perfil.")
                return redirect('dashboard')
        except Estudiante.DoesNotExist:
            messages.warning(request, "No tienes un perfil de estudiante asociado.")
            return redirect('dashboard')

    estudiante = _get_estudiante_con_permisos(pk, user_rol, universidad_id, request.user)
    if not estudiante:
        return redirect('dashboard')

    historial = HistorialAcademico.objects.filter(idEstudiante=estudiante).select_related('idMateria')
    asistencias = Asistencia.objects.filter(idEstudiante=estudiante).select_related('idAula')[:10]

    # ✅ CAMBIO: usar BecaAsignacion con estado='Activa'
    becas = BecaAsignacion.objects.filter(
        idEstudiante=estudiante,
        estado='Activa'
    ).select_related('idBeca', 'idBeca__tipo')

    tiene_riesgo = RiesgoEstudiante.objects.filter(
        idEstudiante=estudiante,
        estado='Activo'
    ).exists()

    puede_editar = user_rol == 'admin'
    puede_editar_notas = user_rol in ['admin', 'tutor', 'profesor']
    puede_registrar_asistencia = user_rol in ['admin', 'profesor']
    puede_ver_riesgos = user_rol == 'admin'

    context = {
        'estudiante': estudiante,
        'usuario': estudiante.idUsuario,
        'historial': historial,
        'asistencias': asistencias,
        'becas': becas,
        'puede_editar': puede_editar,
        'puede_editar_notas': puede_editar_notas,
        'puede_registrar_asistencia': puede_registrar_asistencia,
        'puede_ver_riesgos': puede_ver_riesgos,
        'puede_ver_acciones': user_rol in ['admin', 'tutor', 'profesor'],
        'user_rol': user_rol,
        'tiene_riesgo': tiene_riesgo,
        'es_mi_perfil': user_rol == 'estudiante',
    }
    return render(request, 'estudiante/estudiante_detail.html', context)


@login_required
def estudiante_edit(request, pk):
    """
    Editar un estudiante existente (solo admin y profesor con permisos)
    ✅ Usa form.save() que maneja la actualización correctamente
    ✅ El username NO se modifica al editar
    """
    user_rol = getattr(request.user, 'rol', 'estudiante')
    universidad_id = get_universidad_id(request)

    if user_rol not in ['admin', 'profesor']:
        messages.error(request, "No tienes permiso para editar estudiantes.")
        return redirect('estudiante_list')

    if not universidad_id:
        messages.error(request, "Error: No se encontró una universidad asociada a tu cuenta.")
        return redirect('estudiante_list')

    estudiante = _get_estudiante_con_permisos(pk, user_rol, universidad_id, request.user)
    if not estudiante:
        messages.error(request, "No tienes permiso para editar este estudiante o no existe.")
        return redirect('estudiante_list')

    if estudiante.idUsuario.idUniversidad_id != universidad_id:
        messages.error(request, "No puedes editar estudiantes de otra universidad.")
        return redirect('estudiante_list')

    universidad_nombre = "Sin universidad"
    try:
        universidad = CatalogoUniversidad.objects.get(idUniversidad=universidad_id)
        universidad_nombre = universidad.nombre
    except CatalogoUniversidad.DoesNotExist:
        pass

    carreras = CatalogoCarrera.objects.filter(
        idUniversidad_id=universidad_id
    ).order_by('nombre')

    if not carreras.exists():
        messages.warning(request, "No hay carreras registradas en tu universidad.")
        return redirect('carrera_create')

    if request.method == 'POST':
        form = EstudianteForm(request.POST, request.FILES, instance=estudiante)
        
        if form.is_valid():
            try:
                with transaction.atomic():
                    # ✅ Validar que la carrera pertenezca a la universidad
                    carrera = form.cleaned_data.get('idCarrera')
                    if carrera and carrera.idUniversidad_id != universidad_id:
                        messages.error(request, "La carrera seleccionada no pertenece a tu universidad.")
                        context = {
                            'form': form,
                            'carreras': carreras,
                            'user_rol': user_rol,
                            'titulo': 'Editar Estudiante',
                            'universidad_nombre': universidad_nombre,
                            'estudiante': estudiante,
                            'es_creacion': False,
                        }
                        return render(request, 'estudiante/estudiante_form.html', context)

                    # ✅ Guardar usando form.save() que maneja TODO
                    estudiante = form.save(commit=True, request=request)

                    messages.success(
                        request,
                        f"✅ Estudiante '{estudiante.idUsuario.get_full_name()}' actualizado exitosamente."
                    )
                    return redirect('estudiante_detail', pk=estudiante.idEstudiante)

            except Exception as e:
                logger.error(f"Error editando estudiante: {str(e)}", exc_info=True)
                messages.error(request, f"Error al editar el estudiante: {str(e)}")
                context = {
                    'form': form,
                    'carreras': carreras,
                    'user_rol': user_rol,
                    'titulo': 'Editar Estudiante',
                    'universidad_nombre': universidad_nombre,
                    'estudiante': estudiante,
                    'es_creacion': False,
                }
                return render(request, 'estudiante/estudiante_form.html', context)
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f"{field}: {error}")
            
            context = {
                'form': form,
                'carreras': carreras,
                'user_rol': user_rol,
                'titulo': 'Editar Estudiante',
                'universidad_nombre': universidad_nombre,
                'estudiante': estudiante,
                'es_creacion': False,
            }
            return render(request, 'estudiante/estudiante_form.html', context)

    # ✅ GET: Cargar formulario con datos actuales
    form = EstudianteForm(instance=estudiante)
    form.fields['idCarrera'].queryset = carreras
    
    context = {
        'user_rol': user_rol,
        'carreras': carreras,
        'form': form,
        'titulo': 'Editar Estudiante',
        'universidad_nombre': universidad_nombre,
        'estudiante': estudiante,
        'es_creacion': False,
    }
    return render(request, 'estudiante/estudiante_form.html', context)


@login_required
def estudiante_delete(request, pk):
    """Eliminar un estudiante (solo admin)"""
    user_rol = getattr(request.user, 'rol', 'estudiante')
    universidad_id = get_universidad_id(request)
    
    if user_rol != 'admin':
        messages.error(request, "No tienes permiso para eliminar estudiantes.")
        return redirect('estudiante_list')
    
    estudiante = get_object_or_404(
        Estudiante.objects.select_related('idCarrera', 'idUsuario'),
        pk=pk,
        idCarrera__idUniversidad_id=universidad_id
    )
    
    if request.method == 'POST':
        nombre_estudiante = estudiante.nombre_completo
        carnet = estudiante.carnet
        estudiante.delete()
        
        messages.success(
            request, 
            f"✅ Estudiante '{nombre_estudiante}' ({carnet}) eliminado exitosamente."
        )
        return redirect('estudiante_list')
    
    context = {
        'estudiante': estudiante,
        'user_rol': user_rol,
        'titulo': 'Eliminar Estudiante',
    }
    return render(request, 'estudiante/estudiante_confirm_delete.html', context)


@login_required
def historial_add(request, estudiante_id):
    user_rol = getattr(request.user, 'rol', 'estudiante')
    universidad_id = get_universidad_id(request)

    if user_rol not in ['admin', 'tutor', 'profesor']:
        messages.error(request, "No tienes permiso para agregar notas.")
        return redirect('estudiante_detail', pk=estudiante_id)

    estudiante = _get_estudiante_con_permisos(estudiante_id, user_rol, universidad_id, request.user)
    if not estudiante:
        return redirect('dashboard')

    if user_rol == 'tutor':
        es_asignado = UsuarioEstudiantes.objects.filter(
            usuario_id=request.user.id,
            estudiante_id=estudiante.idEstudiante
        ).exists()
        if not es_asignado:
            messages.error(request, "No tienes permiso para agregar notas a este estudiante.")
            return redirect('dashboard')

    if request.method == 'POST':
        form = HistorialAcademicoForm(request.POST)
        if form.is_valid():
            try:
                with transaction.atomic():
                    historial = form.save(commit=False)
                    historial.idEstudiante = estudiante
                    historial.save()
                    messages.success(request, 'Historial académico agregado.')
                    return redirect('estudiante_detail', pk=estudiante.idEstudiante)
            except Exception as e:
                messages.error(request, f"Error al guardar: {str(e)}")
                estudiante.refresh_from_db()
    else:
        form = HistorialAcademicoForm()

    return render(request, 'estudiante/historial_form.html', {
        'form': form,
        'estudiante': estudiante
    })


@login_required
def asistencia_add(request, estudiante_id):
    user_rol = getattr(request.user, 'rol', 'estudiante')
    universidad_id = get_universidad_id(request)

    if user_rol not in ['admin', 'profesor']:
        messages.error(request, "No tienes permiso para registrar asistencia.")
        return redirect('estudiante_detail', pk=estudiante_id)

    estudiante = _get_estudiante_con_permisos(estudiante_id, user_rol, universidad_id, request.user)
    if not estudiante:
        return redirect('dashboard')

    if request.method == 'POST':
        form = AsistenciaForm(request.POST)
        if form.is_valid():
            try:
                with transaction.atomic():
                    asistencia = form.save(commit=False)
                    asistencia.idEstudiante = estudiante
                    asistencia.save()
                    messages.success(request, '✅ Asistencia registrada exitosamente.')
                    return redirect('estudiante_detail', pk=estudiante.idEstudiante)
            except Exception as e:
                messages.error(request, f"Error al guardar la asistencia: {str(e)}")
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f"{field}: {error}")
    else:
        form = AsistenciaForm()

    return render(request, 'estudiante/asistencia_form.html', {
        'form': form,
        'estudiante': estudiante
    })


@login_required
def estudiante_riesgos(request, pk):
    """Ver los riesgos de un estudiante específico"""
    user_rol = getattr(request.user, 'rol', 'estudiante')
    universidad_id = get_universidad_id(request)

    if user_rol != 'admin':
        messages.error(request, "No tienes permiso para ver riesgos.")
        return redirect('dashboard')

    estudiante = _get_estudiante_con_permisos(pk, user_rol, universidad_id, request.user)
    if not estudiante:
        return redirect('dashboard')

    riesgos = RiesgoEstudiante.objects.filter(
        idEstudiante=estudiante
    ).select_related('idFactor').order_by('-fecha_deteccion')

    context = {
        'estudiante': estudiante,
        'riesgos': riesgos,
        'user_rol': user_rol,
    }
    return render(request, 'estudiante/estudiante_riesgos.html', context)


@login_required
def beca_add(request, estudiante_id):
    """Asignar una beca a un estudiante."""
    user_rol = getattr(request.user, 'rol', 'estudiante')

    if user_rol != 'admin':
        messages.error(request, "No tienes permiso para asignar becas.")
        return redirect('estudiante_detail', pk=estudiante_id)

    universidad_id = get_universidad_id(request)
    estudiante = _get_estudiante_con_permisos(estudiante_id, user_rol, universidad_id, request.user)

    if not estudiante:
        return redirect('dashboard')

    if request.method == 'POST':
        # ✅ CAMBIO: BecaEstudianteForm → BecaAsignacionForm
        form = BecaAsignacionForm(request.POST)
        if form.is_valid():
            beca_asignacion = form.save(commit=False)
            beca_asignacion.idEstudiante = estudiante
            beca_asignacion.save()
            messages.success(request, 'Beca asignada exitosamente.')
            return redirect('estudiante_detail', pk=estudiante.idEstudiante)
    else:
        # ✅ CAMBIO: BecaEstudianteForm → BecaAsignacionForm
        form = BecaAsignacionForm()

    return render(request, 'universidad/beca_form.html', {
        'form': form,
        'estudiante': estudiante
    })


@login_required
def carga_masiva(request):
    user_rol = getattr(request.user, 'rol', 'estudiante')

    if user_rol != 'admin':
        messages.error(request, "No tienes permiso para realizar carga masiva.")
        return redirect('dashboard')

    if request.method == 'POST':
        form = CargaMasivaEstudiantesForm(request.POST, request.FILES)
        if form.is_valid():
            archivo = request.FILES['archivo']
            crear_usuarios = form.cleaned_data['opcion_crear_usuarios']
            actualizar = form.cleaned_data['opcion_actualizar']

            universidad = getattr(request.user, 'idUniversidad', None)

            if universidad is None:
                universidad = CatalogoUniversidad.objects.first()
                if universidad is not None:
                    logger.warning(
                        f"⚠️ Admin {request.user.username} no tiene universidad. "
                        f"Usando: {universidad.nombre}"
                    )

            if universidad is None:
                messages.error(
                    request,
                    "❌ No hay universidades registradas. "
                    "Crea una universidad antes de importar estudiantes."
                )
                return render(request, 'estudiante/carga_masiva.html', {'form': form})

            importador = ImportadorEstudiantes(
                archivo=archivo,
                universidad=universidad,
                usuario=request.user,
                crear_usuarios=crear_usuarios,
                actualizar_existentes=actualizar,
            )

            importador.procesar()
            resumen = importador.get_resumen()

            _mostrar_resumen_carga(request, resumen)
            request.session['carga_resumen'] = resumen
            return redirect('carga_masiva_resultado')
    else:
        form = CargaMasivaEstudiantesForm()

    return render(request, 'estudiante/carga_masiva.html', {'form': form})


@login_required
def carga_masiva_resultado(request):
    user_rol = getattr(request.user, 'rol', 'estudiante')

    if user_rol != 'admin':
        return redirect('dashboard')

    resumen = request.session.get('carga_resumen')
    if not resumen:
        return redirect('carga_masiva')

    del request.session['carga_resumen']
    return render(request, 'estudiante/carga_masiva_resultado.html', {'resumen': resumen})


@login_required
def descargar_plantilla(request):
    user_rol = getattr(request.user, 'rol', 'estudiante')

    if user_rol != 'admin':
        messages.error(request, "No tienes permiso para descargar la plantilla.")
        return redirect('dashboard')

    import pandas as pd

    data = {
        'nombre': ['Juan', 'María', 'Carlos'],
        'apellido_paterno': ['Pérez', 'González', 'López'],
        'apellido_materno': ['Ramírez', 'Martínez', 'Sánchez'],
        'carnet': ['2024-001', '2024-002', '2024-003'],
        'email': ['juan@email.com', 'maria@email.com', 'carlos@email.com'],
        'telefono': ['555-1234', '555-5678', '555-9012'],
        'carrera': ['Ingeniería de Sistemas', 'Administración de Empresas', 'Psicología'],
        'codigo_carrera': ['ING-SIS-2024', 'ADM-EMP-2024', 'PSI-2024'],
        'ano_ingreso': [2024, 2024, 2024],
        'semestre_actual': [1, 1, 1],
        'genero': ['M', 'F', 'M'],
        'fecha_nacimiento': ['2000-01-15', '2001-05-20', '1999-12-10'],
        'nacionalidad': ['Boliviana', 'Colombiana', 'Peruana'],
        'direccion': ['Calle 1 #123', 'Av. Principal #456', 'Calle 5 #789'],
        'telefono_emergencia': ['555-4321', '555-8765', '555-2109'],
        'contacto_emergencia': ['Ana Pérez', 'Luis González', 'Rosa Sánchez'],
        'estado': ['Activo', 'Activo', 'Activo'],
        'materia_1': ['Matemáticas I', 'Contabilidad I', 'Psicología General'],
        'nota_1': [15, 18, 14],
        'materia_2': ['Programación I', 'Economía I', 'Neurociencia'],
        'nota_2': [12, 16, 11],
        'semestre_historial': ['2024-1', '2024-1', '2024-1']
    }

    df = pd.DataFrame(data)
    response = HttpResponse(
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = 'attachment; filename=plantilla_estudiantes.xlsx'
    df.to_excel(response, index=False, sheet_name='Estudiantes')

    return response


# ============================================
# FUNCIÓN AUXILIAR
# ============================================

def _crear_usuario_estudiante(estudiante, universidad_id):
    """
    Crea el usuario asociado a un estudiante.
    ✅ Genera username desde nombre + apellido
    ✅ Usa set_password() en lugar de make_password()
    """
    from ..services.alert_service import AlertaService
    from ..models import Usuario
    
    password_temporal = generar_password_temporal()
    
    try:
        username = generar_username_desde_nombre(
            estudiante.nombre,
            estudiante.apellido_paterno
        )
    except ValueError:
        username = estudiante.carnet.lower()
        base_username = username
        counter = 1
        while Usuario.objects.filter(username=username).exists():
            username = f"{base_username}{counter}"
            counter += 1

    usuario = Usuario(
        username=username,
        email=estudiante.email,
        first_name=estudiante.nombre,
        last_name=f"{estudiante.apellido_paterno} {estudiante.apellido_materno}",
        rol='estudiante',
        is_active=True,
        carnet=estudiante.carnet,
        genero=estudiante.genero,
        telefono=estudiante.telefono,
        fecha_nacimiento=estudiante.fecha_nacimiento,
        cambiar_password=True,
        notificaciones_email=True,
        whatsapp_telefono=estudiante.telefono or '',
        idUniversidad_id=universidad_id,
    )
    
    usuario.set_password(password_temporal)
    usuario.save()

    estudiante.idUsuario = usuario
    estudiante.save()

    try:
        AlertaService.notificar_credenciales(
            usuario=usuario, 
            password_temporal=password_temporal, 
            es_primera_vez=True
        )
    except Exception as e:
        logger.error(f"Error enviando credenciales: {str(e)}")
    
    return usuario