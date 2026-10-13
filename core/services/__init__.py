# core/services/__init__.py

"""
Servicios de la aplicación RetenScan.

⚠️ IMPORTANTE:
Este __init__.py es intencionalmente minimalista para evitar
importaciones circulares con Django.

Cada servicio se importa EXPLÍCITAMENTE desde su módulo:

    from core.services.ai_service import AIService
    from core.services.alert_service import AlertaService
    from core.services.importador_estudiantes import ImportadorEstudiantes

NO importar servicios aquí. Hacerlo causa que Django falle
al cargar `core.models` antes de que las apps estén listas.
"""

# Solo exponer lo que NO depende de Django
from .base import BaseService

__all__ = ['BaseService']