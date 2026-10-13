# core/decorators.py - Crear este archivo

from functools import wraps
from django.core.cache import cache
from django.utils import timezone
import hashlib
import json


def cache_view(timeout=300, key_prefix=''):
    """
    Decorador para cachear vistas con llave dinámica basada en usuario y parámetros
    """
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            # Construir llave de caché
            user_id = request.user.id if request.user.is_authenticated else 'anonymous'
            user_rol = getattr(request.user, 'rol', 'anonimo')
            universidad_id = getattr(request.user, 'idUniversidad_id', None)
            
            # Incluir parámetros de URL
            url_params = request.GET.urlencode()
            
            # Crear llave única
            key_data = f"{key_prefix}_{user_id}_{user_rol}_{universidad_id}_{url_params}_{args}_{kwargs}"
            cache_key = hashlib.md5(key_data.encode()).hexdigest()
            
            # Intentar obtener de caché
            cached_response = cache.get(cache_key)
            if cached_response is not None:
                return cached_response
            
            # Si no está en caché, ejecutar la vista
            response = view_func(request, *args, **kwargs)
            
            # Guardar en caché (solo si es exitoso)
            if response.status_code == 200:
                cache.set(cache_key, response, timeout)
            
            return response
        return wrapper
    return decorator


def invalidate_cache(key_pattern):
    """
    Invalida entradas de caché que coinciden con un patrón
    """
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            response = view_func(request, *args, **kwargs)
            # Limpiar caché después de modificar datos
            cache.delete_pattern(key_pattern)
            return response
        return wrapper
    return decorator