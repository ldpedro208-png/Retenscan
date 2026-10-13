# core/services/fuentes/__init__.py

"""
Fuentes de datos para importadores.

Cada fuente implementa leer() -> (datos, columnas), donde:
  - datos: list[dict]
  - columnas: list[str]

Uso:
    from core.services.fuentes import FuenteArchivo, FuentePostgres, FuenteAPI
    
    # Desde archivo
    fuente = FuenteArchivo(archivo_subido)
    
    # Desde PostgreSQL externo
    fuente = FuentePostgres('universidad_externa', 'SELECT * FROM alumnos')
    
    # Desde API
    fuente = FuenteAPI('https://api.ejemplo.com/estudiantes', 
                       headers={'Authorization': 'Bearer XYZ'})
"""

from .fuente_base import FuenteBase, FuenteError
from .fuente_archivo import FuenteArchivo
from .fuente_postgres import FuentePostgres
from .fuente_mysql import FuenteMySQL
from .fuente_api import FuenteAPI

__all__ = [
    'FuenteBase',
    'FuenteError',
    'FuenteArchivo',
    'FuentePostgres',
    'FuenteMySQL',
    'FuenteAPI',
]