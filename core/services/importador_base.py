# core/services/importador_base.py

"""
Clase base para todos los importadores del sistema.

Incluye:
  ✅ Lectura desde múltiples fuentes (archivo, PostgreSQL, MySQL, API REST)
  ✅ Validación de tamaño, extensión y columnas
  ✅ Normalización de nombres de columnas
  ✅ Actualización selectiva de campos (no sobrescribe con vacíos)
  ✅ Helper para limpiar campos con marca especial (__CLEAR__)
  ✅ Hook 'pre_procesar()' para que las subclases normalicen antes de validar
  ✅ Manejo robusto de errores y logging
  ✅ Fallback de universidad desde el usuario
"""
import csv
import json
import pandas as pd
from io import StringIO
from decimal import Decimal, InvalidOperation
from django.db import transaction
from django.core.exceptions import ValidationError

from ..logging_config import logger
from .fuentes import FuenteBase, FuenteArchivo, FuenteError


class ImportadorBase:
    """
    Clase base para importación de datos desde múltiples fuentes.

    Las subclases deben:
      1. Definir COLUMNAS_REQUERIDAS
      2. (Opcional) Definir MAPEO_COLUMNAS si los nombres de la fuente
         difieren de los campos del modelo.
      3. Implementar procesar_fila(self, fila, indice)
      4. (Opcional) Sobrescribir pre_procesar() si necesitan normalizar
         columnas específicas antes de la validación.
    """

    # ============================================
    # CONFIGURACIÓN (sobrescribible en subclases)
    # ============================================

    # Columnas que deben existir en la fuente
    COLUMNAS_REQUERIDAS = []

    # Mapeo opcional: {nombre_columna_fuente: nombre_campo_modelo}
    MAPEO_COLUMNAS = {}

    # Tamaño máximo de archivo (10MB por defecto) — solo aplica a FuenteArchivo
    TAMANO_MAXIMO = 10 * 1024 * 1024

    # Marca especial para indicar que un campo debe vaciarse
    VALOR_LIMPIAR = '__CLEAR__'

    # Valores que se consideran "vacíos" (no actualizan el campo)
    VALORES_VACIOS = ('', None, [], {}, 'None', 'null', 'NULL')

    # ============================================
    # CONSTRUCTOR
    # ============================================

    def __init__(self, archivo=None, universidad=None, usuario=None, fuente=None):
        """
        Inicializa el importador.

        Args:
            archivo: Archivo subido (InMemoryUploadedFile). Retrocompatible.
                     Si se pasa, se envuelve automáticamente en FuenteArchivo.
            universidad: Universidad asociada (opcional)
            usuario: Usuario que realiza la importación (opcional)
            fuente: Instancia de FuenteBase (nuevo). Si se pasa, se ignora
                    'archivo'.

        Raises:
            ValueError: si no se proporciona ni 'archivo' ni 'fuente'.
        """
        self.universidad = universidad
        self.usuario = usuario

        # ✅ Fallback: si no hay universidad, tomarla del usuario
        if self.universidad is None and self.usuario is not None:
            self.universidad = getattr(self.usuario, 'idUniversidad', None)

        # ✅ Aceptar fuente o archivo (retrocompatible)
        if fuente is not None:
            if not isinstance(fuente, FuenteBase):
                raise ValueError(
                    "El parámetro 'fuente' debe ser una instancia de FuenteBase"
                )
            self.fuente = fuente
            self.archivo = None
            self._error_inicial = None
        elif archivo is not None:
            try:
                self.fuente = FuenteArchivo(archivo)
                self._error_inicial = None
            except FuenteError as e:
                # Guardamos el error para que se muestre en get_resumen()
                self.fuente = None
                self._error_inicial = str(e)
            self.archivo = archivo  # retrocompatibilidad
        else:
            raise ValueError("Debes proporcionar 'archivo' o 'fuente'")

        # Estado interno
        self.errores = []
        self.advertencias = []
        self.exitos = 0
        self.actualizados = 0
        self.datos = []
        self.columnas = []

        # Si hubo error al construir FuenteArchivo, lo registramos
        if self._error_inicial:
            self.errores.append(self._error_inicial)

    # ============================================
    # LECTURA DE LA FUENTE
    # ============================================

    def leer_fuente(self):
        """
        Lee los datos desde la fuente (archivo, BD, API, etc.).

        Returns:
            tuple[list[dict] | None, list[str] | None]:
                - (datos, columnas) si OK
                - (None, None) si hay error (el error queda en self.errores)
        """
        if self.fuente is None:
            # Ya hay error registrado en __init__
            if not self.errores:
                self.errores.append("No se configuró una fuente de datos válida")
            return None, None

        try:
            datos, columnas = self.fuente.leer()
            self.datos = datos or []
            self.columnas = columnas or []
            logger.info(
                f"Fuente leída: {self.fuente.describir()} "
                f"({len(self.datos)} filas, {len(self.columnas)} columnas)"
            )
            return self.datos, self.columnas
        except FuenteError as e:
            self.errores.append(str(e))
            logger.error(f"Error en fuente {self.fuente.describir()}: {str(e)}")
            return None, None
        except Exception as e:
            self.errores.append(f"Error inesperado leyendo fuente: {str(e)}")
            logger.error(f"Error inesperado leyendo fuente: {str(e)}")
            return None, None

    # ============================================
    # RETROCOMPATIBILIDAD
    # ============================================

    def validar_archivo(self):
        """
        Deprecated. La validación ahora está en FuenteArchivo.
        Se mantiene por retrocompatibilidad con código que lo llame.
        """
        return True

    def leer_archivo(self):
        """
        Deprecated. Usa leer_fuente().
        Se mantiene por retrocompatibilidad.
        """
        datos, _ = self.leer_fuente()
        return datos

    # ============================================
    # NORMALIZACIÓN DE COLUMNAS
    # ============================================

    def normalizar_columnas(self):
        """
        Normaliza los nombres de columnas:
          - minúsculas
          - espacios → guiones bajos
          - strip

        También aplica MAPEO_COLUMNAS si está definido en la subclase.

        Modifica self.datos y self.columnas en su lugar.
        """
        if not self.datos:
            return

        # Construir mapa: nombre_normalizado → nombre_original
        mapa_normalizado = {
            str(c).strip().lower().replace(' ', '_'): c
            for c in (self.columnas or [])
        }

        # Aplicar mapeo de columnas si está definido
        if self.MAPEO_COLUMNAS:
            for nombre_fuente, nombre_modelo in self.MAPEO_COLUMNAS.items():
                if nombre_fuente in mapa_normalizado:
                    original = mapa_normalizado[nombre_fuente]
                    for fila in self.datos:
                        if original in fila:
                            fila[nombre_modelo] = fila.pop(original)

        # Renombrar todas las claves de las filas a su forma normalizada
        for fila in self.datos:
            nuevas = {}
            for clave, valor in fila.items():
                clave_str = str(clave)
                clave_norm = clave_str.strip().lower().replace(' ', '_')
                # Si el mapeo ya renombró, respetar el nombre del modelo
                if clave_str in self.MAPEO_COLUMNAS.values():
                    nuevas[clave_str] = valor
                else:
                    nuevas[clave_norm] = valor
            fila.clear()
            fila.update(nuevas)

        # Actualizar self.columnas
        self.columnas = list(self.datos[0].keys()) if self.datos else []

    # ============================================
    # VALIDACIÓN DE COLUMNAS
    # ============================================

    def validar_columnas(self):
        """Valida que la fuente tenga las columnas requeridas."""
        if not self.COLUMNAS_REQUERIDAS:
            return True

        columnas_normalizadas = {
            str(c).strip().lower().replace(' ', '_')
            for c in (self.columnas or [])
        }

        columnas_faltantes = []
        for col in self.COLUMNAS_REQUERIDAS:
            col_norm = str(col).strip().lower().replace(' ', '_')
            if col_norm not in columnas_normalizadas:
                columnas_faltantes.append(col)

        if columnas_faltantes:
            self.errores.append(
                f"Columnas requeridas faltantes: {', '.join(columnas_faltantes)}"
            )
            return False

        return True

    # ============================================
    # HELPERS DE LIMPIEZA Y CONVERSIÓN
    # ============================================

    def limpiar_valor(self, valor):
        """
        Limpia un valor:
          - strings: strip
          - NaN de pandas: ''
          - None: ''
        """
        # Detectar NaN de pandas
        try:
            if pd.isna(valor):
                return ''
        except (TypeError, ValueError):
            pass

        if isinstance(valor, str):
            return valor.strip()
        if valor is None:
            return ''
        return valor

    def parse_decimal(self, valor, default=0):
        """Convierte un valor a Decimal, manejando errores."""
        if valor is None or valor == '':
            return Decimal(str(default)) if default is not None else None
        try:
            return Decimal(str(valor))
        except (InvalidOperation, ValueError, TypeError):
            return Decimal(str(default)) if default is not None else None

    def parse_int(self, valor, default=None):
        """Convierte un valor a int, manejando errores."""
        if valor is None or valor == '':
            return default
        try:
            return int(float(str(valor).strip()))
        except (ValueError, TypeError):
            return default

    def parse_bool(self, valor, default=False):
        """Convierte un valor a bool."""
        if valor is None or valor == '':
            return default
        if isinstance(valor, bool):
            return valor
        return str(valor).strip().lower() in (
            'true', '1', 'sí', 'si', 'yes', 'y', 'verdadero'
        )

    # ============================================
    # ✅ HELPER PRINCIPAL: ACTUALIZACIÓN SELECTIVA
    # ============================================

    def actualizar_si_viene(self, instancia, campo, valor, permitir_limpiar=False):
        """
        Actualiza un campo SOLO si el valor viene con contenido.

        Reglas:
          - Si valor es vacío (None, '', [], {}) → NO tocar el campo existente.
          - Si valor == VALOR_LIMPIAR y permitir_limpiar=True → asignar None.
          - En cualquier otro caso → asignar el valor.

        Args:
            instancia: objeto Django (o cualquier objeto con setattr)
            campo: nombre del campo a actualizar
            valor: valor a asignar
            permitir_limpiar: si True, permite borrar el campo con VALOR_LIMPIAR

        Returns:
            bool: True si se actualizó, False si se omitió.
        """
        # Normalizar strings
        if isinstance(valor, str):
            valor = valor.strip()

        # ¿Es una marca de limpieza?
        if permitir_limpiar and valor == self.VALOR_LIMPIAR:
            setattr(instancia, campo, None)
            return True

        # ¿Está vacío? → no tocar
        if valor in self.VALORES_VACIOS:
            return False

        # ¿El valor ya es igual al que tiene? → no hace falta actualizar
        if getattr(instancia, campo, None) == valor:
            return False

        setattr(instancia, campo, valor)
        return True

    def actualizar_campos_si_vienen(self, instancia, campos, permitir_limpiar=False):
        """
        Actualiza múltiples campos a la vez usando actualizar_si_viene().

        Args:
            instancia: objeto Django
            campos: dict {nombre_campo: valor}
            permitir_limpiar: si True, permite borrar campos con VALOR_LIMPIAR

        Returns:
            int: número de campos actualizados.
        """
        actualizados = 0
        for campo, valor in campos.items():
            if self.actualizar_si_viene(instancia, campo, valor, permitir_limpiar):
                actualizados += 1
        return actualizados

    # ============================================
    # HOOKS DE PROCESAMIENTO
    # ============================================

    def pre_procesar(self):
        """
        Hook que se ejecuta después de leer la fuente y antes de
        normalizar/validar columnas.

        Sobrescribir en subclases que necesiten transformar los datos
        crudos (por ejemplo, unir apellido_paterno + apellido_materno).

        Por defecto no hace nada.
        """
        pass

    def procesar_fila(self, fila, indice):
        """
        Procesa una fila de la fuente.
        Debe ser implementado por las subclases.

        Args:
            fila: dict con los datos de la fila
            indice: número de fila (para mensajes de error)
        """
        raise NotImplementedError("Las subclases deben implementar procesar_fila()")

    # ============================================
    # PROCESAMIENTO PRINCIPAL
    # ============================================

    def procesar(self):
        """
        Procesa toda la fuente.

        Flujo:
          1. Leer fuente
          2. pre_procesar()  ← hook para subclases
          3. Normalizar columnas
          4. Validar columnas requeridas
          5. Procesar cada fila
          6. Devolver resumen
        """
        # 1. Leer fuente
        datos, _ = self.leer_fuente()
        if datos is None:
            return self.get_resumen()

        # 2. Hook pre_procesar (normalización específica de subclases)
        try:
            self.pre_procesar()
        except Exception as e:
            self.errores.append(f"Error en pre_procesar: {str(e)}")
            logger.error(f"Error en pre_procesar: {str(e)}")
            return self.get_resumen()

        # 3. Normalizar nombres de columnas
        self.normalizar_columnas()

        # 4. Validar columnas requeridas
        if not self.validar_columnas():
            return self.get_resumen()

        # 5. Procesar filas
        total_filas = len(self.datos)
        if total_filas == 0:
            self.advertencias.append("La fuente no contiene filas de datos.")

        for idx, fila in enumerate(self.datos, start=2):
            try:
                self.procesar_fila(fila, idx)
            except Exception as e:
                error_msg = f"Fila {idx}: {str(e)}"
                self.errores.append(error_msg)
                logger.error(error_msg)

        return self.get_resumen()

    # ============================================
    # RESULTADOS
    # ============================================

    def get_resumen(self):
        """Retorna un resumen del procesamiento."""
        return {
            'exitos': self.exitos,
            'actualizados': self.actualizados,
            'errores': self.errores,
            'advertencias': self.advertencias,
            'total_procesados': len(self.datos),
            'total_errores': len(self.errores),
        }

    def get_estadisticas(self):
        """Retorna estadísticas del procesamiento."""
        total = len(self.datos)
        return {
            'total_filas': total,
            'exitosas': self.exitos,
            'actualizadas': self.actualizados,
            'errores': len(self.errores),
            'tasa_exito': round(
                (self.exitos / total * 100) if total > 0 else 0, 2
            ),
        }