# core/views/admin/__init__.py

"""
Módulo de vistas de administración
"""

from .carreras import (
    carrera_list,
    carrera_create,
    carrera_detail,
    carrera_edit,
    carrera_delete,
    carrera_api,
)

__all__ = [
    'carrera_list',
    'carrera_create',
    'carrera_detail',
    'carrera_edit',
    'carrera_delete',
    'carrera_api',
]