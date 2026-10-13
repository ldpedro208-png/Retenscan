# core/urls.py

from django.urls import path, include
from django.contrib.auth import views as auth_views
from . import views

urlpatterns = [
    # ============================================
    # DASHBOARD (principal + específicos por rol)
    # ============================================
    path('', views.dashboard, name='dashboard'),
    path('dashboard/admin/', views.dashboard_admin, name='dashboard_admin'),
    path('dashboard/tutor/', views.dashboard_tutor, name='dashboard_tutor'),
    path('dashboard/profesor/', views.dashboard_profesor, name='dashboard_profesor'),
    path('dashboard/estudiante/', views.dashboard_estudiante, name='dashboard_estudiante'),

    # ============================================
    # ESTUDIANTES
    # ============================================
    path('estudiantes/', views.estudiante_list, name='estudiante_list'),
    path('estudiantes/nuevo/', views.estudiante_create, name='estudiante_create'),
    path('estudiantes/<int:pk>/', views.estudiante_detail, name='estudiante_detail'),
    path('estudiantes/<int:pk>/editar/', views.estudiante_edit, name='estudiante_edit'),
    path('estudiantes/<int:pk>/eliminar/', views.estudiante_delete, name='estudiante_delete'),
    path('estudiantes/<int:estudiante_id>/historial/', views.historial_add, name='historial_add'),
    path('estudiantes/<int:estudiante_id>/asistencia/', views.asistencia_add, name='asistencia_add'),
    path('estudiantes/<int:estudiante_id>/beca/', views.beca_add, name='beca_add'),
    path('estudiantes/<int:estudiante_id>/intervencion/', views.intervencion_create, name='intervencion_create'),
    path('estudiantes/<int:pk>/riesgos/', views.estudiante_riesgos, name='estudiante_riesgos'),

    # ============================================
    # CARGA MASIVA
    # ============================================
    path('carga-masiva/', views.carga_masiva, name='carga_masiva'),
    path('carga-masiva/resultado/', views.carga_masiva_resultado, name='carga_masiva_resultado'),
    path('descargar-plantilla/', views.descargar_plantilla, name='descargar_plantilla'),

    # ============================================
    # ENCUESTAS
    # ============================================
    path('encuestas/', views.encuesta_list, name='encuesta_list'),
    path('encuestas/crear/', views.encuesta_create, name='encuesta_create'),
    path('encuestas/<int:pk>/', views.encuesta_detail, name='encuesta_detail'),
    path('encuestas/<int:pk>/editar/', views.encuesta_edit, name='encuesta_edit'),
    path('encuestas/<int:pk>/responder/', views.encuesta_responder, name='encuesta_responder'),
    path('encuestas/<int:pk>/asignar/', views.encuesta_asignar, name='encuesta_asignar'),
    path('encuestas/<int:pk>/resultados/', views.encuesta_resultados, name='encuesta_resultados'),
    path('encuestas/<int:pk>/eliminar/', views.encuesta_delete, name='encuesta_delete'),
    path('encuestas/<int:pk>/estudiantes/', views.encuesta_estudiantes_respuestas, name='encuesta_estudiantes_respuestas'),
    path('debug/encuestas/', views.debug_encuestas, name='debug_encuestas'),

    # ============================================
    # TAREAS
    # ============================================
    path('tareas/', views.tarea_list, name='tarea_list'),
    path('tareas/crear/', views.tarea_create, name='tarea_create'),
    path('tareas/<int:pk>/', views.tarea_detail, name='tarea_detail'),
    path('tareas/<int:pk>/editar/', views.tarea_edit, name='tarea_edit'),
    path('tareas/<int:pk>/entregar/', views.tarea_entregar, name='tarea_entregar'),
    path('tareas/<int:pk>/asignar/', views.tarea_asignar, name='tarea_asignar'),
    path('tareas/<int:pk>/calificar/', views.tarea_calificar, name='tarea_calificar'),
    path('tareas/<int:pk>/resultados/', views.tarea_resultados, name='tarea_resultados'),
    path('tareas/<int:pk>/eliminar/', views.tarea_delete, name='tarea_delete'),
    path('tareas/<int:pk>/restaurar/', views.tarea_restaurar, name='tarea_restaurar'),
    path('tareas/<int:pk>/archivar/', views.tarea_archivar, name='tarea_archivar'),

    # ============================================
    # TUTOR
    # ============================================
    path('tutor/reporte/', views.tutor_reporte, name='tutor_reporte'),
    path('tutor/reporte/pdf/', views.tutor_reporte_pdf, name='tutor_reporte_pdf'),

    # ============================================
    # MENSAJES
    # ============================================
    path('mensajes/', views.mensaje_list, name='mensaje_list'),
    path('mensajes/crear/', views.mensaje_create, name='mensaje_create'),
    path('mensajes/enviar/', views.mensaje_enviar, name='mensaje_enviar'),
    path('mensajes/<int:pk>/', views.mensaje_detail, name='mensaje_detail'),
    path('mensajes/<int:pk>/responder/', views.mensaje_responder, name='mensaje_responder'),
    path('mensajes/<int:pk>/eliminar/', views.mensaje_delete, name='mensaje_delete'),
    path('mensajes/<int:pk>/toggle-leido/', views.mensaje_toggle_leido, name='mensaje_toggle_leido'),
    path('mensajes/<int:pk>/marcar-leido/', views.mensaje_marcar_leido, name='mensaje_marcar_leido'),
    path('mensajes/<int:pk>/marcar-no-leido/', views.mensaje_marcar_no_leido, name='mensaje_marcar_no_leido'),
    path('mensajes/marcar-todos-leidos/', views.mensaje_marcar_todos_leidos, name='mensaje_marcar_todos_leidos'),
    path('mensajes/marcar-seleccionados-leidos/', views.mensaje_marcar_seleccionados_leidos, name='mensaje_marcar_seleccionados_leidos'),
    path('mensajes/marcar-seleccionados-no-leidos/', views.mensaje_marcar_seleccionados_no_leidos, name='mensaje_marcar_seleccionados_no_leidos'),
    path('mensajes/archivar-seleccionados/', views.mensaje_archivar_seleccionados, name='mensaje_archivar_seleccionados'),
    path('mensajes/eliminar-seleccionados/', views.mensaje_eliminar_seleccionados, name='mensaje_eliminar_seleccionados'),
    path('mensajes/<int:pk>/archivar/', views.mensaje_archivar, name='mensaje_archivar'),
    path('mensajes/<int:pk>/desarchivar/', views.mensaje_desarchivar, name='mensaje_desarchivar'),
    path('mensajes/<int:pk>/reenviar/', views.mensaje_reenviar, name='mensaje_reenviar'),
    path('mensajes/<int:pk>/mover/<str:carpeta>/', views.mensaje_mover, name='mensaje_mover'),
    path('mensajes/no-leidos-api/', views.mensaje_no_leidos_api, name='mensaje_no_leidos_api'),
    path('mensajes/contador-api/', views.mensaje_contador_api, name='mensaje_contador_api'),
    path('api/usuarios/buscar/', views.api_buscar_usuarios, name='api_buscar_usuarios'),

    # ============================================
    # REUNIONES
    # ============================================
    path('reuniones/', views.reunion_list, name='reunion_list'),
    path('reuniones/crear/', views.reunion_create, name='reunion_create'),
    path('reuniones/<int:pk>/', views.reunion_detail, name='reunion_detail'),
    path('reuniones/<int:pk>/completar/', views.reunion_completar, name='reunion_completar'),
    path('reuniones/<int:pk>/cancelar/', views.reunion_cancelar, name='reunion_cancelar'),

    # ============================================
    # USUARIOS / AUTENTICACIÓN
    # ============================================
    path('password_change/', views.CustomPasswordChangeView.as_view(), name='password_change'),
    path('password_change/done/', views.CustomPasswordChangeDoneView.as_view(), name='password_change_done'),
    path('perfil/', views.perfil_view, name='perfil'),
    path('usuarios/', views.usuario_list, name='usuario_list'),
    path('usuarios/crear/', views.usuario_create, name='usuario_create'),
    path('usuarios/<int:pk>/', views.usuario_detail, name='usuario_detail'),
    path('usuarios/<int:pk>/editar/', views.usuario_edit, name='usuario_edit'),
    path('usuarios/<int:pk>/eliminar/', views.usuario_delete, name='usuario_delete'),
    path('usuarios/<int:pk>/toggle-active/', views.usuario_toggle_active, name='usuario_toggle_active'),
    path('usuarios/<int:pk>/update/', views.usuario_edit, name='usuario_update'),

    # ============================================
    # RIESGOS Y FACTORES
    # ============================================
    path('riesgos/dashboard/', views.dashboard_riesgo, name='dashboard_riesgo'),
    path('riesgos/gestion/', views.riesgo_gestion, name='riesgo_gestion'),
    path('riesgos/<int:pk>/', views.riesgo_detail, name='riesgo_detail'),
    path('riesgos/entrenar/', views.entrenar_modelo, name='entrenar_modelo'),
    path('riesgos/actualizar/', views.actualizar_riesgos, name='actualizar_riesgos'),
    path('riesgos/predecir/<int:estudiante_id>/', views.predecir_estudiante, name='predecir_estudiante'),

    path('factores/', views.factor_riesgo_list, name='factor_riesgo_list'),
    path('factores/crear/', views.factor_riesgo_create, name='factor_riesgo_create'),
    path('factores/<int:pk>/editar/', views.factor_riesgo_edit, name='factor_riesgo_edit'),
    path('factores/<int:pk>/eliminar/', views.factor_riesgo_delete, name='factor_riesgo_delete'),
    path('factores/<int:pk>/toggle/', views.factor_riesgo_toggle, name='factor_riesgo_toggle'),

    # ============================================
    # INTERVENCIONES
    # ============================================
    path('intervencion/crear/<int:estudiante_id>/', views.intervencion_create, name='intervencion_create'),

    # ============================================
    # AULAS
    # ============================================
    path('aulas/', views.aula_list, name='aula_list'),
    path('aulas/crear/', views.aula_create, name='aula_create'),
    path('aulas/<int:id>/', views.aula_detail, name='aula_detail'),
    path('aulas/<int:id>/editar/', views.aula_edit, name='aula_edit'),
    path('aulas/<int:id>/eliminar/', views.aula_delete, name='aula_delete'),
    path('aulas/<int:id>/cambiar-estado/', views.aula_cambiar_estado, name='aula_cambiar_estado'),

    # ============================================
    # MATERIAS
    # ============================================
    path('admin-universidad/materias/', views.materia_list, name='materia_list'),
    path('admin-universidad/materias/crear/', views.materia_create, name='materia_create'),
    path('admin-universidad/materias/<int:id>/', views.materia_detail, name='materia_detail'),
    path('admin-universidad/materias/<int:id>/editar/', views.materia_edit, name='materia_edit'),
    path('admin-universidad/materias/<int:id>/eliminar/', views.materia_delete, name='materia_delete'),

    # ============================================
    # CARRERAS
    # ============================================
    path('administrar_uni/carreras/', views.carrera_list, name='carrera_list'),
    path('administrar_uni/carreras/crear/', views.carrera_create, name='carrera_create'),
    path('administrar_uni/carreras/<int:pk>/', views.carrera_detail, name='carrera_detail'),
    path('administrar_uni/carreras/<int:pk>/editar/', views.carrera_edit, name='carrera_edit'),
    path('administrar_uni/carreras/<int:pk>/eliminar/', views.carrera_delete, name='carrera_delete'),
    path('api/carreras/', views.carrera_api, name='carrera_api'),

    # ============================================
    # BECAS
    # ============================================
    path('becas/', views.beca_list, name='beca_list'),
    path('becas/crear/', views.beca_create, name='beca_create'),
    path('becas/<int:id>/', views.beca_detail, name='beca_detail'),
    path('becas/<int:id>/editar/', views.beca_edit, name='beca_edit'),
    path('becas/<int:id>/eliminar/', views.beca_delete, name='beca_delete'),
    path('becas/<int:id>/asignar/', views.beca_asignar, name='beca_asignar'),
    path('becas/<int:id>/estudiantes/', views.beca_estudiantes, name='beca_estudiantes'),
    path('becas/asignacion/<int:id>/cancelar/', views.beca_cancelar_asignacion, name='beca_cancelar_asignacion'),

    # ============================================
    # ESTADÍSTICAS
    # ============================================
    path('admin-universidad/estadisticas/', views.estadisticas_universidad, name='estadisticas_universidad'),

    # ============================================
    # AUDITORÍA
    # ============================================
    path('auditoria/', views.auditoria_list, name='auditoria_list'),
    path('auditoria/<int:id>/', views.auditoria_detalle, name='auditoria_detalle'),
    path('auditoria/limpiar/', views.auditoria_limpiar, name='auditoria_limpiar'),

    # ============================================
    # CONFIGURACIÓN DEL SISTEMA
    # ============================================
    path('configuracion/', views.configuracion_sistema, name='configuracion_sistema'),
    path('configuracion/test-email/', views.configuracion_test_email, name='configuracion_test_email'),
    path('configuracion/test-whatsapp/', views.configuracion_test_whatsapp, name='configuracion_test_whatsapp'),
    path('configuracion/importar/', views.configuracion_importar, name='configuracion_importar'),
    path('configuracion/restaurar-default/', views.configuracion_restaurar_default, name='configuracion_restaurar_default'),
    path('configuracion/universidad/', views.configuracion_universidad, name='configuracion_universidad'),
    path('configuracion/universidad/editar/', views.configuracion_universidad_editar, name='configuracion_universidad_editar'),
    path('configuracion/reset-cache/', views.configuracion_reset_cache, name='configuracion_reset_cache'),
    path('configuracion/exportar/', views.configuracion_universidad_exportar, name='configuracion_universidad_exportar'),

    # ============================================
    # IMPORTACIÓN DE DATOS
    # ============================================
    path('admin-universidad/importar/', views.importar_datos, name='importar_datos'),
    path('admin-universidad/importar/resultado/', views.importar_resultado, name='importar_resultado'),
    path('admin-universidad/importar/template/<str:tipo>/', views.importar_descargar_template, name='importar_descargar_template'),
    path('admin-universidad/importar/estado/', views.importar_estado, name='importar_estado'),

    # ============================================
    # EXPORTACIÓN DE DATOS
    # ============================================
    path('exportaciones/', views.exportaciones_index, name='exportaciones_index'),
    path('exportaciones/<str:tipo>/<str:formato>/', views.exportar_datos, name='exportar_datos'),

    # ============================================
    # PROFESOR - ASIGNACIÓN DE TUTORES
    # ============================================
    path('profesor/asignacion-tutores/', views.asignacion_tutores_lista, name='asignacion_tutores_lista'),
    path('profesor/asignacion-tutores/crear/', views.asignacion_tutores_crear, name='asignacion_tutores_crear'),
    path('profesor/asignacion-tutores/individual/', views.asignacion_tutores_individual, name='asignacion_tutores_individual'),
    path('profesor/asignacion-tutores/masiva/', views.asignacion_tutores_masiva, name='asignacion_tutores_masiva'),
    path('profesor/asignacion-tutores/confirmar/<int:asignacion_id>/', views.asignacion_tutores_confirmar, name='asignacion_tutores_confirmar'),
    path('profesor/asignacion-tutores/cancelar/<int:asignacion_id>/', views.asignacion_tutores_cancelar, name='asignacion_tutores_cancelar'),
    path('profesor/asignacion-tutores/estadisticas/', views.asignacion_tutores_estadisticas, name='asignacion_tutores_estadisticas'),

    # ============================================
    # BIBLIOTECA
    # ============================================
    path('biblioteca/', include('biblioteca.urls', namespace='biblioteca')),

    # ============================================
    # RESET DE CONTRASEÑA (OPCIONAL)
    # ============================================
    # Solo si necesitas que los usuarios puedan recuperar su contraseña por email.
    # Si NO usas reset de contraseña, puedes eliminar este bloque completo.
    path('password_reset/',
         auth_views.PasswordResetView.as_view(
             template_name='core/password_reset.html',
             email_template_name='core/password_reset_email.html',
             subject_template_name='core/password_reset_subject.txt',
             success_url='/password_reset/done/',
         ),
         name='password_reset'),
    path('password_reset/done/',
         auth_views.PasswordResetDoneView.as_view(
             template_name='core/password_reset_done.html'
         ),
         name='password_reset_done'),
    path('reset/<uidb64>/<token>/',
         auth_views.PasswordResetConfirmView.as_view(
             template_name='core/password_reset_confirm.html',
             success_url='/reset/done/',
         ),
         name='password_reset_confirm'),
    path('reset/done/',
         auth_views.PasswordResetCompleteView.as_view(
             template_name='core/password_reset_complete.html'
         ),
         name='password_reset_complete'),
]