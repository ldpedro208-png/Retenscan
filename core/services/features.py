# core/ml/features.py
import pandas as pd
import numpy as np
from django.db.models import Avg, Count, Q
from django.utils import timezone
from datetime import timedelta
import logging

from core.models import (
    Estudiante, HistorialAcademico, Asistencia, 
    RiesgoEstudiante, TareaAsignacion, EncuestaRespuesta,
    CatalogoFactorRiesgo, EncuestaAsignacion, UsuarioEstudiantes
)

logger = logging.getLogger(__name__)


class FeatureEngineer:
    """
    Clase para crear características (features) a partir de los datos
    """
    
    def __init__(self):
        self.feature_names = []
    
    def crear_dataset_entrenamiento(self, universidad_id=None):
        """
        Crea un dataset con todas las características para entrenamiento
        """
        try:
            # Obtener estudiantes
            estudiantes_qs = Estudiante.objects.all()
            if universidad_id:
                estudiantes_qs = estudiantes_qs.filter(
                    idCarrera__idUniversidad_id=universidad_id
                )
            
            estudiantes = estudiantes_qs.select_related('idCarrera')
            
            datos = []
            errores = 0
            exitos = 0
            
            for estudiante in estudiantes:
                try:
                    fila = self._calcular_features(estudiante)
                    # ✅ AGREGAR LA ETIQUETA (ABANDONO)
                    fila['abandono'] = 1 if estudiante.estado == 'Abandonado' else 0
                    datos.append(fila)
                    exitos += 1
                except Exception as e:
                    errores += 1
                    if errores <= 5:
                        logger.warning(f"Error procesando estudiante {estudiante.idEstudiante}: {str(e)}")
            
            logger.info(f"Estudiantes procesados: {exitos} exitosos, {errores} errores")
            
            if not datos:
                logger.warning("No se pudieron generar datos para ningún estudiante")
                return pd.DataFrame()
            
            df = pd.DataFrame(datos)
            
            # Guardar nombres de características
            self.feature_names = [col for col in df.columns if col != 'abandono']
            
            logger.info(f"Dataset creado con {len(df)} estudiantes y {len(self.feature_names)} características")
            logger.info(f"  - Estudiantes activos: {len(df[df['abandono'] == 0])}")
            logger.info(f"  - Estudiantes abandonados: {len(df[df['abandono'] == 1])}")
            
            return df
            
        except Exception as e:
            logger.error(f"Error creando dataset: {str(e)}")
            return pd.DataFrame()
    
    def _calcular_features(self, estudiante):
        """
        Calcula todas las características para un estudiante
        """
        features = {}
        
        # ============================================
        # 1. DATOS DEMOGRÁFICOS Y ACADÉMICOS
        # ============================================
        features['edad'] = self._calcular_edad(estudiante)
        features['semestre_actual'] = estudiante.semestre_actual
        features['ano_ingreso'] = estudiante.ano_ingreso
        
        # ============================================
        # 2. RENDIMIENTO ACADÉMICO
        # ============================================
        historial = HistorialAcademico.objects.filter(idEstudiante=estudiante)
        
        if historial.exists():
            notas = historial.filter(nota_final__isnull=False)
            
            if notas.exists():
                features['promedio_general'] = notas.aggregate(Avg('nota_final'))['nota_final__avg'] or 0
            else:
                features['promedio_general'] = 0
            
            features['materias_aprobadas'] = historial.filter(estado_materia='Aprobada').count()
            features['materias_reprobadas'] = historial.filter(estado_materia='Reprobada').count()
            features['materias_cursando'] = historial.filter(estado_materia='Cursando').count()
            features['total_materias'] = historial.count()
            
            # Tendencia de notas (últimas 3)
            ultimas_notas = list(notas.order_by('-idHistorial')[:3].values_list('nota_final', flat=True))
            
            if ultimas_notas:
                features['tendencia_notas'] = sum(ultimas_notas) / len(ultimas_notas)
                # Detectar tendencia descendente
                if len(ultimas_notas) >= 3:
                    features['tendencia_descendente'] = 1 if ultimas_notas[0] < ultimas_notas[-1] else 0
                else:
                    features['tendencia_descendente'] = 0
            else:
                features['tendencia_notas'] = features.get('promedio_general', 0)
                features['tendencia_descendente'] = 0
                
        else:
            features['promedio_general'] = 0
            features['materias_aprobadas'] = 0
            features['materias_reprobadas'] = 0
            features['materias_cursando'] = 0
            features['total_materias'] = 0
            features['tendencia_notas'] = 0
            features['tendencia_descendente'] = 0
        
        # ============================================
        # 3. ASISTENCIAS
        # ============================================
        asistencias = Asistencia.objects.filter(idEstudiante=estudiante)
        total_asistencias = asistencias.count()
        
        if total_asistencias > 0:
            presentes = asistencias.filter(presente=True).count()
            features['porcentaje_asistencia'] = (presentes / total_asistencias) * 100
            features['faltas'] = asistencias.filter(presente=False).count()
            features['porcentaje_faltas'] = 100 - features['porcentaje_asistencia']
        else:
            features['porcentaje_asistencia'] = 0
            features['faltas'] = 0
            features['porcentaje_faltas'] = 100
        
        # ============================================
        # 4. TAREAS
        # ============================================
        entregas = TareaAsignacion.objects.filter(estudiante=estudiante)
        total_entregas = entregas.count()
        
        if total_entregas > 0:
            entregas_realizadas = entregas.filter(entregada=True).count()
            features['porcentaje_entregas'] = (entregas_realizadas / total_entregas) * 100
            
            calificadas = entregas.filter(calificada=True)
            if calificadas.exists():
                features['promedio_calificaciones'] = calificadas.aggregate(
                    Avg('puntaje_obtenido')
                )['puntaje_obtenido__avg'] or 0
            else:
                features['promedio_calificaciones'] = 0
        else:
            features['porcentaje_entregas'] = 0
            features['promedio_calificaciones'] = 0
        
        # ============================================
        # 5. RIESGOS DETECTADOS
        # ============================================
        riesgos = RiesgoEstudiante.objects.filter(idEstudiante=estudiante)
        features['riesgos_activos'] = riesgos.filter(estado='Activo').count()
        features['riesgos_totales'] = riesgos.count()
        
        # ============================================
        # 6. ENCUESTAS (sentimiento)
        # ============================================
        asignaciones = EncuestaAsignacion.objects.filter(estudiante=estudiante)
        
        if asignaciones.exists():
            respuestas = EncuestaRespuesta.objects.filter(
                asignacion__in=asignaciones
            ).order_by('-fecha_respuesta')[:10]
            
            if respuestas.exists():
                respuestas_escala = respuestas.filter(respuesta_escala__isnull=False)
                if respuestas_escala.exists():
                    features['sentimiento_promedio'] = respuestas_escala.aggregate(
                        Avg('respuesta_escala')
                    )['respuesta_escala__avg'] or 3
                else:
                    features['sentimiento_promedio'] = 3
            else:
                features['sentimiento_promedio'] = 3
        else:
            features['sentimiento_promedio'] = 3
        
        # ============================================
        # 7. FACTORES DE RIESGO (one-hot encoding)
        # ============================================
        factores = CatalogoFactorRiesgo.objects.filter(activo=True)
        for factor in factores:
            key = f'factor_{factor.idFactor}'
            features[key] = 1 if riesgos.filter(idFactor=factor, estado='Activo').exists() else 0
        
        # ============================================
        # 8. ÍNDICES AVANZADOS (para mejorar el modelo)
        # ============================================
        # Índice académico (0-1)
        if features.get('promedio_general', 0) > 0:
            features['indice_academico'] = min(features['promedio_general'] / 20, 1.0)
        else:
            features['indice_academico'] = 0
        
        # Índice de compromiso (0-1)
        comp_asistencia = features.get('porcentaje_asistencia', 0) / 100
        comp_entregas = features.get('porcentaje_entregas', 0) / 100
        # Porcentaje de materias aprobadas
        total_materias = features.get('total_materias', 1)
        comp_materias = features.get('materias_aprobadas', 0) / max(total_materias, 1)
        
        features['indice_compromiso'] = min(
            (comp_asistencia * 0.4) + (comp_entregas * 0.3) + (comp_materias * 0.3),
            1.0
        )
        
        # Índice de bienestar (0-1)
        sentimiento = features.get('sentimiento_promedio', 3) / 5
        penalizacion_riesgos = min(features.get('riesgos_activos', 0) * 0.1, 0.5)
        features['indice_bienestar'] = max(min(sentimiento - penalizacion_riesgos, 1.0), 0)
        
        # Horas de estudio estimadas (basado en rendimiento)
        promedio = features.get('promedio_general', 0)
        if promedio >= 18:
            features['horas_estudio'] = 8 + (promedio - 18) * 2
        elif promedio >= 14:
            features['horas_estudio'] = 6 + (promedio - 14) * 0.5
        elif promedio >= 10:
            features['horas_estudio'] = 4 + (promedio - 10) * 0.3
        else:
            features['horas_estudio'] = max(2, promedio * 0.3)
        
        # ============================================
        # 9. RIESGO COMBINADO (feature compuesta)
        # ============================================
        features['riesgo_combinado'] = min(
            (1 - features.get('indice_academico', 0)) * 0.4 +
            (1 - features.get('porcentaje_asistencia', 0) / 100) * 0.3 +
            (features.get('riesgos_activos', 0) / 5) * 0.3,
            1.0
        )
        
        return features
    
    def _calcular_edad(self, estudiante):
        """Calcula la edad del estudiante"""
        if estudiante.fecha_nacimiento:
            hoy = timezone.now().date()
            return hoy.year - estudiante.fecha_nacimiento.year
        return 18