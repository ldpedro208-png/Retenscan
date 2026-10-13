# core/services/importador_becas.py

"""
Importador de becas desde archivos CSV, Excel, JSON,
PostgreSQL, MySQL o API REST.

✅ Acepta fuente= (archivo, BD, API)
✅ Actualización selectiva: no sobrescribe con vacíos
✅ Normaliza tipo, estado y montos
"""
from decimal import Decimal

from django.db import transaction

from ..models import Beca, CatalogoUniversidad
from .importador_base import ImportadorBase
from ..logging_config import logger


class ImportadorBecas(ImportadorBase):
    """
    Importador de becas.

    Uso:
        # Desde archivo
        imp = ImportadorBecas(archivo=request.FILES['archivo'],
                              universidad=u, usuario=request.user,
                              actualizar_existentes=True)

        # Desde PostgreSQL externo
        fuente = FuentePostgres('bd_externa', 'SELECT * FROM becas')
        imp = ImportadorBecas(fuente=fuente, universidad=u, usuario=request.user)
    """

    COLUMNAS_REQUERIDAS = ['nombre', 'codigo', 'tipo', 'monto']

    TIPOS_VALIDOS = [
        'Académica', 'Deportiva', 'Cultural', 'Social',
        'Investigación', 'Excelencia', 'Necesidad', 'Otra'
    ]

    ESTADOS_VALIDOS = ['Activa', 'Inactiva', 'Completa', 'Cancelada']

    # Normalización de tipos (input → canónico)
    MAPA_TIPOS = {
        'academica': 'Académica',
        'académica': 'Académica',
        'deportiva': 'Deportiva',
        'cultural': 'Cultural',
        'social': 'Social',
        'investigacion': 'Investigación',
        'investigación': 'Investigación',
        'excelencia': 'Excelencia',
        'necesidad': 'Necesidad',
        'otra': 'Otra',
    }

    MAPA_ESTADOS = {
        'activa': 'Activa',
        'inactiva': 'Inactiva',
        'completa': 'Completa',
        'cancelada': 'Cancelada',
    }

    def __init__(self, archivo=None, universidad=None, usuario=None,
                 actualizar_existentes=False, fuente=None):
        super().__init__(archivo=archivo, universidad=universidad,
                         usuario=usuario, fuente=fuente)
        self.actualizar_existentes = actualizar_existentes

    # ============================================
    # HELPERS
    # ============================================

    def _normalizar_tipo(self, tipo_raw):
        """Convierte el tipo a su forma canónica."""
        if not tipo_raw:
            return 'Académica'
        clave = str(tipo_raw).strip().lower()
        if clave in self.MAPA_TIPOS:
            return self.MAPA_TIPOS[clave]
        # Si ya es un tipo válido con mayúsculas correctas
        if tipo_raw in self.TIPOS_VALIDOS:
            return tipo_raw
        return None

    def _normalizar_estado(self, estado_raw):
        """Convierte el estado a su forma canónica."""
        if not estado_raw:
            return None  # no forzar; se conservará el existente
        clave = str(estado_raw).strip().lower()
        if clave in self.MAPA_ESTADOS:
            return self.MAPA_ESTADOS[clave]
        if estado_raw in self.ESTADOS_VALIDOS:
            return estado_raw
        return None

    # ============================================
    # PROCESAMIENTO DE FILA
    # ============================================

    def procesar_fila(self, fila, indice):
        """Procesa una fila de becas."""

        # --- Lectura y limpieza ---
        nombre = self.limpiar_valor(fila.get('nombre', ''))
        codigo = self.limpiar_valor(fila.get('codigo', ''))
        tipo_raw = self.limpiar_valor(fila.get('tipo', ''))
        monto_raw = fila.get('monto', None)
        descripcion = self.limpiar_valor(fila.get('descripcion', ''))
        duracion_meses = self.parse_int(fila.get('duracion_meses'), default=None)
        cupos = self.parse_int(fila.get('cupos_disponibles'), default=None)
        estado_raw = self.limpiar_valor(fila.get('estado', ''))
        porcentaje_raw = fila.get('porcentaje_cobertura', None)
        fecha_inicio = self.limpiar_valor(fila.get('fecha_inicio', ''))
        fecha_fin = self.limpiar_valor(fila.get('fecha_fin', ''))

        # --- Validaciones obligatorias ---
        if not nombre:
            raise ValueError("Nombre es obligatorio")
        if not codigo:
            raise ValueError("Código es obligatorio")

        # Normalizar tipo
        tipo = self._normalizar_tipo(tipo_raw)
        if tipo is None:
            raise ValueError(
                f"Tipo '{tipo_raw}' inválido. "
                f"Válidos: {', '.join(self.TIPOS_VALIDOS)}"
            )

        # Normalizar monto
        monto = self.parse_decimal(monto_raw, default=None)
        if monto is None or monto <= 0:
            raise ValueError("Monto debe ser mayor a 0")

        # Normalizar estado
        estado = self._normalizar_estado(estado_raw)

        # Normalizar porcentaje
        porcentaje = self.parse_decimal(porcentaje_raw, default=None) if porcentaje_raw not in (None, '') else None

        # --- Buscar beca existente ---
        beca_existente = Beca.objects.filter(codigo=codigo).first()

        if beca_existente and not self.actualizar_existentes:
            self.advertencias.append(f"Beca '{codigo}' ya existe (omitido)")
            return

        with transaction.atomic():
            if beca_existente:
                # ✅ ACTUALIZACIÓN SELECTIVA: solo lo que viene con valor
                self.actualizar_campos_si_vienen(beca_existente, {
                    'nombre': nombre,
                    'tipo': tipo,
                    'monto': monto,
                    'descripcion': descripcion,
                    'duracion_meses': duracion_meses,
                    'cupos_disponibles': cupos,
                    'estado': estado,
                    'porcentaje_cobertura': porcentaje,
                    'fecha_inicio': fecha_inicio,
                    'fecha_fin': fecha_fin,
                }, permitir_limpiar=True)
                beca_existente.save()
                self.actualizados += 1
                logger.info(f"✅ Beca actualizada: {codigo}")
            else:
                # ✅ CREAR NUEVA
                Beca.objects.create(
                    nombre=nombre,
                    codigo=codigo,
                    tipo=tipo,
                    monto=monto,
                    descripcion=descripcion or None,
                    duracion_meses=duracion_meses if duracion_meses is not None else 12,
                    cupos_disponibles=cupos if cupos is not None else 0,
                    estado=estado or 'Activa',
                    porcentaje_cobertura=porcentaje,
                    fecha_inicio=fecha_inicio or None,
                    fecha_fin=fecha_fin or None,
                    idUniversidad=self.universidad,
                )
                self.exitos += 1
                logger.info(f"✅ Beca creada: {codigo}")