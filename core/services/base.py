# core/services/base.py
"""
Servicios base y utilidades compartidas
"""
import logging
import sys
import codecs

# Configurar encoding para Windows
if sys.platform == 'win32':
    try:
        sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
        sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')
    except:
        pass

# Configurar logger
logger = logging.getLogger(__name__)

class BaseService:
    """Clase base para todos los servicios"""
    
    @staticmethod
    def log_info(mensaje):
        """Log de información"""
        logger.info(mensaje)
    
    @staticmethod
    def log_warning(mensaje):
        """Log de advertencia"""
        logger.warning(mensaje)
    
    @staticmethod
    def log_error(mensaje):
        """Log de error"""
        logger.error(mensaje)
    
    @staticmethod
    def log_debug(mensaje):
        """Log de debug"""
        logger.debug(mensaje)