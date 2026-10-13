# core/services/ai_service.py
"""
Servicio de IA - Carga lazy y thread-safe de modelos predictivos.

Este módulo centraliza el acceso a los servicios de IA del sistema.
"""
import logging
import threading
from .base import BaseService

logger = logging.getLogger(__name__)


# ============================================
# IMPORT ÚNICO (a nivel de módulo)
# ============================================
try:
    from core.ml.models import ServicioPrediccion, ModeloPredictivoDesercion
    ML_DISPONIBLE = True
except ImportError as e:
    logger.warning(f"⚠️ Módulo ML no disponible: {e}")
    ServicioPrediccion = None
    ModeloPredictivoDesercion = None
    ML_DISPONIBLE = False


# ============================================
# CACHÉ GLOBAL CON THREAD-SAFETY
# ============================================
_servicio_prediccion = None
_modelo_predictivo = None
_lock_servicio = threading.Lock()
_lock_modelo = threading.Lock()


def _crear_servicio_prediccion():
    """Crea una nueva instancia del servicio de predicción (sin caché)."""
    if not ML_DISPONIBLE or ServicioPrediccion is None:
        logger.warning("ServicioPrediccion no disponible (ML no instalado)")
        return None
    try:
        servicio = ServicioPrediccion(auto_entrenar=False)
        logger.info("✅ Servicio de predicción creado")
        return servicio
    except Exception as e:
        logger.error(f"❌ Error creando servicio de predicción: {e}", exc_info=True)
        return None


def _crear_modelo_predictivo():
    """Crea una nueva instancia del modelo predictivo (sin caché)."""
    if not ML_DISPONIBLE or ModeloPredictivoDesercion is None:
        logger.warning("ModeloPredictivoDesercion no disponible (ML no instalado)")
        return None
    try:
        modelo = ModeloPredictivoDesercion(auto_cargar=True)
        if modelo and getattr(modelo, 'modelo', None) is not None:
            logger.info("✅ Modelo predictivo cargado")
        else:
            logger.info("ℹ️ Modelo predictivo inicializado (sin modelo entrenado)")
        return modelo
    except Exception as e:
        logger.error(f"❌ Error creando modelo predictivo: {e}", exc_info=True)
        return None


def get_servicio_prediccion(force_new=False):
    """
    Obtiene el servicio de predicción.

    Args:
        force_new: Si es True, crea una instancia nueva (ignora la caché).

    Returns:
        ServicioPrediccion | None
    """
    global _servicio_prediccion

    if force_new:
        return _crear_servicio_prediccion()

    if _servicio_prediccion is None:
        with _lock_servicio:
            if _servicio_prediccion is None:
                _servicio_prediccion = _crear_servicio_prediccion()

    return _servicio_prediccion


def get_modelo_predictivo(force_new=False):
    """
    Obtiene el modelo predictivo.

    Args:
        force_new: Si es True, crea una instancia nueva (ignora la caché).

    Returns:
        ModeloPredictivoDesercion | None
    """
    global _modelo_predictivo

    if force_new:
        return _crear_modelo_predictivo()

    if _modelo_predictivo is None:
        with _lock_modelo:
            if _modelo_predictivo is None:
                _modelo_predictivo = _crear_modelo_predictivo()

    return _modelo_predictivo


# Alias para compatibilidad con código existente
obtener_servicio_prediccion = get_servicio_prediccion
obtener_modelo_predictivo = get_modelo_predictivo


# ============================================
# RESET (útil cuando se re-entrena el modelo)
# ============================================

def reset_servicio_prediccion():
    """Invalida la caché del servicio de predicción."""
    global _servicio_prediccion
    with _lock_servicio:
        _servicio_prediccion = None
    logger.info("🔄 Caché del servicio de predicción invalidada")


def reset_modelo_predictivo():
    """Invalida la caché del modelo predictivo."""
    global _modelo_predictivo
    with _lock_modelo:
        _modelo_predictivo = None
    logger.info("🔄 Caché del modelo predictivo invalidada")


def reset_all():
    """Invalida todas las cachés de IA."""
    reset_servicio_prediccion()
    reset_modelo_predictivo()


# ============================================
# AIService (wrapper con métodos de negocio)
# ============================================

class AIService(BaseService):
    """Servicio de IA con métodos de conveniencia."""

    @staticmethod
    def predecir_riesgo(estudiante_id, datos_adicionales=None):
        """
        Predice el riesgo de deserción para un estudiante.

        Args:
            estudiante_id: ID del estudiante (int).
            datos_adicionales: dict opcional con features extra.

        Returns:
            dict | None: Predicción con nivel_riesgo, probabilidad, etc.
        """
        if not isinstance(estudiante_id, int) or estudiante_id <= 0:
            logger.warning(f"⚠️ estudiante_id inválido: {estudiante_id}")
            return None

        servicio = get_servicio_prediccion()
        if not servicio:
            logger.warning("Servicio de predicción no disponible")
            return None

        if not hasattr(servicio, 'predecir'):
            logger.error("El servicio no tiene método 'predecir'")
            return None

        try:
            resultado = servicio.predecir(estudiante_id, datos_adicionales)
            if resultado:
                logger.debug(f"✅ Predicción generada para estudiante {estudiante_id}")
            return resultado
        except Exception as e:
            logger.error(
                f"❌ Error prediciendo riesgo para estudiante {estudiante_id}: {e}",
                exc_info=True
            )
            return None

    @staticmethod
    def entrenar_modelo(datos_entrenamiento=None, invalidar_cache=True):
        """
        Entrena el modelo predictivo.

        Args:
            datos_entrenamiento: datos opcionales para el entrenamiento.
            invalidar_cache: si True, resetea la caché después de entrenar.

        Returns:
            bool: True si el entrenamiento fue exitoso.
        """
        servicio = get_servicio_prediccion()
        if not servicio:
            logger.warning("Servicio de predicción no disponible")
            return False

        if not hasattr(servicio, 'entrenar'):
            logger.error("El servicio no tiene método 'entrenar'")
            return False

        try:
            resultado = servicio.entrenar(datos_entrenamiento)
            if resultado:
                logger.info("✅ Modelo entrenado exitosamente")
                if invalidar_cache:
                    reset_all()
            else:
                logger.warning("⚠️ El entrenamiento no devolvió éxito")
            return bool(resultado)
        except Exception as e:
            logger.error(f"❌ Error entrenando modelo: {e}", exc_info=True)
            return False

    @staticmethod
    def esta_disponible():
        """Verifica si el módulo ML está cargado."""
        return ML_DISPONIBLE

    @staticmethod
    def info():
        """Devuelve información del estado del servicio."""
        return {
            'ml_disponible': ML_DISPONIBLE,
            'servicio_cargado': _servicio_prediccion is not None,
            'modelo_cargado': _modelo_predictivo is not None,
            'modelo_entrenado': (
                _modelo_predictivo is not None
                and getattr(_modelo_predictivo, 'modelo', None) is not None
            ),
        }