# core/views/encuestas.py - VERSIÓN FINAL (Router principal)

"""
Vistas para encuestas - Redirige al módulo de encuestas
"""
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
]