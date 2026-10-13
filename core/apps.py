# core/apps.py

from django.apps import AppConfig
import logging

logger = logging.getLogger(__name__)


class CoreConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'core'
    
    def ready(self):
        """
        Método que se ejecuta cuando la aplicación está lista.
        Importa las señales para que se registren.
        """
        try:
            # ✅ Importar señales y registrar
            from .signals import register_signals
            register_signals()
            logger.info("✅ Aplicación core cargada correctamente con señales")
        except Exception as e:
            logger.error(f"❌ Error cargando señales de core: {e}")