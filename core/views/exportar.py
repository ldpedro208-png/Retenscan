# core/views/exportar.py - VERSIÓN CORREGIDA

from django.contrib.auth.decorators import login_required
from django.shortcuts import render, get_object_or_404, redirect  # ✅ Agregar redirect
from django.contrib import messages
from django.http import HttpResponse, JsonResponse
from django.db.models import Count, Avg, Sum, Q, Max, Min  # ✅ Agregar Max y Min
from django.utils import timezone
from datetime import datetime, timedelta
import json
import csv
from io import BytesIO, StringIO
import xlsxwriter
from reportlab.lib.pagesizes import letter, landscape
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib.enums import TA_CENTER, TA_LEFT

# ✅ CAMBIO: Carrera, Materia, Aula → CatalogoCarrera, CatalogoMateria, CatalogoAula
from ..models import (
    Estudiante, Usuario, CatalogoCarrera, CatalogoMateria, CatalogoAula,
    Beca, BecaAsignacion, Alerta, Intervencion,
    CatalogoUniversidad, Asistencia, HistorialAcademico
)
from .base import get_universidad_id, logger


@login_required
def exportar_estadisticas(request, formato='json'):
    """
    Exporta estadísticas de la universidad en diferentes formatos
    Formatos soportados: json, csv, excel, pdf
    """
    user_rol = request.user.rol
    universidad_id = get_universidad_id(request)

    # Verificar permisos
    if user_rol != 'admin':
        messages.error(request, "No tienes permiso para exportar estadísticas.")
        return redirect('dashboard')

    # Obtener universidad del usuario
    universidad = request.user.idUniversidad if not request.user.is_superuser else None

    # Si es superuser, puede seleccionar universidad
    if request.user.is_superuser:
        universidad_id_param = request.GET.get('universidad_id')
        if universidad_id_param:
            universidad = get_object_or_404(CatalogoUniversidad, idUniversidad=universidad_id_param)
            universidad_id = universidad.idUniversidad

    # Filtrar por universidad
    if universidad:
        estudiantes = Estudiante.objects.filter(idUniversidad=universidad)
    else:
        estudiantes = Estudiante.objects.all()

    # ============================================
    # RECOPILAR DATOS ESTADÍSTICOS
    # ============================================

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

    # ============================================
    # EXPORTAR SEGÚN FORMATO
    # ============================================

    if formato == 'json':
        return exportar_json(data)
    elif formato == 'csv':
        return exportar_csv(data)
    elif formato == 'excel':
        return exportar_excel(data)
    elif formato == 'pdf':
        return exportar_pdf(data)
    else:
        return JsonResponse({'error': 'Formato no soportado'}, status=400)


def exportar_json(data):
    """Exporta a JSON"""
    response = HttpResponse(
        json.dumps(data, indent=2, ensure_ascii=False),
        content_type='application/json'
    )
    nombre_archivo = f"estadisticas_{data['universidad']['nombre']}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    response['Content-Disposition'] = f'attachment; filename="{nombre_archivo}"'
    return response


def exportar_csv(data):
    """Exporta a CSV"""
    output = StringIO()
    writer = csv.writer(output, delimiter=';')

    # Escribir encabezado
    writer.writerow(['=== ESTADÍSTICAS UNIVERSIDAD ==='])
    writer.writerow([f"Universidad: {data['universidad']['nombre']}"])
    writer.writerow([f"Fecha: {data['fecha_actual']}"])
    writer.writerow([])

    # Estadísticas generales
    writer.writerow(['=== ESTADÍSTICAS GENERALES ==='])
    for key, value in data['estadisticas_generales'].items():
        writer.writerow([key.replace('_', ' ').title(), value])
    writer.writerow([])

    # Estado académico
    writer.writerow(['=== ESTADO ACADÉMICO ==='])
    writer.writerow(['Estado', 'Cantidad'])
    for estado, cantidad in data['estados_academicos'].items():
        writer.writerow([estado, cantidad])
    writer.writerow([])

    # Distribución por carrera
    writer.writerow(['=== DISTRIBUCIÓN POR CARRERA ==='])
    writer.writerow(['Carrera', 'Cantidad'])
    for carrera in data['distribucion_carreras']:
        writer.writerow([carrera['idCarrera__nombre'] or 'Sin carrera', carrera['cantidad']])
    writer.writerow([])

    # Rendimiento
    writer.writerow(['=== RENDIMIENTO ACADÉMICO ==='])
    for key, value in data['rendimiento'].items():
        writer.writerow([key.replace('_', ' ').title(), f"{value:.2f}" if isinstance(value, float) else value])
    writer.writerow([])

    # Alertas
    writer.writerow(['=== ALERTAS ==='])
    for nivel, cantidad in data['alertas'].items():
        writer.writerow([nivel, cantidad])
    writer.writerow([])

    # Intervenciones
    writer.writerow(['=== INTERVENCIONES ==='])
    for key, value in data['intervenciones'].items():
        writer.writerow([key.replace('_', ' ').title(), f"{value:.2f}" if isinstance(value, float) else value])

    response = HttpResponse(output.getvalue(), content_type='text/csv; charset=utf-8')
    nombre_archivo = f"estadisticas_{data['universidad']['nombre']}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    response['Content-Disposition'] = f'attachment; filename="{nombre_archivo}"'
    return response


def exportar_excel(data):
    """Exporta a Excel usando xlsxwriter"""
    output = BytesIO()
    workbook = xlsxwriter.Workbook(output)

    # Formatos
    title_format = workbook.add_format({'bold': True, 'font_size': 16, 'align': 'center'})
    header_format = workbook.add_format({'bold': True, 'bg_color': '#4e73df', 'color': 'white', 'align': 'center'})
    cell_format = workbook.add_format({'align': 'center'})
    number_format = workbook.add_format({'align': 'center', 'num_format': '#,##0.00'})

    # Hoja 1: Resumen
    ws1 = workbook.add_worksheet('Resumen')

    # Título
    ws1.merge_range('A1:D1', f"ESTADÍSTICAS - {data['universidad']['nombre']}", title_format)
    ws1.write(2, 0, f"Fecha: {data['fecha_actual']}")
    ws1.write(3, 0, "---")

    # Estadísticas generales
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

    # Hoja 2: Estado Académico
    ws2 = workbook.add_worksheet('Estado Académico')
    ws2.write(0, 0, "Estado", header_format)
    ws2.write(0, 1, "Cantidad", header_format)
    row = 1
    for estado, cantidad in data['estados_academicos'].items():
        ws2.write(row, 0, estado)
        ws2.write(row, 1, cantidad)
        row += 1

    # Hoja 3: Carreras
    ws3 = workbook.add_worksheet('Carreras')
    ws3.write(0, 0, "Carrera", header_format)
    ws3.write(0, 1, "Cantidad", header_format)
    row = 1
    for carrera in data['distribucion_carreras']:
        ws3.write(row, 0, carrera['idCarrera__nombre'] or 'Sin carrera')
        ws3.write(row, 1, carrera['cantidad'])
        row += 1

    # Hoja 4: Alertas
    ws4 = workbook.add_worksheet('Alertas')
    ws4.write(0, 0, "Nivel", header_format)
    ws4.write(0, 1, "Cantidad", header_format)
    row = 1
    for nivel, cantidad in data['alertas'].items():
        ws4.write(row, 0, nivel)
        ws4.write(row, 1, cantidad)
        row += 1

    # Hoja 5: Intervenciones
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


def exportar_pdf(data):
    """Exporta a PDF usando reportlab"""
    response = HttpResponse(content_type='application/pdf')
    nombre_archivo = f"estadisticas_{data['universidad']['nombre']}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
    response['Content-Disposition'] = f'attachment; filename="{nombre_archivo}"'

    doc = SimpleDocTemplate(
        response,
        pagesize=letter,
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

    # Título
    elements.append(Paragraph(f"ESTADÍSTICAS - {data['universidad']['nombre']}", title_style))
    elements.append(Paragraph(f"Fecha: {data['fecha_actual']}", normal_style))
    elements.append(Spacer(1, 20))

    # Estadísticas generales
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

    # Rendimiento
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

    # Estado Académico
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

    # Alertas
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

    # Intervenciones
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

    # Construir PDF
    doc.build(elements)

    return response


@login_required
def exportar_estudiantes(request, formato='excel'):
    """Exporta la lista de estudiantes de la universidad"""
    user_rol = request.user.rol

    if user_rol != 'admin':
        messages.error(request, "No tienes permiso para exportar estudiantes.")
        return redirect('dashboard')

    universidad_id = get_universidad_id(request)

    if request.user.is_superuser:
        estudiantes = Estudiante.objects.all().select_related('idUsuario', 'idCarrera')
    else:
        estudiantes = Estudiante.objects.filter(idUniversidad_id=universidad_id).select_related('idUsuario', 'idCarrera')

    # Datos para exportar
    data = []
    for est in estudiantes:
        data.append({
            'carnet': est.carnet,
            'nombre_completo': est.nombre_completo,
            'email': est.email,
            'telefono': est.telefono,
            'carrera': est.idCarrera.nombre if est.idCarrera else 'Sin carrera',
            'semestre': est.semestre_actual,
            'estado': est.estado_academico,
            'promedio': est.promedio_general or 0,
            'asistencia': est.porcentaje_asistencia or 0,
        })

    if formato == 'csv':
        return exportar_estudiantes_csv(data)
    else:
        return exportar_estudiantes_excel(data)


def exportar_estudiantes_csv(data):
    """Exporta estudiantes a CSV"""
    output = StringIO()
    writer = csv.writer(output, delimiter=';')

    # Encabezados
    headers = ['Carnet', 'Nombre Completo', 'Email', 'Teléfono', 'Carrera', 'Semestre', 'Estado', 'Promedio', 'Asistencia']
    writer.writerow(headers)

    # Datos
    for item in data:
        writer.writerow([
            item['carnet'],
            item['nombre_completo'],
            item['email'],
            item['telefono'],
            item['carrera'],
            item['semestre'],
            item['estado'],
            f"{item['promedio']:.2f}",
            f"{item['asistencia']:.2f}",
        ])

    response = HttpResponse(output.getvalue(), content_type='text/csv; charset=utf-8')
    nombre_archivo = f"estudiantes_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    response['Content-Disposition'] = f'attachment; filename="{nombre_archivo}"'
    return response


def exportar_estudiantes_excel(data):
    """Exporta estudiantes a Excel"""
    output = BytesIO()
    workbook = xlsxwriter.Workbook(output)

    header_format = workbook.add_format({'bold': True, 'bg_color': '#4e73df', 'color': 'white', 'align': 'center'})
    cell_format = workbook.add_format({'align': 'center'})

    ws = workbook.add_worksheet('Estudiantes')

    # Encabezados
    headers = ['Carnet', 'Nombre Completo', 'Email', 'Teléfono', 'Carrera', 'Semestre', 'Estado', 'Promedio', 'Asistencia']
    for col, header in enumerate(headers):
        ws.write(0, col, header, header_format)
        ws.set_column(col, col, 18)

    # Datos
    for row, item in enumerate(data, start=1):
        ws.write(row, 0, item['carnet'], cell_format)
        ws.write(row, 1, item['nombre_completo'], cell_format)
        ws.write(row, 2, item['email'], cell_format)
        ws.write(row, 3, item['telefono'], cell_format)
        ws.write(row, 4, item['carrera'], cell_format)
        ws.write(row, 5, item['semestre'], cell_format)
        ws.write(row, 6, item['estado'], cell_format)
        ws.write(row, 7, item['promedio'], cell_format)
        ws.write(row, 8, item['asistencia'], cell_format)

    workbook.close()

    response = HttpResponse(output.getvalue(), content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    nombre_archivo = f"estudiantes_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    response['Content-Disposition'] = f'attachment; filename="{nombre_archivo}"'
    return response