# core/views/__init__.py
# ✅ VERSIÓN CORREGIDA

# ============================================
# BASE (utilidades compartidas) - PRIMERO
# ============================================
from .base import (
    get_universidad_id,
    get_universidad_nombre,
    get_carreras_por_universidad,
    filter_by_universidad,
    get_estudiantes_por_usuario,
    _get_estudiante_con_permisos,
    _mostrar_resumen_carga,
    mensaje_exito,
    mensaje_error,
    get_servicio_prediccion,
    get_modelo_predictivo,
    obtener_servicio_prediccion,
    obtener_modelo_predictivo,
    get_universidad_nombre_from_user,
    get_universidad_id_from_user,
    REPORTLAB_AVAILABLE,
    obtener_usuarios_por_rol,
)

# ✅ FUNCIONES QUE ESTÁN EN utils.py - IMPORTAR DESDE AHÍ
from ..utils import (
    logger,
    generar_password_temporal,
    generar_username_desde_nombre,
    parse_decimal,
    formatear_fecha_mensaje,
)

# ============================================
# AUTENTICACIÓN
# ============================================
from .auth import (
    login_view,
    logout_view,
    CustomPasswordChangeView,
    CustomPasswordChangeDoneView,
    password_change_view,
    sesiones_activas,
    cerrar_sesion_remota,
    cerrar_todas_sesiones_remotas,
    preferencias_notificacion,
)

# ============================================
# DASHBOARDS
# ============================================
from .dashboard import (
    dashboard_admin,
    dashboard_tutor,
    dashboard_profesor,
    dashboard_estudiante,
    dashboard,
    DASHBOARD_MAP,
)

from .dashboard.asignacion_tutores import (
    asignacion_tutores_lista,
    asignacion_tutores_crear,
    asignacion_tutores_individual,
    asignacion_tutores_masiva,
    asignacion_tutores_confirmar,
    asignacion_tutores_cancelar,
    asignacion_tutores_estadisticas,
)

# ============================================
# ESTUDIANTES
# ============================================
from .estudiantes import (
    estudiante_list,
    estudiante_create,
    estudiante_detail,
    estudiante_edit,
    estudiante_delete,
    historial_add,
    asistencia_add,
    beca_add,
    estudiante_riesgos,
    carga_masiva,
    carga_masiva_resultado,
    descargar_plantilla,
)

# ============================================
# USUARIOS
# ============================================
from .usuarios import (
    usuario_list,
    usuario_detail,
    usuario_create,
    usuario_edit,
    usuario_delete,
    usuario_toggle_active,
    perfil_view,
)

# ============================================
# ENCUESTAS
# ============================================
from .encuestas import (
    encuesta_list,
    encuesta_create,
    encuesta_detail,
    encuesta_edit,
    encuesta_responder,
    encuesta_asignar,
    encuesta_resultados,
    encuesta_delete,
    encuesta_estudiantes_respuestas,
    debug_encuestas,
)

# ============================================
# TAREAS
# ============================================
from .tareas import (
    tarea_list,
    tarea_create,
    tarea_detail,
    tarea_edit,
    tarea_entregar,
    tarea_asignar,
    tarea_calificar,
    tarea_resultados,
    tarea_delete,
    tarea_restaurar,
    tarea_archivar,
)

# ============================================
# MENSAJES
# ============================================
from .mensajes import (
    mensaje_list,
    mensaje_create,
    mensaje_enviar,
    mensaje_detail,
    mensaje_edit,
    mensaje_delete,
    mensaje_confirm_delete,
    mensaje_responder,
    mensaje_toggle_leido,
    mensaje_marcar_leido,
    mensaje_marcar_no_leido,
    mensaje_marcar_todos_leidos,
    mensaje_marcar_seleccionados_leidos,
    mensaje_no_leidos_api,
    mensaje_contador_api,
    api_buscar_usuarios,
    mensaje_marcar_seleccionados_no_leidos,
    mensaje_archivar,
    mensaje_desarchivar,
    mensaje_reenviar,
    mensaje_mover,
    mensaje_archivar_seleccionados,
    mensaje_eliminar_seleccionados,
)

# ============================================
# REUNIONES
# ============================================
from .reuniones import (
    reunion_list,
    reunion_create,
    reunion_detail,
    reunion_completar,
    reunion_cancelar,
)

# ============================================
# BECAS
# ============================================
from .becas import (
    beca_list,
    beca_create,
    beca_detail,
    beca_edit,
    beca_delete,
    beca_asignar,
    beca_estudiantes,
    beca_cancelar_asignacion,
)

# ============================================
# AULAS
# ============================================
from .aulas import (
    aula_list,
    aula_create,
    aula_detail,
    aula_edit,
    aula_delete,
    aula_cambiar_estado,
)

# ============================================
# MATERIAS
# ============================================
from .materias import (
    materia_list,
    materia_create,
    materia_detail,
    materia_edit,
    materia_delete,
)

# ============================================
# REPORTES
# ============================================
from .reportes import (
    tutor_reporte,
    tutor_reporte_pdf,
)

# ============================================
# AUDITORÍA
# ============================================
from .auditoria import (
    auditoria_list,
    auditoria_detalle,
    auditoria_limpiar,
)

# ============================================
# CONFIGURACIÓN
# ============================================
from .configuracion import (
    configuracion_sistema,
    configuracion_test_email,
    configuracion_test_whatsapp,
    configuracion_importar,
    configuracion_restaurar_default,
    configuracion_universidad,
    configuracion_universidad_editar,
    configuracion_reset_cache,
    configuracion_universidad_exportar,
)

# ============================================
# ESTADÍSTICAS UNIVERSIDAD
# ============================================
from .estadisticas_universidad import (
    estadisticas_universidad,
)

# ============================================
# RIESGO (con fallback)
# ============================================
try:
    from .riesgo import (
        dashboard_riesgo,
        riesgo_gestion,
        riesgo_detail,
        entrenar_modelo,
        actualizar_riesgos,
        predecir_estudiante,
        intervencion_create,
        factor_riesgo_list,
        factor_riesgo_create,
        factor_riesgo_edit,
        factor_riesgo_delete,
        factor_riesgo_toggle,
    )
except ImportError:
    def _placeholder(request, *args, **kwargs):
        from django.shortcuts import render
        return render(request, 'error.html', {'mensaje': 'Módulo de riesgo no disponible'})

    dashboard_riesgo = riesgo_gestion = riesgo_detail = _placeholder
    entrenar_modelo = actualizar_riesgos = predecir_estudiante = _placeholder
    intervencion_create = _placeholder
    factor_riesgo_list = factor_riesgo_create = factor_riesgo_edit = _placeholder
    factor_riesgo_delete = factor_riesgo_toggle = _placeholder

# ============================================
# EXPORTACIONES (con fallback)
# ============================================
try:
    from .exportaciones import (
        exportaciones_index,
        exportar_datos,
    )
except ImportError:
    def exportaciones_index(request):
        from django.shortcuts import render
        return render(request, 'error.html', {'mensaje': 'Módulo de exportaciones no disponible'})

    def exportar_datos(request, tipo, formato):
        from django.shortcuts import render
        return render(request, 'error.html', {'mensaje': 'Módulo de exportaciones no disponible'})

# ============================================
# IMPORTACIÓN (con fallback)
# ============================================
try:
    from .importar import (
        importar_datos,
        importar_resultado,
        importar_descargar_template,
        importar_estado,
    )
except ImportError:
    def importar_datos(request):
        from django.shortcuts import render
        return render(request, 'error.html', {'mensaje': 'Módulo de importación no disponible'})

    def importar_resultado(request):
        from django.shortcuts import render
        return render(request, 'error.html', {'mensaje': 'Módulo de importación no disponible'})

    def importar_descargar_template(request, tipo):
        from django.shortcuts import render
        return render(request, 'error.html', {'mensaje': 'Módulo de importación no disponible'})

    def importar_estado(request):
        from django.shortcuts import render
        return render(request, 'error.html', {'mensaje': 'Módulo de importación no disponible'})

# ============================================
# CARRERAS (con fallback)
# ============================================
try:
    from .administrar_uni.carreras import (
        carrera_list,
        carrera_create,
        carrera_detail,
        carrera_edit,
        carrera_delete,
        carrera_api,
    )
except ImportError:
    def carrera_list(request):
        from django.shortcuts import render
        return render(request, 'error.html', {'mensaje': 'Módulo de carreras no disponible'})

    def carrera_create(request):
        from django.shortcuts import render
        return render(request, 'error.html', {'mensaje': 'Módulo de carreras no disponible'})

    def carrera_detail(request, pk):
        from django.shortcuts import render
        return render(request, 'error.html', {'mensaje': 'Módulo de carreras no disponible'})

    def carrera_edit(request, pk):
        from django.shortcuts import render
        return render(request, 'error.html', {'mensaje': 'Módulo de carreras no disponible'})

    def carrera_delete(request, pk):
        from django.shortcuts import render
        return render(request, 'error.html', {'mensaje': 'Módulo de carreras no disponible'})

    def carrera_api(request):
        from django.shortcuts import render
        return render(request, 'error.html', {'mensaje': 'Módulo de carreras no disponible'})