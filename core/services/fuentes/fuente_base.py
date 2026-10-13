# core/services/fuentes/fuente_base.py

"""
Interfaz abstracta para todas las fuentes de datos.

Una fuente es cualquier cosa que pueda devolver:
  - datos: list[dict]  (cada dict es una fila)
  - columnas: list[str]  (nombres de columnas)

Esto permite que el importador trabaje igual con:
  - Archivos (CSV, Excel, JSON)
  - Bases de datos externas (PostgreSQL, MySQL, SQL Server)
  - APIs REST
  - Google Sheets
  - Cualquier otra fuente que se te ocurra
"""
from abc import ABC, abstractmethod


class FuenteError(Exception):
    """Excepción genérica para errores de fuentes."""
    pass


class FuenteBase(ABC):
    """
    Clase base para todas las fuentes de datos.

    Las subclases DEBEN implementar:
      - leer() -> (datos, columnas)
      - describir() -> str  (opcional pero recomendado)
    """

    @abstractmethod
    def leer(self):
        """
        Lee los datos de la fuente.

        Returns:
            tuple[list[dict], list[str]]:
                - datos: lista de diccionarios (una entrada por fila)
                - columnas: lista de nombres de columnas

        Raises:
            FuenteError: si hay un problema al leer
        """
        raise NotImplementedError

    def describir(self):
        """
        Devuelve una descripción legible de la fuente (para logs/UI).
        Sobrescribir en subclases.
        """
        return self.__class__.__name__

    def __repr__(self):
        return f"<{self.__class__.__name__}: {self.describir()}>"