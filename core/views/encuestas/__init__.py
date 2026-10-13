# core/views/encuestas/__init__.py

"""
Módulo de encuestas para el sistema RetenScan
Cada funcionalidad tiene su propio archivo optimizado
"""

from .list import encuesta_list
from .create import encuesta_create
from .detail import encuesta_detail
from .edit import encuesta_edit
from .respond import encuesta_responder
from .assign import encuesta_asignar
from .results import encuesta_resultados
from .delete import encuesta_delete
from .students import encuesta_estudiantes_respuestas
from .debug import debug_encuestas
from .base import (
    obtener_encuesta_con_permisos,
    obtener_estudiantes_asignados,
    obtener_estadisticas_respuestas,
    limpiar_cache_encuesta,
)

__all__ = [
    'encuesta_list',
    'encuesta_create',
    'encuesta_detail',
    'encuesta_edit',
    'encuesta_responder',
    'encuesta_asignar',
    'encuesta_resultados',
    'encuesta_delete',
    'encuesta_estudiantes_respuestas',
    'obtener_encuesta_con_permisos',
    'obtener_estudiantes_asignados',
    'obtener_estadisticas_respuestas',
    'limpiar_cache_encuesta',
    'debug',

]