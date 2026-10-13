
# core/services/stats_service.py
"""
Servicio de estadísticas con caché
"""
import logging
from django.core.cache import cache
from django.db.models import Count
from .base import BaseService

logger = logging.getLogger(__name__)


class EstadisticasService(BaseService):
    """Servicio para obtener estadísticas con caché"""
    
    CACHE_TIMEOUT = {
        'global': 600,  # 10 minutos
        'carreras': 900,  # 15 minutos
        'estados': 600,  # 10 minutos
        'riesgo': 900,  # 15 minutos
    }
    
    @classmethod
    def _get_estudiantes_queryset(cls, universidad_id=None):
        """Obtiene el queryset base de estudiantes"""
        from core.models import Estudiante  # Import absoluto
        
        estudiantes_qs = Estudiante.objects.all()
        if universidad_id:
            estudiantes_qs = estudiantes_qs.filter(
                idCarrera__idUniversidad_id=universidad_id
            )
        return estudiantes_qs
    
    @classmethod
    def get_estadisticas_globales(cls, universidad_id=None):
        """Obtiene estadísticas globales con caché"""
        cache_key = f'estadisticas_globales_{universidad_id}'
        stats = cache.get(cache_key)
        
        if not stats:
            logger.info(f"Calculando estadísticas globales para universidad: {universidad_id}")
            
            from core.models import RiesgoEstudiante, HistorialAcademico  # Import absoluto
            
            estudiantes_qs = cls._get_estudiantes_queryset(universidad_id)
            estudiantes_ids = estudiantes_qs.values_list('idEstudiante', flat=True)
            
            stats = {
                'total': estudiantes_qs.count(),
                'activos': estudiantes_qs.filter(estado='Activo').count(),
                'en_riesgo': RiesgoEstudiante.objects.filter(
                    idEstudiante__in=estudiantes_ids,
                    estado='Activo'
                ).values('idEstudiante').distinct().count(),
                'bajo_rendimiento': HistorialAcademico.objects.filter(
                    idEstudiante__in=estudiantes_ids,
                    nota_final__lt=10
                ).values('idEstudiante').distinct().count(),
            }
            
            # Cachear
            cache.set(cache_key, stats, cls.CACHE_TIMEOUT['global'])
            logger.info(f"Estadísticas cacheadas para universidad: {universidad_id}")
        
        return stats
    
    @classmethod
    def get_estadisticas_carreras(cls, universidad_id=None, limit=5):
        """
        Obtiene estadísticas por carrera con caché
        """
        cache_key = f'estadisticas_carreras_{universidad_id}_{limit}'
        carreras = cache.get(cache_key)
        
        if not carreras:
            logger.info(f"Calculando estadísticas por carrera para universidad: {universidad_id}")
            
            estudiantes_qs = cls._get_estudiantes_queryset(universidad_id)
            
            carreras = estudiantes_qs.values(
                'idCarrera__nombre'
            ).annotate(
                cantidad=Count('idEstudiante')
            ).order_by('-cantidad')[:limit]
            
            # Convertir a lista para que sea serializable
            carreras = list(carreras)
            cache.set(cache_key, carreras, cls.CACHE_TIMEOUT['carreras'])
            logger.info(f"Estadísticas por carrera cacheadas")
        
        return carreras
    
    @classmethod
    def get_estadisticas_estados(cls, universidad_id=None):
        """
        Obtiene estadísticas por estado con caché
        """
        cache_key = f'estadisticas_estados_{universidad_id}'
        estados = cache.get(cache_key)
        
        if not estados:
            logger.info(f"Calculando estadísticas por estado para universidad: {universidad_id}")
            
            estudiantes_qs = cls._get_estudiantes_queryset(universidad_id)
            
            estados = estudiantes_qs.values('estado').annotate(
                cantidad=Count('idEstudiante')
            )
            
            # Convertir a lista para que sea serializable
            estados = list(estados)
            cache.set(cache_key, estados, cls.CACHE_TIMEOUT['estados'])
            logger.info(f"Estadísticas por estado cacheadas")
        
        return estados
    
    @classmethod
    def get_estadisticas_riesgo(cls, universidad_id=None, limit=5):
        """Obtiene estadísticas de factores de riesgo con caché"""
        cache_key = f'estadisticas_riesgo_{universidad_id}_{limit}'
        factores = cache.get(cache_key)
        
        if not factores:
            logger.info(f"Calculando estadísticas de riesgo para universidad: {universidad_id}")
            
            from core.models import RiesgoEstudiante  # Import absoluto
            
            estudiantes_qs = cls._get_estudiantes_queryset(universidad_id)
            
            factores = RiesgoEstudiante.objects.filter(
                idEstudiante__in=estudiantes_qs.values_list('idEstudiante', flat=True),
                estado='Activo'
            ).values('idFactor__nombre').annotate(
                cantidad=Count('idFactor')
            ).order_by('-cantidad')[:limit]
            
            # Convertir a lista para que sea serializable
            factores = list(factores)
            cache.set(cache_key, factores, cls.CACHE_TIMEOUT['riesgo'])
            logger.info(f"Estadísticas de riesgo cacheadas")
        
        return factores
    
    @classmethod
    def invalidate_estadisticas(cls, universidad_id=None):
        """
        Invalida toda la caché de estadísticas
        """
        patterns = [
            f'estadisticas_globales_{universidad_id}',
            f'estadisticas_carreras_{universidad_id}_*',
            f'estadisticas_estados_{universidad_id}',
            f'estadisticas_riesgo_{universidad_id}_*',
        ]
        
        for pattern in patterns:
            try:
                # Intentar usar delete_pattern
                if hasattr(cache, 'delete_pattern'):
                    cache.delete_pattern(pattern)
                else:
                    # Si no tiene delete_pattern, intentar con patrones específicos
                    cache.delete(pattern.replace('*', ''))
                logger.info(f"Caché invalidado: {pattern}")
            except Exception as e:
                logger.warning(f"Error invalidando caché {pattern}: {str(e)}")
        
        # También invalidar caché de dashboard
        try:
            if universidad_id:
                if hasattr(cache, 'delete_pattern'):
                    cache.delete_pattern(f'dashboard_admin_{universidad_id}_*')
            else:
                if hasattr(cache, 'delete_pattern'):
                    cache.delete_pattern('dashboard_admin_*')
        except Exception as e:
            logger.warning(f"Error invalidando caché de dashboard: {str(e)}")
        
        logger.info("Todas las estadísticas cacheadas han sido invalidadas")


def invalidar_cache_estadisticas(universidad_id=None):
    """
    Función auxiliar para invalidar la caché de estadísticas
    """
    EstadisticasService.invalidate_estadisticas(universidad_id)