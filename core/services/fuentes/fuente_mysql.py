# core/services/fuentes/fuente_mysql.py

"""
Fuente de datos desde un MySQL externo (sin pasar por Django).

Útil cuando:
  - No quieres agregar la BD externa a settings.DATABASES
  - Necesitas conexión directa con credenciales dinámicas
"""
from .fuente_base import FuenteBase, FuenteError


class FuenteMySQL(FuenteBase):
    """
    Lee datos desde MySQL usando pymysql directamente.

    Requiere: pip install pymysql
    """

    def __init__(self, host, user, password, database, query,
                 port=3306, charset='utf8mb4'):
        self.host = host
        self.user = user
        self.password = password
        self.database = database
        self.query = query
        self.port = port
        self.charset = charset

    def leer(self):
        try:
            import pymysql
            from pymysql.cursors import DictCursor
        except ImportError:
            raise FuenteError(
                "pymysql no está instalado. Ejecuta: pip install pymysql"
            )

        try:
            conn = pymysql.connect(
                host=self.host,
                port=self.port,
                user=self.user,
                password=self.password,
                database=self.database,
                charset=self.charset,
                cursorclass=DictCursor,
            )
            try:
                with conn.cursor() as cursor:
                    cursor.execute(self.query)
                    datos = cursor.fetchall()
                columnas = list(datos[0].keys()) if datos else []
                return datos, columnas
            finally:
                conn.close()
        except Exception as e:
            raise FuenteError(f"Error leyendo MySQL: {str(e)}")

    def describir(self):
        return f"MySQL[{self.host}/{self.database}]: {self.query[:80]}..."