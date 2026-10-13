# core/views/exportaciones.py - VERSIÓN CORREGIDA

"""
Vistas para exportación de datos en múltiples formatos
Soporta: CSV, Excel, PDF, JSON
"""
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.http import HttpResponse, JsonResponse
from django.db.models import Count, Avg, Sum, Q, Max, Min
from django.utils import timezone
from datetime import datetime, timedelta
import json
import csv
from io import BytesIO, StringIO
import xlsxwriter

# ============================================
# IMPORTACIÓN OPCIONAL DE REPORTLAB
# ============================================
try:
    from reportlab.lib.pagesizes import letter, landscape, A4
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image, PageBreak
    from reportlab.lib import colors
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import inch, cm
    from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
    from reportlab.pdfgen import canvas
    REPORTLAB_AVAILABLE = True
except ImportError:
    REPORTLAB_AVAILABLE = False

# ============================================
# IMPORTACIÓN DE MODELOS
# ============================================
# ✅ CAMBIO: Carrera, Materia, Aula → CatalogoCarrera, CatalogoMateria, CatalogoAula
from ..models import (
    Estudiante, Usuario, CatalogoCarrera, CatalogoMateria, CatalogoAula,
    Beca, BecaAsignacion, Alerta, Intervencion,
    CatalogoUniversidad, Asistencia, HistorialAcademico,
    Notificacion, RiesgoEstudiante,
)

# ✅ Importar Auditoria solo si existe
try:
    from ..models import Auditoria
    AUDITORIA_DISPONIBLE = True
except ImportError:
    AUDITORIA_DISPONIBLE = False

from .base import get_universidad_id, logger


# ============================================
# SECCIÓN 1: PANEL PRINCIPAL
# ============================================

@login_required
def exportaciones_index(request):
    """
    Panel principal de exportaciones
    """
    user_rol = request.user.rol

    if user_rol != 'admin':
        messages.error(request, "No tienes permiso para acceder a exportaciones.")
        return redirect('dashboard')

    universidad_id = get_universidad_id(request)
    universidad = request.user.idUniversidad if not request.user.is_superuser else None

    # Obtener estadísticas para el panel
    # ✅ CAMBIO: Materia → CatalogoMateria, filtrar por idCarrera__idUniversidad
    stats = {
        'total_estudiantes': Estudiante.objects.filter(idUniversidad_id=universidad_id).count() if universidad_id else Estudiante.objects.count(),
        'total_usuarios': Usuario.objects.filter(idUniversidad_id=universidad_id).count() if universidad_id else Usuario.objects.count(),
        'total_materias': CatalogoMateria.objects.filter(idCarrera__idUniversidad_id=universidad_id).count() if universidad_id else CatalogoMateria.objects.count(),
        'total_becas': Beca.objects.filter(idUniversidad_id=universidad_id).count() if universidad_id else Beca.objects.count(),
        'total_alertas': Alerta.objects.filter(idEstudiante__idUniversidad_id=universidad_id).count() if universidad_id else Alerta.objects.count(),
    }

    # Tipos de exportación disponibles
    tipos_exportacion = [
        {'id': 'estudiantes', 'nombre': 'Estudiantes', 'icono': 'bi-people', 'color': 'primary'},
        {'id': 'usuarios', 'nombre': 'Usuarios', 'icono': 'bi-person-badge', 'color': 'success'},
        {'id': 'materias', 'nombre': 'Materias', 'icono': 'bi-book', 'color': 'info'},
        {'id': 'carreras', 'nombre': 'Carreras', 'icono': 'bi-mortarboard', 'color': 'warning'},
        {'id': 'becas', 'nombre': 'Becas', 'icono': 'bi-award', 'color': 'secondary'},
        {'id': 'asistencias', 'nombre': 'Asistencias', 'icono': 'bi-calendar-check', 'color': 'success'},
        {'id': 'alertas', 'nombre': 'Alertas', 'icono': 'bi-exclamation-triangle', 'color': 'danger'},
        {'id': 'intervenciones', 'nombre': 'Intervenciones', 'icono': 'bi-chat-dots', 'color': 'info'},
        {'id': 'historial', 'nombre': 'Historial Académico', 'icono': 'bi-journal', 'color': 'primary'},
        {'id': 'auditoria', 'nombre': 'Auditoría', 'icono': 'bi-clock-history', 'color': 'dark'},
        {'id': 'estadisticas', 'nombre': 'Estadísticas', 'icono': 'bi-graph-up', 'color': 'purple'},
        {'id': 'riesgos', 'nombre': 'Riesgos', 'icono': 'bi-exclamation-diamond', 'color': 'danger'},
    ]

    # Formatos disponibles
    formatos = [
        {'id': 'csv', 'nombre': 'CSV', 'icono': 'bi-filetype-csv'},
        {'id': 'excel', 'nombre': 'Excel', 'icono': 'bi-file-earmark-excel'},
        {'id': 'pdf', 'nombre': 'PDF', 'icono': 'bi-filetype-pdf', 'disponible': REPORTLAB_AVAILABLE},
        {'id': 'json', 'nombre': 'JSON', 'icono': 'bi-filetype-json'},
    ]

    context = {
        'stats': stats,
        'tipos_exportacion': tipos_exportacion,
        'formatos': formatos,
        'universidad': universidad,
        'user_rol': user_rol,
        'is_superuser': request.user.is_superuser,
        'fecha_actual': timezone.now(),
        'reportlab_disponible': REPORTLAB_AVAILABLE,
    }

    return render(request, 'exportaciones/exportaciones_index.html', context)


# ============================================
# SECCIÓN 2: ROUTER DE EXPORTACIÓN
# ============================================

@login_required
def exportar_datos(request, tipo, formato):
    """
    Router principal para exportar datos según tipo y formato
    """
    user_rol = request.user.rol

    if user_rol != 'admin':
        messages.error(request, "No tienes permiso para exportar datos.")
        return redirect('dashboard')

    universidad_id = get_universidad_id(request)

    # Mapeo de tipos a funciones
    exportadores = {
        'estudiantes': exportar_estudiantes,
        'usuarios': exportar_usuarios,
        'materias': exportar_materias,
        'carreras': exportar_carreras,
        'becas': exportar_becas,
        'asistencias': exportar_asistencias,
        'alertas': exportar_alertas,
        'intervenciones': exportar_intervenciones,
        'historial': exportar_historial,
        'auditoria': exportar_auditoria,
        'estadisticas': exportar_estadisticas_universidad,
        'riesgos': exportar_riesgos,
    }

    if tipo not in exportadores:
        messages.error(request, f"Tipo de exportación '{tipo}' no válido.")
        return redirect('exportaciones_index')

    # Ejecutar el exportador correspondiente
    return exportadores[tipo](request, formato, universidad_id)


# ============================================
# SECCIÓN 3: EXPORTADORES POR TIPO DE DATOS
# ============================================

def exportar_estudiantes(request, formato, universidad_id):
    """Exportar estudiantes"""
    if request.user.is_superuser:
        estudiantes = Estudiante.objects.all().select_related('idUsuario', 'idCarrera')
    else:
        estudiantes = Estudiante.objects.filter(idUniversidad_id=universidad_id).select_related('idUsuario', 'idCarrera')

    estado = request.GET.get('estado', '')
    if estado:
        estudiantes = estudiantes.filter(estado_academico=estado)

    carrera = request.GET.get('carrera', '')
    if carrera:
        estudiantes = estudiantes.filter(idCarrera__nombre__icontains=carrera)

    data = []
    for est in estudiantes:
        data.append({
            'Carnet': est.carnet,
            'Nombre Completo': est.nombre_completo,
            'Email': est.email,
            'Teléfono': est.telefono,
            'Carrera': est.idCarrera.nombre if est.idCarrera else 'Sin carrera',
            'Semestre': est.semestre_actual,
            'Estado': est.estado_academico,
            'Promedio': float(est.promedio_general or 0),
            'Asistencia %': float(est.porcentaje_asistencia or 0),
            'Compromiso': float(est.indice_compromiso or 0),
            'Bienestar': float(est.indice_bienestar or 0),
            'Fecha Registro': est.created_at.strftime('%Y-%m-%d %H:%M') if est.created_at else '',
        })

    titulo = "Estudiantes"
    headers = list(data[0].keys()) if data else []

    return generar_exportacion(data, titulo, formato, headers)


def exportar_usuarios(request, formato, universidad_id):
    """Exportar usuarios"""
    if request.user.is_superuser:
        usuarios = Usuario.objects.all()
    else:
        usuarios = Usuario.objects.filter(idUniversidad_id=universidad_id)

    rol = request.GET.get('rol', '')
    if rol:
        usuarios = usuarios.filter(rol=rol)

    data = []
    for user in usuarios:
        data.append({
            'Username': user.username,
            'Nombre': user.first_name,
            'Apellido': user.last_name,
            'Email': user.email,
            'Carnet': user.carnet,
            'Rol': user.get_rol_display(),
            'Teléfono': user.telefono or '',
            'Activo': 'Sí' if user.is_active else 'No',
            'Último Login': user.last_login.strftime('%Y-%m-%d %H:%M') if user.last_login else '',
            'Fecha Registro': user.date_joined.strftime('%Y-%m-%d %H:%M') if user.date_joined else '',
        })

    titulo = "Usuarios"
    headers = list(data[0].keys()) if data else []

    return generar_exportacion(data, titulo, formato, headers)


def exportar_materias(request, formato, universidad_id):
    """Exportar materias"""
    # ✅ CAMBIO: CatalogoMateria + select_related idCarrera__idUniversidad
    if request.user.is_superuser:
        materias = CatalogoMateria.objects.all().select_related('idCarrera__idUniversidad')
    else:
        materias = CatalogoMateria.objects.filter(
            idCarrera__idUniversidad_id=universidad_id
        ).select_related('idCarrera__idUniversidad')

    data = []
    for mat in materias:
        data.append({
            'Código': mat.codigo or '',
            'Nombre': mat.nombre,
            'Créditos': mat.creditos,
            'Semestre': mat.semestre_curricular or '',
            'Carrera': mat.idCarrera.nombre if mat.idCarrera else '',
            'Universidad': mat.idCarrera.idUniversidad.nombre if mat.idCarrera and mat.idCarrera.idUniversidad else '',
            'Fecha Creación': mat.created_at.strftime('%Y-%m-%d') if mat.created_at else '',
        })

    titulo = "Materias"
    headers = list(data[0].keys()) if data else []

    return generar_exportacion(data, titulo, formato, headers)


def exportar_carreras(request, formato, universidad_id):
    """Exportar carreras"""
    # ✅ CAMBIO: CatalogoCarrera
    if request.user.is_superuser:
        carreras = CatalogoCarrera.objects.all().select_related('idUniversidad')
    else:
        carreras = CatalogoCarrera.objects.filter(idUniversidad_id=universidad_id).select_related('idUniversidad')

    data = []
    for car in carreras:
        data.append({
            'Código': car.codigo or '',
            'Nombre': car.nombre,
            'Duración (años)': car.duracion,
            'Descripción': car.descripcion or '',
            'Universidad': car.idUniversidad.nombre if car.idUniversidad else '',
            # ✅ CAMBIO: ahora cuenta materias vía related_name materias_catalogo
            'Materias': car.materias_catalogo.count(),
            'Fecha Creación': car.created_at.strftime('%Y-%m-%d') if car.created_at else '',
        })

    titulo = "Carreras"
    headers = list(data[0].keys()) if data else []

    return generar_exportacion(data, titulo, formato, headers)


def exportar_becas(request, formato, universidad_id):
    """Exportar becas"""
    if request.user.is_superuser:
        becas = Beca.objects.all().select_related('idUniversidad')
    else:
        becas = Beca.objects.filter(idUniversidad_id=universidad_id).select_related('idUniversidad')

    tipo = request.GET.get('tipo', '')
    if tipo:
        becas = becas.filter(tipo=tipo)

    estado = request.GET.get('estado', '')
    if estado:
        becas = becas.filter(estado=estado)

    data = []
    for beca in becas:
        data.append({
            'Código': beca.codigo,
            'Nombre': beca.nombre,
            'Tipo': beca.tipo,
            'Monto': float(beca.monto),
            'Cobertura %': float(beca.porcentaje_cobertura or 0),
            'Duración (meses)': beca.duracion_meses,
            'Cupos': beca.cupos_disponibles,
            'Estado': beca.estado,
            'Asignados': beca.becaasignacion_set.count(),
            'Universidad': beca.idUniversidad.nombre if beca.idUniversidad else '',
            'Fecha Inicio': beca.fecha_inicio.strftime('%Y-%m-%d') if beca.fecha_inicio else '',
            'Fecha Fin': beca.fecha_fin.strftime('%Y-%m-%d') if beca.fecha_fin else '',
        })

    titulo = "Becas"
    headers = list(data[0].keys()) if data else []

    return generar_exportacion(data, titulo, formato, headers)


def exportar_asistencias(request, formato, universidad_id):
    """Exportar asistencias"""
    if request.user.is_superuser:
        estudiantes = Estudiante.objects.all()
    else:
        estudiantes = Estudiante.objects.filter(idUniversidad_id=universidad_id)

    asistencias = Asistencia.objects.filter(
        idEstudiante__in=estudiantes
    ).select_related('idEstudiante', 'idEstudiante__idUsuario', 'idMateria')

    fecha_inicio = request.GET.get('fecha_inicio', '')
    fecha_fin = request.GET.get('fecha_fin', '')

    if fecha_inicio:
        try:
            fecha_inicio_dt = datetime.strptime(fecha_inicio, '%Y-%m-%d')
            asistencias = asistencias.filter(fecha__gte=fecha_inicio_dt)
        except ValueError:
            pass

    if fecha_fin:
        try:
            fecha_fin_dt = datetime.strptime(fecha_fin, '%Y-%m-%d')
            asistencias = asistencias.filter(fecha__lte=fecha_fin_dt)
        except ValueError:
            pass

    data = []
    for asc in asistencias:
        data.append({
            'Estudiante': asc.idEstudiante.nombre_completo,
            'Carnet': asc.idEstudiante.carnet,
            'Materia': asc.idMateria.nombre if asc.idMateria else '',
            'Fecha': asc.fecha.strftime('%Y-%m-%d') if asc.fecha else '',
            'Presente': 'Sí' if asc.presente else 'No',
            'Justificación': asc.justificacion or '',
            'Hora Entrada': asc.hora_entrada.strftime('%H:%M') if asc.hora_entrada else '',
            'Hora Salida': asc.hora_salida.strftime('%H:%M') if asc.hora_salida else '',
        })

    titulo = "Asistencias"
    headers = list(data[0].keys()) if data else []

    return generar_exportacion(data, titulo, formato, headers)


def exportar_alertas(request, formato, universidad_id):
    """Exportar alertas"""
    if request.user.is_superuser:
        alertas = Alerta.objects.all().select_related('idEstudiante', 'idEstudiante__idUsuario', 'idFactor')
    else:
        alertas = Alerta.objects.filter(
            idEstudiante__idUniversidad_id=universidad_id
        ).select_related('idEstudiante', 'idEstudiante__idUsuario', 'idFactor')

    nivel = request.GET.get('nivel', '')
    if nivel:
        alertas = alertas.filter(nivel=nivel)

    estado = request.GET.get('estado', '')
    if estado:
        alertas = alertas.filter(estado=estado)

    data = []
    for alerta in alertas:
        data.append({
            'Estudiante': alerta.idEstudiante.nombre_completo,
            'Carnet': alerta.idEstudiante.carnet,
            'Nivel': alerta.nivel,
            'Estado': alerta.estado,
            'Factor': alerta.idFactor.nombre if alerta.idFactor else '',
            'Descripción': alerta.descripcion[:100] + '...' if len(alerta.descripcion) > 100 else alerta.descripcion,
            'Fecha Detección': alerta.fecha_deteccion.strftime('%Y-%m-%d %H:%M') if alerta.fecha_deteccion else '',
            'Fecha Atención': alerta.fecha_atencion.strftime('%Y-%m-%d %H:%M') if alerta.fecha_atencion else '',
        })

    titulo = "Alertas"
    headers = list(data[0].keys()) if data else []

    return generar_exportacion(data, titulo, formato, headers)


def exportar_intervenciones(request, formato, universidad_id):
    """Exportar intervenciones"""
    if request.user.is_superuser:
        intervenciones = Intervencion.objects.all().select_related('idEstudiante', 'idEstudiante__idUsuario', 'responsable')
    else:
        intervenciones = Intervencion.objects.filter(
            idEstudiante__idUniversidad_id=universidad_id
        ).select_related('idEstudiante', 'idEstudiante__idUsuario', 'responsable')

    data = []
    for inv in intervenciones:
        data.append({
            'Estudiante': inv.idEstudiante.nombre_completo,
            'Carnet': inv.idEstudiante.carnet,
            'Tipo': inv.tipo_intervencion,
            'Estado': inv.estado,
            'Descripción': inv.descripcion[:100] + '...' if len(inv.descripcion) > 100 else inv.descripcion,
            'Fecha Programada': inv.fecha_programada.strftime('%Y-%m-%d %H:%M') if inv.fecha_programada else '',
            'Fecha Realizada': inv.fecha_realizada.strftime('%Y-%m-%d %H:%M') if inv.fecha_realizada else '',
            'Efectiva': 'Sí' if inv.efectiva else 'No',
            'Responsable': inv.responsable.nombre_completo if inv.responsable else '',
        })

    titulo = "Intervenciones"
    headers = list(data[0].keys()) if data else []

    return generar_exportacion(data, titulo, formato, headers)


def exportar_historial(request, formato, universidad_id):
    """Exportar historial académico"""
    if request.user.is_superuser:
        historial = HistorialAcademico.objects.all().select_related('idEstudiante', 'idEstudiante__idUsuario', 'idMateria')
    else:
        historial = HistorialAcademico.objects.filter(
            idEstudiante__idUniversidad_id=universidad_id
        ).select_related('idEstudiante', 'idEstudiante__idUsuario', 'idMateria')

    data = []
    for hist in historial:
        data.append({
            'Estudiante': hist.idEstudiante.nombre_completo,
            'Carnet': hist.idEstudiante.carnet,
            'Materia': hist.idMateria.nombre if hist.idMateria else '',
            'Semestre': hist.semestre,
            'Nota Final': float(hist.nota_final or 0),
            'Estado': hist.estado_materia,
            'Intentos': hist.intentos,
            'Fecha Inscripción': hist.fecha_inscripcion.strftime('%Y-%m-%d') if hist.fecha_inscripcion else '',
            'Fecha Aprobación': hist.fecha_aprobacion.strftime('%Y-%m-%d') if hist.fecha_aprobacion else '',
        })

    titulo = "Historial Académico"
    headers = list(data[0].keys()) if data else []

    return generar_exportacion(data, titulo, formato, headers)


def exportar_auditoria(request, formato, universidad_id):
    """Exportar registros de auditoría"""
    if not AUDITORIA_DISPONIBLE:
        data = []
        usuarios = Usuario.objects.filter(idUniversidad_id=universidad_id) if universidad_id else Usuario.objects.all()

        for user in usuarios[:50]:
            data.append({
                'ID': user.id,
                'Usuario': user.username,
                'Nombre': user.nombre_completo,
                'Email': user.email,
                'Acción': 'Login' if user.last_login else 'Creación',
                'Tipo': 'login' if user.last_login else 'creacion',
                'Tabla': 'Usuario',
                'Registro ID': user.id,
                'IP': '127.0.0.1',
                'Fecha': user.last_login.strftime('%Y-%m-%d %H:%M:%S') if user.last_login else user.date_joined.strftime('%Y-%m-%d %H:%M:%S'),
            })
    else:
        if request.user.is_superuser:
            auditorias = Auditoria.objects.all().select_related('usuario')
        else:
            auditorias = Auditoria.objects.filter(usuario__idUniversidad_id=universidad_id).select_related('usuario')

        data = []
        for aud in auditorias:
            data.append({
                'ID': aud.id,
                'Usuario': aud.usuario.username if aud.usuario else 'Sistema',
                'Nombre': aud.usuario.nombre_completo if aud.usuario else '',
                'Email': aud.usuario.email if aud.usuario else '',
                'Acción': aud.accion,
                'Tipo': aud.tipo,
                'Tabla': aud.tabla_afectada or '',
                'Registro ID': aud.registro_afectado or '',
                'IP': aud.ip or '',
                'Fecha': aud.fecha.strftime('%Y-%m-%d %H:%M:%S') if aud.fecha else '',
            })

    titulo = "Auditoría"
    headers = list(data[0].keys()) if data else []

    return generar_exportacion(data, titulo, formato, headers)


def exportar_riesgos(request, formato, universidad_id):
    """Exportar riesgos de estudiantes"""
    if request.user.is_superuser:
        riesgos = RiesgoEstudiante.objects.all().select_related('idEstudiante', 'idFactor')
    else:
        riesgos = RiesgoEstudiante.objects.filter(
            idEstudiante__idUniversidad_id=universidad_id
        ).select_related('idEstudiante', 'idFactor')

    nivel = request.GET.get('nivel', '')
    if nivel:
        riesgos = riesgos.filter(nivel=nivel)

    estado = request.GET.get('estado', '')
    if estado:
        riesgos = riesgos.filter(estado=estado)

    data = []
    for riesgo in riesgos:
        data.append({
            'Estudiante': riesgo.idEstudiante.nombre_completo,
            'Carnet': riesgo.idEstudiante.carnet,
            'Factor': riesgo.idFactor.nombre if riesgo.idFactor else '',
            'Nivel': riesgo.nivel,
            'Estado': riesgo.estado,
            'Observaciones': riesgo.observaciones or '',
            'Fecha Detección': riesgo.fecha_deteccion.strftime('%Y-%m-%d') if riesgo.fecha_deteccion else '',
        })

    titulo = "Riesgos"
    headers = list(data[0].keys()) if data else []

    return generar_exportacion(data, titulo, formato, headers)


# ============================================
# SECCIÓN 4: EXPORTAR ESTADÍSTICAS
# ============================================

def exportar_estadisticas_universidad(request, formato, universidad_id):
    """
    Exporta estadísticas de la universidad en diferentes formatos
    """
    # Obtener universidad
    if request.user.is_superuser:
        universidad_id_param = request.GET.get('universidad_id')
        if universidad_id_param:
            universidad = get_object_or_404(CatalogoUniversidad, idUniversidad=universidad_id_param)
            universidad_id = universidad.idUniversidad
        else:
            universidad = None
    else:
        universidad = request.user.idUniversidad

    if universidad:
        estudiantes = Estudiante.objects.filter(idUniversidad=universidad)
    else:
        estudiantes = Estudiante.objects.all()

    # Estadísticas generales
    # ✅ CAMBIO: CatalogoCarrera, CatalogoMateria, CatalogoAula
    stats_generales = {
        'total_estudiantes': estudiantes.count(),
        'total_usuarios': Usuario.objects.filter(idUniversidad=universidad).count() if universidad else Usuario.objects.count(),
        'total_carreras': CatalogoCarrera.objects.filter(idUniversidad=universidad).count() if universidad else CatalogoCarrera.objects.count(),
        'total_materias': CatalogoMateria.objects.filter(idCarrera__idUniversidad=universidad).count() if universidad else CatalogoMateria.objects.count(),
        'total_aulas': CatalogoAula.objects.filter(idUniversidad=universidad).count() if universidad else CatalogoAula.objects.count(),
        'total_becas': Beca.objects.filter(idUniversidad=universidad).count() if universidad else Beca.objects.count(),
        'total_becas_activas': Beca.objects.filter(idUniversidad=universidad, estado='Activa').count() if universidad else Beca.objects.filter(estado='Activa').count(),
        'total_estudiantes_becados': BecaAsignacion.objects.filter(
            idBeca__idUniversidad=universidad,
            estado='Activa'
        ).values('idEstudiante').distinct().count() if universidad else BecaAsignacion.objects.filter(estado='Activa').values('idEstudiante').distinct().count(),
    }

    # Estado académico
    estados_academicos = estudiantes.values('estado_academico').annotate(
        cantidad=Count('idEstudiante')
    ).order_by('estado_academico')

    estados_dict = {item['estado_academico']: item['cantidad'] for item in estados_academicos if item['estado_academico']}

    # Distribución por carrera
    distribucion_carreras = estudiantes.values(
        'idCarrera__nombre'
    ).annotate(
        cantidad=Count('idEstudiante')
    ).order_by('-cantidad')

    # Rendimiento académico
    rendimiento = estudiantes.aggregate(
        promedio_notas=Avg('promedio_general'),
        max_nota=Max('promedio_general'),
        min_nota=Min('promedio_general'),
        promedio_asistencia=Avg('porcentaje_asistencia'),
    )

    # Alertas
    alertas = Alerta.objects.filter(
        idEstudiante__in=estudiantes
    ).values('nivel').annotate(
        cantidad=Count('id')
    )
    alertas_dict = {item['nivel']: item['cantidad'] for item in alertas if item['nivel']}

    # Intervenciones
    intervenciones_count = Intervencion.objects.filter(
        idEstudiante__in=estudiantes
    ).count()

    intervenciones_efectivas = Intervencion.objects.filter(
        idEstudiante__in=estudiantes,
        efectiva=True
    ).count()

    # Datos para exportar
    data = {
        'universidad': {
            'id': universidad.idUniversidad if universidad else None,
            'nombre': universidad.nombre if universidad else "Todas las universidades",
            'fecha_exportacion': timezone.now().isoformat(),
        },
        'estadisticas_generales': stats_generales,
        'estados_academicos': estados_dict,
        'distribucion_carreras': list(distribucion_carreras),
        'rendimiento': {
            'promedio_general': float(rendimiento['promedio_notas'] or 0),
            'nota_maxima': float(rendimiento['max_nota'] or 0),
            'nota_minima': float(rendimiento['min_nota'] or 0),
            'promedio_asistencia': float(rendimiento['promedio_asistencia'] or 0),
        },
        'alertas': alertas_dict,
        'intervenciones': {
            'total': intervenciones_count,
            'efectivas': intervenciones_efectivas,
            'tasa_efectividad': (intervenciones_efectivas / intervenciones_count * 100) if intervenciones_count > 0 else 0,
        },
        'fecha_actual': timezone.now().isoformat(),
    }

    # Usar los generadores de exportación
    if formato == 'json':
        return exportar_json(data)
    elif formato == 'csv':
        return exportar_estadisticas_csv(data)
    elif formato == 'excel':
        return exportar_estadisticas_excel(data)
    elif formato == 'pdf':
        if not REPORTLAB_AVAILABLE:
            messages.error(request, "La librería reportlab no está instalada. Usa CSV, Excel o JSON.")
            return redirect('exportaciones_index')
        return exportar_estadisticas_pdf(data)
    else:
        return JsonResponse({'error': 'Formato no soportado'}, status=400)


# ============================================
# SECCIÓN 5: GENERADORES DE EXPORTACIÓN (GENÉRICOS)
# ============================================

def generar_exportacion(data, titulo, formato, headers=None):
    """
    Genera la exportación en el formato solicitado
    """
    if not data:
        return HttpResponse(
            json.dumps({'error': 'No hay datos para exportar'}, ensure_ascii=False),
            content_type='application/json',
            status=404
        )

    if headers is None:
        headers = list(data[0].keys()) if data else []

    if formato == 'csv':
        return exportar_csv(data, headers, titulo)
    elif formato == 'excel':
        return exportar_excel(data, headers, titulo)
    elif formato == 'pdf':
        if not REPORTLAB_AVAILABLE:
            return HttpResponse(
                json.dumps({'error': 'PDF no disponible. Instala reportlab.'}, ensure_ascii=False),
                content_type='application/json',
                status=503
            )
        return exportar_pdf(data, headers, titulo)
    elif formato == 'json':
        return exportar_json(data, titulo)
    else:
        return HttpResponse(
            json.dumps({'error': f'Formato {formato} no soportado'}, ensure_ascii=False),
            content_type='application/json',
            status=400
        )


def exportar_csv(data, headers, titulo):
    """Exportar a CSV"""
    output = StringIO()
    writer = csv.writer(output, delimiter=';')

    writer.writerow([f"=== {titulo.upper()} ==="])
    writer.writerow([f"Fecha: {datetime.now().strftime('%Y-%m-%d %H:%M')}"])
    writer.writerow([])
    writer.writerow(headers)

    for row in data:
        writer.writerow([row.get(h, '') for h in headers])

    response = HttpResponse(output.getvalue(), content_type='text/csv; charset=utf-8')
    filename = f"{titulo.lower()}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response


def exportar_excel(data, headers, titulo):
    """Exportar a Excel"""
    output = BytesIO()
    workbook = xlsxwriter.Workbook(output)

    title_format = workbook.add_format({'bold': True, 'font_size': 14, 'align': 'center'})
    header_format = workbook.add_format({'bold': True, 'bg_color': '#4e73df', 'color': 'white', 'align': 'center'})
    cell_format = workbook.add_format({'align': 'center'})
    number_format = workbook.add_format({'align': 'center', 'num_format': '#,##0.00'})
    date_format = workbook.add_format({'align': 'center', 'num_format': 'yyyy-mm-dd'})

    ws = workbook.add_worksheet(titulo[:31])

    ws.merge_range('A1:{}1'.format(chr(64 + len(headers))), f"{titulo.upper()}", title_format)
    ws.write(2, 0, f"Fecha: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    ws.write(3, 0, "---")

    for col, header in enumerate(headers):
        ws.write(4, col, header, header_format)
        ws.set_column(col, col, 18)

    for row, item in enumerate(data, start=5):
        for col, header in enumerate(headers):
            value = item.get(header, '')

            if isinstance(value, float):
                ws.write(row, col, value, number_format)
            elif isinstance(value, (int, bool)):
                ws.write(row, col, value)
            elif 'Fecha' in header or 'fecha' in header:
                if value:
                    ws.write(row, col, value, date_format)
                else:
                    ws.write(row, col, '')
            else:
                ws.write(row, col, str(value), cell_format)

    workbook.close()

    response = HttpResponse(output.getvalue(), content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    filename = f"{titulo.lower()}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response


def exportar_pdf(data, headers, titulo):
    """Exportar a PDF"""
    if not REPORTLAB_AVAILABLE:
        raise ImportError("reportlab no está instalado")

    response = HttpResponse(content_type='application/pdf')
    filename = f"{titulo.lower()}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
    response['Content-Disposition'] = f'attachment; filename="{filename}"'

    doc = SimpleDocTemplate(
        response,
        pagesize=landscape(A4),
        rightMargin=0.5*inch,
        leftMargin=0.5*inch,
        topMargin=0.5*inch,
        bottomMargin=0.5*inch
    )

    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=16,
        alignment=TA_CENTER,
        spaceAfter=20
    )

    elements = []

    elements.append(Paragraph(f"{titulo.upper()}", title_style))
    elements.append(Paragraph(f"Fecha: {datetime.now().strftime('%Y-%m-%d %H:%M')}", styles['Normal']))
    elements.append(Spacer(1, 10))

    table_data = [headers]
    for row in data:
        row_data = []
        for h in headers:
            value = row.get(h, '')
            if isinstance(value, float):
                value = f"{value:.2f}"
            row_data.append(str(value) if value else '')
        table_data.append(row_data)

    max_data = len(max(row) for row in table_data) if table_data else 0
    col_widths = [1.2*inch] * max_data

    table = Table(table_data, colWidths=col_widths, repeatRows=1)
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#4e73df')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 8),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 6),
        ('TOPPADDING', (0, 0), (-1, 0), 6),
        ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#f8f9fc')),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#dee2e6')),
        ('FONTSIZE', (0, 1), (-1, -1), 8),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
    ]))

    elements.append(table)
    elements.append(Spacer(1, 20))
    elements.append(Paragraph(f"Total de registros: {len(data)}", styles['Normal']))

    doc.build(elements)

    return response


def exportar_json(data, titulo=None):
    """Exportar a JSON"""
    if isinstance(data, dict):
        response_data = data
    else:
        response_data = {
            'titulo': titulo or 'Exportación',
            'fecha_exportacion': datetime.now().isoformat(),
            'total_registros': len(data),
            'datos': data
        }

    response = HttpResponse(
        json.dumps(response_data, indent=2, ensure_ascii=False),
        content_type='application/json'
    )
    filename = f"exportacion_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response


# ============================================
# SECCIÓN 6: EXPORTAR ESTADÍSTICAS EN FORMATOS ESPECÍFICOS
# ============================================

def exportar_estadisticas_csv(data):
    """Exporta estadísticas a CSV"""
    output = StringIO()
    writer = csv.writer(output, delimiter=';')

    writer.writerow(['=== ESTADÍSTICAS UNIVERSIDAD ==='])
    writer.writerow([f"Universidad: {data['universidad']['nombre']}"])
    writer.writerow([f"Fecha: {data['fecha_actual']}"])
    writer.writerow([])

    writer.writerow(['=== ESTADÍSTICAS GENERALES ==='])
    for key, value in data['estadisticas_generales'].items():
        writer.writerow([key.replace('_', ' ').title(), value])
    writer.writerow([])

    writer.writerow(['=== ESTADO ACADÉMICO ==='])
    writer.writerow(['Estado', 'Cantidad'])
    for estado, cantidad in data['estados_academicos'].items():
        writer.writerow([estado, cantidad])
    writer.writerow([])

    writer.writerow(['=== DISTRIBUCIÓN POR CARRERA ==='])
    writer.writerow(['Carrera', 'Cantidad'])
    for carrera in data['distribucion_carreras']:
        writer.writerow([carrera['idCarrera__nombre'] or 'Sin carrera', carrera['cantidad']])
    writer.writerow([])

    writer.writerow(['=== RENDIMIENTO ACADÉMICO ==='])
    for key, value in data['rendimiento'].items():
        writer.writerow([key.replace('_', ' ').title(), f"{value:.2f}" if isinstance(value, float) else value])
    writer.writerow([])

    writer.writerow(['=== ALERTAS ==='])
    for nivel, cantidad in data['alertas'].items():
        writer.writerow([nivel, cantidad])
    writer.writerow([])

    writer.writerow(['=== INTERVENCIONES ==='])
    for key, value in data['intervenciones'].items():
        writer.writerow([key.replace('_', ' ').title(), f"{value:.2f}" if isinstance(value, float) else value])

    response = HttpResponse(output.getvalue(), content_type='text/csv; charset=utf-8')
    nombre_archivo = f"estadisticas_{data['universidad']['nombre']}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    response['Content-Disposition'] = f'attachment; filename="{nombre_archivo}"'
    return response


def exportar_estadisticas_excel(data):
    """Exporta estadísticas a Excel"""
    output = BytesIO()
    workbook = xlsxwriter.Workbook(output)

    title_format = workbook.add_format({'bold': True, 'font_size': 16, 'align': 'center'})
    header_format = workbook.add_format({'bold': True, 'bg_color': '#4e73df', 'color': 'white', 'align': 'center'})
    cell_format = workbook.add_format({'align': 'center'})
    number_format = workbook.add_format({'align': 'center', 'num_format': '#,##0.00'})

    ws1 = workbook.add_worksheet('Resumen')

    ws1.merge_range('A1:D1', f"ESTADÍSTICAS - {data['universidad']['nombre']}", title_format)
    ws1.write(2, 0, f"Fecha: {data['fecha_actual']}")
    ws1.write(3, 0, "---")

    row = 5
    ws1.write(row, 0, "ESTADÍSTICAS GENERALES", header_format)
    row += 1
    for key, value in data['estadisticas_generales'].items():
        ws1.write(row, 0, key.replace('_', ' ').title())
        ws1.write(row, 1, value)
        row += 1

    row += 1
    ws1.write(row, 0, "RENDIMIENTO ACADÉMICO", header_format)
    row += 1
    for key, value in data['rendimiento'].items():
        ws1.write(row, 0, key.replace('_', ' ').title())
        ws1.write(row, 1, value, number_format)
        row += 1

    ws2 = workbook.add_worksheet('Estado Académico')
    ws2.write(0, 0, "Estado", header_format)
    ws2.write(0, 1, "Cantidad", header_format)
    row = 1
    for estado, cantidad in data['estados_academicos'].items():
        ws2.write(row, 0, estado)
        ws2.write(row, 1, cantidad)
        row += 1

    ws3 = workbook.add_worksheet('Carreras')
    ws3.write(0, 0, "Carrera", header_format)
    ws3.write(0, 1, "Cantidad", header_format)
    row = 1
    for carrera in data['distribucion_carreras']:
        ws3.write(row, 0, carrera['idCarrera__nombre'] or 'Sin carrera')
        ws3.write(row, 1, carrera['cantidad'])
        row += 1

    ws4 = workbook.add_worksheet('Alertas')
    ws4.write(0, 0, "Nivel", header_format)
    ws4.write(0, 1, "Cantidad", header_format)
    row = 1
    for nivel, cantidad in data['alertas'].items():
        ws4.write(row, 0, nivel)
        ws4.write(row, 1, cantidad)
        row += 1

    ws5 = workbook.add_worksheet('Intervenciones')
    ws5.write(0, 0, "Métrica", header_format)
    ws5.write(0, 1, "Valor", header_format)
    row = 1
    for key, value in data['intervenciones'].items():
        ws5.write(row, 0, key.replace('_', ' ').title())
        ws5.write(row, 1, value)
        row += 1

    workbook.close()

    response = HttpResponse(
        output.getvalue(),
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    nombre_archivo = f"estadisticas_{data['universidad']['nombre']}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    response['Content-Disposition'] = f'attachment; filename="{nombre_archivo}"'
    return response


def exportar_estadisticas_pdf(data):
    """Exporta estadísticas a PDF"""
    if not REPORTLAB_AVAILABLE:
        raise ImportError("reportlab no está instalado")

    response = HttpResponse(content_type='application/pdf')
    nombre_archivo = f"estadisticas_{data['universidad']['nombre']}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
    response['Content-Disposition'] = f'attachment; filename="{nombre_archivo}"'

    doc = SimpleDocTemplate(
        response,
        pagesize=A4,
        rightMargin=72,
        leftMargin=72,
        topMargin=72,
        bottomMargin=72
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=20,
        alignment=TA_CENTER,
        spaceAfter=20
    )
    heading_style = ParagraphStyle(
        'CustomHeading',
        parent=styles['Heading2'],
        fontSize=14,
        alignment=TA_LEFT,
        spaceAfter=10,
        spaceBefore=10
    )
    normal_style = styles['Normal']

    elements = []

    elements.append(Paragraph(f"ESTADÍSTICAS - {data['universidad']['nombre']}", title_style))
    elements.append(Paragraph(f"Fecha: {data['fecha_actual']}", normal_style))
    elements.append(Spacer(1, 20))

    elements.append(Paragraph("ESTADÍSTICAS GENERALES", heading_style))
    data_table = [['Métrica', 'Valor']]
    for key, value in data['estadisticas_generales'].items():
        data_table.append([key.replace('_', ' ').title(), str(value)])
    table = Table(data_table, colWidths=[3*inch, 2*inch])
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#4e73df')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 10),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
    ]))
    elements.append(table)
    elements.append(Spacer(1, 20))

    elements.append(Paragraph("RENDIMIENTO ACADÉMICO", heading_style))
    data_table = [['Métrica', 'Valor']]
    for key, value in data['rendimiento'].items():
        data_table.append([key.replace('_', ' ').title(), f"{value:.2f}" if isinstance(value, float) else str(value)])
    table = Table(data_table, colWidths=[3*inch, 2*inch])
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1cc88a')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 10),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
    ]))
    elements.append(table)
    elements.append(Spacer(1, 20))

    elements.append(Paragraph("ESTADO ACADÉMICO", heading_style))
    data_table = [['Estado', 'Cantidad']]
    for estado, cantidad in data['estados_academicos'].items():
        data_table.append([estado, str(cantidad)])
    table = Table(data_table, colWidths=[3*inch, 2*inch])
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#36b9cc')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 10),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
    ]))
    elements.append(table)
    elements.append(Spacer(1, 20))

    if data['alertas']:
        elements.append(Paragraph("ALERTAS", heading_style))
        data_table = [['Nivel', 'Cantidad']]
        for nivel, cantidad in data['alertas'].items():
            data_table.append([nivel, str(cantidad)])
        table = Table(data_table, colWidths=[3*inch, 2*inch])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#e74a3b')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ]))
        elements.append(table)
        elements.append(Spacer(1, 20))

    elements.append(Paragraph("INTERVENCIONES", heading_style))
    data_table = [['Métrica', 'Valor']]
    for key, value in data['intervenciones'].items():
        data_table.append([key.replace('_', ' ').title(), f"{value:.2f}" if isinstance(value, float) else str(value)])
    table = Table(data_table, colWidths=[3*inch, 2*inch])
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#f6c23e')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.black),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 10),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
    ]))
    elements.append(table)

    doc.build(elements)

    return response