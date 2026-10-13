# core/services/fuentes/fuente_postgres.py

"""
Fuente de datos desde otra base de datos PostgreSQL.

Usa el sistema multi-DB de Django: la BD externa debe estar
configurada en settings.DATABASES con un alias.
"""
from django.db import connections
from django.db.utils import OperationalError, ProgrammingError

from .fuente_base import FuenteBase, FuenteError


class FuentePostgres(FuenteBase):
    """
    Lee datos desde otra base de datos PostgreSQL usando Django.

    Requiere que la BD externa esté configurada en settings.DATABASES
    con un alias, por ejemplo:

        DATABASES = {
            'default': {...},
            'universidad_externa': {
                'ENGINE': 'django.db.backends.postgresql',
                'NAME': 'bd_universidad',
                'HOST': '190.129.x.x',
                'USER': 'lector',
                'PASSWORD': '***',
            },
        }

    Uso:
        fuente = FuentePostgres(
            database_alias='universidad_externa',
            query='SELECT carnet, nombres, apellidos, email FROM alumnos WHERE activo = %s',
            params=[True]
        )
        datos, columnas = fuente.leer()
    """

    def __init__(self, database_alias, query, params=None):
        self.database_alias = database_alias
        self.query = query
        self.params = params or []

        # Validar que el alias existe
        if database_alias not in connections:
            raise FuenteError(
                f"Alias de base de datos '{database_alias}' no está "
                f"configurado en settings.DATABASES."
            )

    def leer(self):
        try:
            with connections[self.database_alias].cursor() as cursor:
                cursor.execute(self.query, self.params)
                columnas = [col[0] for col in cursor.description]
                filas = cursor.fetchall()
                datos = [dict(zip(columnas, fila)) for fila in filas]
            return datos, columnas
        except (OperationalError, ProgrammingError) as e:
            raise FuenteError(f"Error consultando '{self.database_alias}': {str(e)}")
        except Exception as e:
            raise FuenteError(f"Error inesperado leyendo PostgreSQL: {str(e)}")

    def describir(self):
        return f"PostgreSQL[{self.database_alias}]: {self.query[:80]}..."