# core/services/fuentes/fuente_api.py

"""
Fuente de datos desde una API REST que devuelve JSON.
"""
from .fuente_base import FuenteBase, FuenteError


class FuenteAPI(FuenteBase):
    """
    Lee datos desde una API REST.

    Uso:
        fuente = FuenteAPI(
            url='https://api.universidad.edu/estudiantes',
            headers={'Authorization': 'Bearer XYZ'},
            ruta_datos='data.items',  # opcional si viene anidado
        )
        datos, columnas = fuente.leer()
    """

    def __init__(self, url, headers=None, metodo='GET', data=None,
                 ruta_datos=None, timeout=30, params=None):
        self.url = url
        self.headers = headers or {}
        self.metodo = metodo.upper()
        self.data = data
        self.ruta_datos = ruta_datos
        self.timeout = timeout
        self.params = params or {}

    def leer(self):
        try:
            import requests
        except ImportError:
            raise FuenteError(
                "requests no está instalado. Ejecuta: pip install requests"
            )

        try:
            if self.metodo == 'POST':
                response = requests.post(
                    self.url,
                    json=self.data,
                    headers=self.headers,
                    params=self.params,
                    timeout=self.timeout,
                )
            else:
                response = requests.get(
                    self.url,
                    headers=self.headers,
                    params=self.params,
                    timeout=self.timeout,
                )

            response.raise_for_status()
            payload = response.json()

            # Navegar ruta anidada si aplica: 'data.items' → payload['data']['items']
            if self.ruta_datos:
                for parte in self.ruta_datos.split('.'):
                    if not isinstance(payload, dict) or parte not in payload:
                        raise FuenteError(
                            f"Ruta '{self.ruta_datos}' no encontrada en la respuesta"
                        )
                    payload = payload[parte]

            if not isinstance(payload, list):
                raise FuenteError(
                    "La API no devolvió una lista de registros. "
                    "Revisa 'ruta_datos'."
                )

            columnas = list(payload[0].keys()) if payload else []
            return payload, columnas

        except FuenteError:
            raise
        except Exception as e:
            raise FuenteError(f"Error consultando API: {str(e)}")

    def describir(self):
        return f"API[{self.metodo} {self.url}]"