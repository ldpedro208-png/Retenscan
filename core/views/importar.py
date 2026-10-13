# core/views/importar.py - ACTUALIZAR IMPORTS Y QUERIES

"""
Vistas para importación de datos
"""
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.http import HttpResponse
from django.utils import timezone
from datetime import datetime

from ..models import CatalogoUniversidad
from ..services.importador_estudiantes import ImportadorEstudiantes
from ..services.importador_usuarios import ImportadorUsuarios
from ..services.importador_becas import ImportadorBecas
from .base import get_universidad_id, logger


# ============================================
# CONSTANTES
# ============================================

TIPOS_IMPORTACION = [
    ('estudiantes', 'Estudiantes', 'bi-people', 'primary'),
    ('usuarios', 'Usuarios', 'bi-person-badge', 'success'),
    ('becas', 'Becas', 'bi-award', 'secondary'),
    # ('materias', 'Materias', 'bi-book', 'info'),  # Futura implementación
    # ('carreras', 'Carreras', 'bi-mortarboard', 'warning'),  # Futura implementación
]

FORMATOS_SOPORTADOS = ['CSV', 'Excel (.xlsx, .xls)', 'JSON']


# ============================================
# VISTA PRINCIPAL
# ============================================

@login_required
def importar_datos(request):
    """
    Vista para importar datos desde archivos CSV, Excel o JSON.
    Solo accesible para administradores.
    """
    user_rol = request.user.rol

    # Verificar permisos - solo administradores
    if user_rol != 'admin':
        messages.error(request, "❌ No tienes permiso para importar datos.")
        return redirect('dashboard')

    universidad_id = get_universidad_id(request)
    universidad = request.user.idUniversidad if not request.user.is_superuser else None

    # Si es superuser, puede seleccionar universidad
    if request.user.is_superuser:
        universidad_id_param = request.GET.get('universidad_id')
        if universidad_id_param:
            universidad = get_object_or_404(CatalogoUniversidad, idUniversidad=universidad_id_param)
            universidad_id = universidad.idUniversidad

    # Procesar importación
    if request.method == 'POST':
        return procesar_importacion(request, universidad, universidad_id)

    # Obtener estadísticas para el template
    stats = obtener_estadisticas_importacion(universidad_id)

    # Universidades para superuser
    universidades = CatalogoUniversidad.objects.all() if request.user.is_superuser else []

    context = {
        'stats': stats,
        'universidad': universidad,
        'universidades': universidades,
        'user_rol': user_rol,
        'is_superuser': request.user.is_superuser,
        'tipos_importacion': TIPOS_IMPORTACION,
        'formatos_soportados': FORMATOS_SOPORTADOS,
    }

    return render(request, 'importar/importar_datos.html', context)


# ============================================
# FUNCIONES AUXILIARES
# ============================================

def obtener_estadisticas_importacion(universidad_id):
    """
    Obtiene estadísticas para el panel de importación.
    """
    # ✅ CAMBIO: importar CatalogoMateria y CatalogoCarrera
    from ..models import Estudiante, Usuario, CatalogoMateria, CatalogoCarrera, Beca

    if universidad_id:
        stats = {
            'total_estudiantes': Estudiante.objects.filter(idUniversidad_id=universidad_id).count(),
            'total_usuarios': Usuario.objects.filter(idUniversidad_id=universidad_id).count(),
            # ✅ CAMBIO: materias se filtran por idCarrera__idUniversidad_id
            'total_materias': CatalogoMateria.objects.filter(idCarrera__idUniversidad_id=universidad_id).count(),
            'total_carreras': CatalogoCarrera.objects.filter(idUniversidad_id=universidad_id).count(),
            'total_becas': Beca.objects.filter(idUniversidad_id=universidad_id).count(),
        }
    else:
        stats = {
            'total_estudiantes': Estudiante.objects.count(),
            'total_usuarios': Usuario.objects.count(),
            'total_materias': CatalogoMateria.objects.count(),
            'total_carreras': CatalogoCarrera.objects.count(),
            'total_becas': Beca.objects.count(),
        }

    return stats


def procesar_importacion(request, universidad, universidad_id):
    """
    Procesa la importación de datos.
    """
    tipo_importacion = request.POST.get('tipo_importacion', 'estudiantes')
    archivo = request.FILES.get('archivo')
    opcion_crear_usuarios = request.POST.get('opcion_crear_usuarios') == 'on'
    opcion_actualizar = request.POST.get('opcion_actualizar') == 'on'

    # Validar archivo
    if not archivo:
        messages.error(request, "❌ Por favor, selecciona un archivo para importar.")
        return redirect('importar_datos')

    # Validar tamaño (máximo 10MB)
    if archivo.size > 10 * 1024 * 1024:
        messages.error(request, "❌ El archivo es demasiado grande. Máximo 10MB.")
        return redirect('importar_datos')

    # Validar extensión
    extension = archivo.name.split('.')[-1].lower()
    if extension not in ['csv', 'xlsx', 'xls', 'json']:
        messages.error(request, f"❌ Formato de archivo no soportado: {extension}. Usa CSV, Excel o JSON.")
        return redirect('importar_datos')

    # Mapeo de tipos a importadores
    importadores = {
        'estudiantes': ImportadorEstudiantes,
        'usuarios': ImportadorUsuarios,
        'becas': ImportadorBecas,
    }

    if tipo_importacion not in importadores:
        messages.error(request, f"❌ Tipo de importación '{tipo_importacion}' no soportado.")
        return redirect('importar_datos')

    try:
        # Crear importador
        importador_class = importadores[tipo_importacion]

        # Parámetros según el tipo
        if tipo_importacion == 'estudiantes':
            importador = importador_class(
                archivo=archivo,
                universidad=universidad,
                usuario=request.user,
                crear_usuarios=opcion_crear_usuarios,
                actualizar_existentes=opcion_actualizar
            )
        elif tipo_importacion == 'usuarios':
            importador = importador_class(
                archivo=archivo,
                universidad=universidad,
                usuario=request.user,
                actualizar_existentes=opcion_actualizar
            )
        elif tipo_importacion == 'becas':
            importador = importador_class(
                archivo=archivo,
                universidad=universidad,
                usuario=request.user,
                actualizar_existentes=opcion_actualizar
            )
        else:
            importador = importador_class(
                archivo=archivo,
                universidad=universidad,
                usuario=request.user
            )

        # Procesar
        resultado = importador.procesar()

        # Mostrar resultados
        mostrar_resultados_importacion(request, resultado, tipo_importacion)

        # Guardar en sesión para ver detalle
        request.session['importacion_resultado'] = resultado
        request.session['importacion_tipo'] = tipo_importacion

        return redirect('importar_resultado')

    except Exception as e:
        logger.error(f"Error en importación: {str(e)}")
        messages.error(request, f"❌ Error al procesar el archivo: {str(e)}")
        return redirect('importar_datos')


def mostrar_resultados_importacion(request, resultado, tipo):
    """
    Muestra los resultados de la importación.
    """
    tipo_nombre = dict(TIPOS_IMPORTACION).get(tipo, tipo)

    if resultado['exitos'] > 0:
        messages.success(
            request,
            f"✅ {resultado['exitos']} {tipo_nombre} importados exitosamente."
        )

    if resultado['actualizados'] > 0:
        messages.info(
            request,
            f"🔄 {resultado['actualizados']} {tipo_nombre} actualizados."
        )

    if resultado.get('advertencias'):
        for adv in resultado['advertencias'][:5]:
            messages.warning(request, f"⚠️ {adv}")
        if len(resultado['advertencias']) > 5:
            messages.warning(
                request,
                f"⚠️ Y {len(resultado['advertencias']) - 5} advertencias más."
            )

    if resultado['errores']:
        for err in resultado['errores'][:5]:
            messages.error(request, f"❌ {err}")
        if len(resultado['errores']) > 5:
            messages.error(
                request,
                f"❌ Y {len(resultado['errores']) - 5} errores más."
            )


# ============================================
# VISTA DE RESULTADOS
# ============================================

@login_required
def importar_resultado(request):
    """
    Muestra el detalle de los resultados de la importación.
    """
    user_rol = request.user.rol

    if user_rol != 'admin':
        messages.error(request, "❌ No tienes permiso para ver esta página.")
        return redirect('dashboard')

    resultado = request.session.get('importacion_resultado')
    tipo = request.session.get('importacion_tipo', '')

    if not resultado:
        messages.info(request, "ℹ️ No hay resultados de importación para mostrar.")
        return redirect('importar_datos')

    # Limpiar sesión después de mostrar
    del request.session['importacion_resultado']
    del request.session['importacion_tipo']

    tipo_nombre = dict(TIPOS_IMPORTACION).get(tipo, tipo)

    context = {
        'resultado': resultado,
        'tipo': tipo,
        'tipo_nombre': tipo_nombre,
        'user_rol': user_rol,
        'fecha': timezone.now(),
        'estadisticas': {
            'total_procesados': resultado.get('total_procesados', 0),
            'exitosos': resultado.get('exitos', 0),
            'actualizados': resultado.get('actualizados', 0),
            'errores': len(resultado.get('errores', [])),
            'advertencias': len(resultado.get('advertencias', [])),
        }
    }

    return render(request, 'importar/importar_resultado.html', context)


# ============================================
# DESCARGA DE PLANTILLAS
# ============================================

@login_required
def importar_descargar_template(request, tipo):
    """
    Descargar template para importación de datos.
    """
    user_rol = request.user.rol

    if user_rol != 'admin':
        messages.error(request, "❌ No tienes permiso para descargar templates.")
        return redirect('dashboard')

    # Definir templates según tipo
    templates = {
        'estudiantes': {
            'headers': ['carnet', 'email', 'nombre', 'apellido', 'apellido_materno',
                       'telefono', 'carrera', 'codigo_carrera', 'ano_ingreso',
                       'semestre_actual', 'estado', 'genero', 'fecha_nacimiento'],
            'ejemplo': ['2024001', 'juan.perez@universidad.edu', 'Juan', 'Pérez', 'Ramírez',
                       '71234567', 'Ingeniería de Sistemas', 'ING-SIS-2024', '2024',
                       '1', 'Activo', 'M', '2000-01-15']
        },
        'usuarios': {
            'headers': ['username', 'email', 'nombre', 'apellido', 'carnet', 'rol', 'telefono'],
            'ejemplo': ['jperez', 'jperez@universidad.edu', 'Juan', 'Pérez', '2024001', 'estudiante', '71234567']
        },
        'becas': {
            'headers': ['nombre', 'codigo', 'tipo', 'monto', 'descripcion', 'duracion_meses',
                       'cupos_disponibles', 'estado'],
            'ejemplo': ['Beca Excelencia', 'BEC-EXC-001', 'Excelencia', '500.00',
                       'Beca para estudiantes con alto rendimiento', '12', '10', 'Activa']
        },
    }

    if tipo not in templates:
        messages.error(request, f"❌ Tipo de template '{tipo}' no válido.")
        return redirect('importar_datos')

    template = templates[tipo]

    # Crear archivo CSV
    import csv
    from io import StringIO

    output = StringIO()
    writer = csv.writer(output, delimiter=';')
    writer.writerow(template['headers'])
    writer.writerow(template['ejemplo'])

    response = HttpResponse(output.getvalue(), content_type='text/csv; charset=utf-8')
    filename = f"template_importacion_{tipo}_{datetime.now().strftime('%Y%m%d')}.csv"
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response


@login_required
def importar_estado(request):
    """
    Ver el estado de las importaciones (historial)
    """
    user_rol = request.user.rol

    if user_rol != 'admin':
        messages.error(request, "❌ No tienes permiso para ver el historial de importaciones.")
        return redirect('dashboard')

    context = {
        'user_rol': user_rol,
        'mensaje': '📊 Historial de importaciones disponible próximamente.',
    }

    return render(request, 'importar/importar_estado.html', context)