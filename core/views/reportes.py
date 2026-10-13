# core/views/reportes.py

from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import HttpResponse
from django.utils import timezone
from datetime import datetime
from ..models import Estudiante, RiesgoEstudiante, Intervencion, UsuarioEstudiantes
from .base import get_universidad_id, logger

# ✅ Importar REPORTLAB_AVAILABLE desde base
from .base import REPORTLAB_AVAILABLE

# ✅ Condicional para reportlab
if REPORTLAB_AVAILABLE:
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib import colors
        from reportlab.lib.units import inch
        from io import BytesIO
    except ImportError:
        REPORTLAB_AVAILABLE = False


@login_required
def tutor_reporte(request):
    user_rol = getattr(request.user, 'rol', 'estudiante')
    universidad_id = get_universidad_id(request)

    if user_rol != 'tutor':
        messages.error(request, "No tienes permiso para ver esta página.")
        return redirect('dashboard')

    estudiantes_asignados = UsuarioEstudiantes.objects.filter(
        usuario_id=request.user.id
    ).values_list('estudiante_id', flat=True)

    estudiantes = Estudiante.objects.filter(
        idEstudiante__in=estudiantes_asignados
    ).select_related('idCarrera', 'idUsuario')

    total_estudiantes = estudiantes.count()
    en_riesgo = RiesgoEstudiante.objects.filter(
        idEstudiante__in=estudiantes_asignados,
        estado='Activo'
    ).values('idEstudiante').distinct().count()
    sin_riesgo = total_estudiantes - en_riesgo

    estudiantes_riesgo = RiesgoEstudiante.objects.filter(
        idEstudiante__in=estudiantes_asignados,
        estado='Activo'
    ).values_list('idEstudiante', flat=True)

    for estudiante in estudiantes:
        estudiante.intervenciones_count = Intervencion.objects.filter(
            idEstudiante=estudiante
        ).count()

    total_intervenciones = Intervencion.objects.filter(
        idEstudiante__in=estudiantes_asignados
    ).count()

    context = {
        'estudiantes': estudiantes,
        'total_estudiantes': total_estudiantes,
        'en_riesgo': en_riesgo,
        'sin_riesgo': sin_riesgo,
        'total_intervenciones': total_intervenciones,
        'estudiantes_riesgo': list(estudiantes_riesgo),
        'fecha_actual': timezone.now(),
        'user_rol': user_rol,
    }
    return render(request, 'tutor/tutor_reporte.html', context)


@login_required
def tutor_reporte_pdf(request):
    user_rol = getattr(request.user, 'rol', 'estudiante')

    if user_rol != 'tutor':
        messages.error(request, "No tienes permiso para generar este reporte.")
        return redirect('dashboard')

    if not REPORTLAB_AVAILABLE:
        messages.error(request, "La librería reportlab no está instalada.")
        return redirect('tutor_reporte')

    estudiantes_asignados = UsuarioEstudiantes.objects.filter(
        usuario_id=request.user.id
    ).values_list('estudiante_id', flat=True)

    estudiantes = Estudiante.objects.filter(
        idEstudiante__in=estudiantes_asignados
    ).select_related('idCarrera', 'idUsuario')

    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename=reporte_tutor_{datetime.now().strftime("%Y%m%d")}.pdf'

    try:
        doc = SimpleDocTemplate(response, pagesize=A4)
        styles = getSampleStyleSheet()
        elements = []

        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=18,
            textColor=colors.HexColor('#2c3e50'),
            spaceAfter=30
        )

        elements.append(Paragraph(f"Reporte de Tutoría - {request.user.get_full_name() or request.user.username}", title_style))
        elements.append(Paragraph(f"Fecha: {datetime.now().strftime('%d/%m/%Y %H:%M')}", styles['Normal']))
        elements.append(Spacer(1, 20))

        total = estudiantes.count()
        en_riesgo = RiesgoEstudiante.objects.filter(
            idEstudiante__in=estudiantes_asignados,
            estado='Activo'
        ).values('idEstudiante').distinct().count()

        summary_data = [
            ['Total Estudiantes', 'En Riesgo', 'Sin Riesgo'],
            [str(total), str(en_riesgo), str(total - en_riesgo)]
        ]

        summary_table = Table(summary_data, colWidths=[2*inch, 2*inch, 2*inch])
        summary_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#3498db')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 12),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#ecf0f1')),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ]))
        elements.append(summary_table)
        elements.append(Spacer(1, 20))

        data = [['Carnet', 'Nombre', 'Carrera', 'Estado', 'Riesgo']]

        for estudiante in estudiantes:
            tiene_riesgo = RiesgoEstudiante.objects.filter(
                idEstudiante=estudiante,
                estado='Activo'
            ).exists()

            nombre_completo = f"{estudiante.idUsuario.first_name} {estudiante.idUsuario.last_name}".strip()
            if not nombre_completo:
                nombre_completo = estudiante.idUsuario.username

            data.append([
                estudiante.idUsuario.carnet,
                nombre_completo,
                estudiante.idCarrera.nombre[:20] if estudiante.idCarrera else 'N/A',
                estudiante.estado_academico,
                'Sí' if tiene_riesgo else 'No'
            ])

        table = Table(data, colWidths=[1.2*inch, 2.5*inch, 2*inch, 1.2*inch, 0.8*inch])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2c3e50')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#f8f9fa')),
            ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#bdc3c7')),
            ('FONTSIZE', (0, 1), (-1, -1), 8),
        ]))
        elements.append(table)

        doc.build(elements)
        
    except Exception as e:
        logger.error(f"Error generando PDF: {str(e)}")
        messages.error(request, f"Error al generar el PDF: {str(e)}")
        return redirect('tutor_reporte')

    return response