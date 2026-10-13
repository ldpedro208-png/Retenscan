# core/logging_config.py

"""
Configuración centralizada de logging para todo el proyecto
"""

import logging

# ============================================
# CONFIGURACIÓN DE LOGGING
# ============================================

def get_logger(name):
    """
    Obtiene un logger configurado con el nombre especificado.
    
    Args:
        name: Nombre del logger (usualmente __name__)
    
    Returns:
        logging.Logger: Logger configurado
    """
    logger = logging.getLogger(name)
    
    # Si ya tiene handlers, no agregar más
    if logger.handlers:
        return logger
    
    # Configurar formato
    formatter = logging.Formatter(
        '[%(asctime)s] %(levelname)s [%(name)s:%(lineno)d] - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # Handler para consola
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    # Handler para archivo (opcional)
    try:
        from logging.handlers import RotatingFileHandler
        file_handler = RotatingFileHandler(
            'logs/retenscan.log',
            maxBytes=10*1024*1024,  # 10MB
            backupCount=5
        )
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    except Exception:
        pass  # Si no se puede crear el archivo, solo usar consola
    
    # Nivel por defecto
    logger.setLevel(logging.INFO)
    
    return logger


# ============================================
# LOGGER PREDETERMINADO
# ============================================

# Logger principal de la aplicación
logger = get_logger('retenscan')

# Logger para vistas
views_logger = get_logger('retenscan.views')

# Logger para servicios
services_logger = get_logger('retenscan.services')

# Logger para modelos
models_logger = get_logger('retenscan.models')