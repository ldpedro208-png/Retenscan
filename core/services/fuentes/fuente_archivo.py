# core/services/fuentes/fuente_archivo.py

"""
Fuente de datos desde archivo (CSV, Excel, JSON).
Reutiliza la lógica que ya tenías en ImportadorBase.
"""
import csv
import json
import pandas as pd
from io import StringIO

from .fuente_base import FuenteBase, FuenteError


class FuenteArchivo(FuenteBase):
    """
    Lee datos desde un archivo subido (InMemoryUploadedFile o similar).

    Soporta: .csv, .xlsx, .xls, .json
    """

    EXTENSIONES_VALIDAS = ['csv', 'xlsx', 'xls', 'json']
    TAMANO_MAXIMO = 10 * 1024 * 1024  # 10 MB

    def __init__(self, archivo):
        self.archivo = archivo
        self._validar()

    def _validar(self):
        """Valida tamaño y extensión."""
        if self.archivo is None:
            raise FuenteError("No se proporcionó archivo")

        if self.archivo.size > self.TAMANO_MAXIMO:
            raise FuenteError(
                f"El archivo es demasiado grande. "
                f"Máximo {self.TAMANO_MAXIMO // (1024 * 1024)}MB."
            )

        extension = self._extension()
        if extension not in self.EXTENSIONES_VALIDAS:
            raise FuenteError(
                f"Formato de archivo no soportado: {extension}. "
                f"Usa CSV, Excel o JSON."
            )

    def _extension(self):
        return self.archivo.name.split('.')[-1].lower()

    def leer(self):
        """Lee el archivo según su extensión."""
        extension = self._extension()

        try:
            if extension == 'csv':
                return self._leer_csv()
            elif extension in ['xlsx', 'xls']:
                return self._leer_excel()
            elif extension == 'json':
                return self._leer_json()
        except FuenteError:
            raise
        except Exception as e:
            raise FuenteError(f"Error al leer el archivo: {str(e)}")

    def _leer_csv(self):
        """Lee CSV con detección automática de delimitador."""
        content = self.archivo.read().decode('utf-8-sig')

        # Detectar delimitador
        primera_linea = content.split('\n', 1)[0]
        delimitador = ';' if primera_linea.count(';') > primera_linea.count(',') else ','

        io = StringIO(content)
        reader = csv.DictReader(io, delimiter=delimitador)
        columnas = reader.fieldnames or []
        datos = list(reader)
        return datos, columnas

    def _leer_excel(self):
        """Lee Excel (.xlsx, .xls)."""
        df = pd.read_excel(self.archivo)
        df.columns = [str(c).strip() for c in df.columns]
        columnas = df.columns.tolist()
        datos = df.to_dict('records')
        return datos, columnas

    def _leer_json(self):
        """Lee JSON (lista o dict con clave 'data')."""
        content = self.archivo.read().decode('utf-8')
        data = json.loads(content)

        if isinstance(data, list):
            columnas = list(data[0].keys()) if data else []
            return data, columnas
        elif isinstance(data, dict) and 'data' in data:
            datos = data['data']
            columnas = list(datos[0].keys()) if datos else []
            return datos, columnas
        else:
            raise FuenteError(
                "Formato JSON inválido. Debe ser una lista "
                "o tener una clave 'data'."
            )

    def describir(self):
        return f"Archivo: {self.archivo.name}"