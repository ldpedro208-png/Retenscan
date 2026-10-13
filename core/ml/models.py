# core/ml/models.py
import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split, cross_val_score
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import classification_report, confusion_matrix, roc_auc_score, accuracy_score, precision_score, recall_score, f1_score
import joblib
from django.db.models import Avg, Count, Q
from django.utils import timezone
from datetime import timedelta
import logging
import os
from django.conf import settings
from ..services.features import FeatureEngineer

logger = logging.getLogger(__name__)

from core.models import (
    Estudiante, HistorialAcademico, Asistencia, 
    EncuestaRespuesta, RiesgoEstudiante, CatalogoFactorRiesgo,
    Usuario, TareaAsignacion, UsuarioEstudiantes, EncuestaAsignacion
)


class ModeloPredictivoDesercion:
    """
    Modelo predictivo de deserción estudiantil
    """
    
    def __init__(self, auto_cargar=True):
        self.modelo = None
        self.scaler = None
        self.feature_names = []
        self.shap_explainer = None
        self.umbral_riesgo = 0.5
        self.modelo_path = os.path.join(settings.BASE_DIR, 'core', 'ml', 'models')
        
        # Variables para almacenar métricas
        self.metricas = {}
        self.X_test = None
        self.y_test = None
        self.X_train = None
        self.y_train = None
        self.accuracy = 0.0
        self.fecha_entrenamiento = None
        self.model_type = 'random_forest'
        
        # Intentar cargar modelo existente SOLO si se solicita
        if auto_cargar:
            self.cargar_modelo()
        else:
            logger.info("Modelo inicializado sin carga automática")
    
    def _crear_directorio_modelo(self):
        """Crea el directorio para guardar el modelo"""
        if not os.path.exists(self.modelo_path):
            os.makedirs(self.modelo_path)

    def preparar_datos(self, universidad_id=None):
        """
        Prepara los datos de entrenamiento
        """
        # 1. Obtener estudiantes
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
                
                # Etiqueta: ¿Abandonó?
                fila['abandono'] = 1 if estudiante.estado == 'Abandonado' else 0
                
                datos.append(fila)
                exitos += 1
            except Exception as e:
                errores += 1
                if errores <= 5:
                    logger.error(f"Error procesando estudiante {estudiante.idEstudiante}: {str(e)}")
        
        logger.info(f"Estudiantes procesados: {exitos} exitosos, {errores} errores")
        
        if not datos:
            logger.warning("No hay datos disponibles para entrenar")
            return pd.DataFrame()
        
        df = pd.DataFrame(datos)
        
        # Guardar nombres de features
        self.feature_names = [col for col in df.columns if col != 'abandono']
        
        logger.info(f"Features generadas: {len(self.feature_names)}")
        
        return df
    
    def _calcular_features(self, estudiante):
        """Calcula todas las features para un estudiante"""
        features = {}
        
        # 1. Datos demográficos y académicos
        features['edad'] = self._calcular_edad(estudiante)
        features['semestre_actual'] = estudiante.semestre_actual
        features['ano_ingreso'] = estudiante.ano_ingreso
        
        # 2. Rendimiento académico
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
            
            # Tendencia de notas (últimas 3 materias)
            ultimas_notas = historial.filter(nota_final__isnull=False).order_by('-idHistorial')[:3].values_list('nota_final', flat=True)
            if len(ultimas_notas) > 0:
                features['tendencia_notas'] = sum(ultimas_notas) / len(ultimas_notas)
            else:
                features['tendencia_notas'] = features.get('promedio_general', 0)
        else:
            features['promedio_general'] = 0
            features['materias_aprobadas'] = 0
            features['materias_reprobadas'] = 0
            features['materias_cursando'] = 0
            features['total_materias'] = 0
            features['tendencia_notas'] = 0
        
        # 3. Asistencias
        asistencias = Asistencia.objects.filter(idEstudiante=estudiante)
        total_asistencias = asistencias.count()
        
        if total_asistencias > 0:
            features['porcentaje_asistencia'] = (asistencias.filter(presente=True).count() / total_asistencias) * 100
            features['faltas'] = asistencias.filter(presente=False).count()
        else:
            features['porcentaje_asistencia'] = 0
            features['faltas'] = 0
        
        # 4. Entregas de tareas
        entregas = TareaAsignacion.objects.filter(estudiante=estudiante)
        total_entregas = entregas.count()
        
        if total_entregas > 0:
            features['entregas_realizadas'] = entregas.filter(entregada=True).count()
            features['porcentaje_entregas'] = (features['entregas_realizadas'] / total_entregas) * 100
            
            calificadas = entregas.filter(calificada=True)
            if calificadas.exists():
                features['promedio_calificaciones'] = calificadas.aggregate(
                    Avg('puntaje_obtenido')
                )['puntaje_obtenido__avg'] or 0
            else:
                features['promedio_calificaciones'] = 0
        else:
            features['entregas_realizadas'] = 0
            features['porcentaje_entregas'] = 0
            features['promedio_calificaciones'] = 0
        
        # 5. Riesgos detectados
        riesgos = RiesgoEstudiante.objects.filter(idEstudiante=estudiante)
        features['riesgos_activos'] = riesgos.filter(estado='Activo').count()
        features['riesgos_totales'] = riesgos.count()
        
        # 6. Encuestas (corregido)
        asignaciones = EncuestaAsignacion.objects.filter(estudiante=estudiante)
        
        if asignaciones.exists():
            # Obtener respuestas de las asignaciones
            respuestas = EncuestaRespuesta.objects.filter(
                asignacion__in=asignaciones
            ).order_by('-fecha_respuesta')[:10]
            
            if respuestas.exists():
                # Sentimiento promedio (escala 1-5)
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
        
        # 7. Factores de riesgo específicos
        factores_riesgo = CatalogoFactorRiesgo.objects.all()
        for factor in factores_riesgo:
            key = f'factor_{factor.idFactor}'
            features[key] = 1 if riesgos.filter(idFactor=factor, estado='Activo').exists() else 0
        
        return features
    
    def _calcular_edad(self, estudiante):
        """Calcula la edad del estudiante"""
        if estudiante.fecha_nacimiento:
            hoy = timezone.now().date()
            return hoy.year - estudiante.fecha_nacimiento.year
        return 18

    # ============================================
    # ENTRENAMIENTO DEL MODELO
    # ============================================
    
    def entrenar(self, universidad_id=None, test_size=0.2, random_state=42, model_type='random_forest'):
        """
        Entrena el modelo y guarda las métricas
        """
        self._crear_directorio_modelo()
        self.fecha_entrenamiento = timezone.now()
        self.model_type = model_type
        
        # ============================================
        # 1. PREPARAR DATOS USANDO FEATUREENGINEER
        # ============================================
        feature_engineer = FeatureEngineer()
        df = feature_engineer.crear_dataset_entrenamiento(universidad_id)
        
        if df.empty:
            logger.error("No hay datos suficientes para entrenar")
            return False
        
        # GUARDAR FEATURE NAMES (ANTES DE MODIFICAR EL DATAFRAME)
        self.feature_names = [col for col in df.columns if col != 'abandono']
        
        # Verificar cuántos abandonos hay
        abandonos_count = df['abandono'].sum()
        total_count = len(df)
        
        logger.info(f"Total estudiantes: {total_count}")
        logger.info(f"Abandonos: {abandonos_count}")
        logger.info(f"Features generadas: {len(self.feature_names)}")
        
        # ============================================
        # 2. CREAR DATOS SINTÉTICOS SI ES NECESARIO
        # ============================================
        if abandonos_count < 3:
            logger.warning(f"Solo hay {abandonos_count} abandonos. Creando datos sintéticos...")
            
            df_sintetico = df.copy()
            
            # Seleccionar estudiantes aleatorios para marcar como abandonos
            n_abandono = max(int(total_count * 0.15), 5)
            indices_abandono = np.random.choice(total_count, n_abandono, replace=False)
            df_sintetico.loc[indices_abandono, 'abandono'] = 1
            
            # MODIFICAR CARACTERÍSTICAS PARA HACERLOS MÁS REALISTAS
            for idx in indices_abandono:
                # Reducir asistencia
                if 'porcentaje_asistencia' in df_sintetico.columns:
                    df_sintetico.loc[idx, 'porcentaje_asistencia'] = max(0, 
                        df_sintetico.loc[idx, 'porcentaje_asistencia'] - np.random.randint(20, 50))
                # Reducir promedio
                if 'promedio_general' in df_sintetico.columns:
                    df_sintetico.loc[idx, 'promedio_general'] = max(0, 
                        df_sintetico.loc[idx, 'promedio_general'] - np.random.randint(5, 15))
                # Reducir compromiso
                if 'indice_compromiso' in df_sintetico.columns:
                    df_sintetico.loc[idx, 'indice_compromiso'] = max(0, 
                        df_sintetico.loc[idx, 'indice_compromiso'] - np.random.randint(20, 50) / 100)
                # Aumentar faltas
                if 'faltas' in df_sintetico.columns:
                    df_sintetico.loc[idx, 'faltas'] = df_sintetico.loc[idx, 'faltas'] + np.random.randint(5, 15)
                # Reducir entregas
                if 'porcentaje_entregas' in df_sintetico.columns:
                    df_sintetico.loc[idx, 'porcentaje_entregas'] = max(0, 
                        df_sintetico.loc[idx, 'porcentaje_entregas'] - np.random.randint(20, 50))
            
            df = df_sintetico
            abandonos_count = df['abandono'].sum()
            logger.info(f"Datos sintéticos creados: {abandonos_count} abandonos de {total_count}")
        
        # ============================================
        # 3. SEPARAR FEATURES Y TARGET
        # ============================================
        X = df[self.feature_names]
        y = df['abandono']
        
        # ============================================
        # 4. BALANCEAR CON SMOTE
        # ============================================
        try:
            from imblearn.over_sampling import SMOTE
            smote = SMOTE(random_state=random_state)
            X, y = smote.fit_resample(X, y)
            logger.info(f"Balanceo con SMOTE: {len(X)} muestras")
        except ImportError:
            logger.warning("imbalanced-learn no instalado. Usando datos sin balancear.")
        
        # ============================================
        # 5. DIVIDIR DATOS
        # ============================================
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=test_size, random_state=random_state, stratify=y
        )
        
        # GUARDAR DATOS PARA MÉTRICAS Y PREDICCIONES
        self.X_train = X_train
        self.y_train = y_train
        self.X_test = X_test
        self.y_test = y_test
        
        # ============================================
        # 6. NORMALIZAR
        # ============================================
        self.scaler = StandardScaler()
        X_train_scaled = self.scaler.fit_transform(X_train)
        X_test_scaled = self.scaler.transform(X_test)
        
        # GUARDAR PARA PREDICCIONES
        self.X_test_scaled = X_test_scaled
        
        # ============================================
        # 7. ENTRENAR MODELO
        # ============================================
        self.modelo = RandomForestClassifier(
            n_estimators=100,
            max_depth=10,
            min_samples_split=5,
            min_samples_leaf=2,
            random_state=random_state,
            class_weight='balanced'
        )
        self.modelo.fit(X_train_scaled, y_train)
        
        # ============================================
        # 8. EVALUAR Y CALCULAR MÉTRICAS
        # ============================================
        y_pred = self.modelo.predict(X_test_scaled)
        
        self.accuracy = accuracy_score(y_test, y_pred)
        self.precision = precision_score(y_test, y_pred, average='weighted', zero_division=0)
        self.recall = recall_score(y_test, y_pred, average='weighted', zero_division=0)
        self.f1 = f1_score(y_test, y_pred, average='weighted', zero_division=0)
        
        self.metricas = {
            'accuracy': self.accuracy,
            'precision': self.precision,
            'recall': self.recall,
            'f1_score': self.f1,
            'confusion_matrix': confusion_matrix(y_test, y_pred).tolist(),
            'n_features': len(self.feature_names),
            'n_samples': len(X),
            'n_abandonos': int(abandonos_count),
            'total_estudiantes': total_count,
        }
        
        # AUC-ROC
        if len(np.unique(y_test)) > 1:
            try:
                y_prob = self.modelo.predict_proba(X_test_scaled)[:, 1]
                self.metricas['auc_roc'] = roc_auc_score(y_test, y_prob)
            except Exception as e:
                logger.warning(f"No se pudo calcular AUC-ROC: {str(e)}")
        
        # Importancia de características
        if hasattr(self.modelo, 'feature_importances_'):
            importancias = self.modelo.feature_importances_
            self.metricas['feature_importance'] = dict(zip(self.feature_names, importancias))
        
        # ============================================
        # 9. LOGGING
        # ============================================
        logger.info("="*50)
        logger.info("EVALUACIÓN DEL MODELO")
        logger.info("="*50)
        logger.info(f"Precisión (Accuracy): {self.accuracy:.4f}")
        logger.info(f"Precisión (Precision): {self.precision:.4f}")
        logger.info(f"Recuperación (Recall): {self.recall:.4f}")
        logger.info(f"F1-Score: {self.f1:.4f}")
        if 'auc_roc' in self.metricas:
            logger.info(f"AUC-ROC: {self.metricas['auc_roc']:.4f}")
        
        # Mostrar top 10 características más importantes
        if 'feature_importance' in self.metricas:
            logger.info("Top 10 características más importantes:")
            sorted_features = sorted(
                self.metricas['feature_importance'].items(),
                key=lambda x: x[1],
                reverse=True
            )[:10]
            for feature, importance in sorted_features:
                logger.info(f"  - {feature}: {importance:.4f}")
        
        # ============================================
        # 10. GUARDAR MODELO
        # ============================================
        self._guardar_modelo()
        
        logger.info(f"Modelo guardado en: {self.modelo_path}")
        
        return True

    # ============================================
    # CARGA Y GUARDADO DEL MODELO
    # ============================================
    
    def cargar_modelo(self):
        """Carga un modelo guardado y sus métricas"""
        self._crear_directorio_modelo()
        
        modelo_file = os.path.join(self.modelo_path, 'modelo.pkl')
        scaler_file = os.path.join(self.modelo_path, 'scaler.pkl')
        features_file = os.path.join(self.modelo_path, 'features.txt')
        metrics_file = os.path.join(self.modelo_path, 'metrics.pkl')
        
        try:
            if os.path.exists(modelo_file) and os.path.exists(scaler_file):
                self.modelo = joblib.load(modelo_file)
                self.scaler = joblib.load(scaler_file)
                
                if os.path.exists(features_file):
                    with open(features_file, 'r') as f:
                        self.feature_names = f.read().split(',')
                
                # Cargar métricas si existen
                if os.path.exists(metrics_file):
                    self.metricas = joblib.load(metrics_file)
                    self.accuracy = self.metricas.get('accuracy', 0.0)
                
                logger.info("Modelo cargado exitosamente")
                return True
            else:
                logger.warning("No se encontró modelo guardado")
                return False
        except Exception as e:
            logger.error(f"Error cargando modelo: {str(e)}")
            return False
    
    def _guardar_modelo(self):
        """Guarda el modelo entrenado y sus métricas"""
        self._crear_directorio_modelo()
        
        try:
            # Guardar modelo
            joblib.dump(self.modelo, os.path.join(self.modelo_path, 'modelo.pkl'))
            joblib.dump(self.scaler, os.path.join(self.modelo_path, 'scaler.pkl'))
            
            # Guardar feature names
            with open(os.path.join(self.modelo_path, 'features.txt'), 'w') as f:
                f.write(','.join(self.feature_names))
            
            # Guardar métricas
            joblib.dump(self.metricas, os.path.join(self.modelo_path, 'metrics.pkl'))
            
            # Guardar metadatos en JSON
            metadata = {
                'fecha_entrenamiento': self.fecha_entrenamiento.isoformat() if self.fecha_entrenamiento else None,
                'model_type': self.model_type,
                'accuracy': self.accuracy,
                'precision': self.precision if hasattr(self, 'precision') else 0.0,
                'recall': self.recall if hasattr(self, 'recall') else 0.0,
                'f1_score': self.f1 if hasattr(self, 'f1') else 0.0,
                'n_features': len(self.feature_names),
            }
            
            import json
            with open(os.path.join(self.modelo_path, 'model_info.json'), 'w') as f:
                json.dump(metadata, f, indent=2)
            
            logger.info("Modelo guardado exitosamente")
            return True
        except Exception as e:
            logger.error(f"Error guardando modelo: {str(e)}")
            return False
    
    def get_metrics(self):
        """Retorna las métricas del modelo entrenado"""
        return self.metricas.copy() if self.metricas else {
            'accuracy': 0.0,
            'precision': 0.0,
            'recall': 0.0,
            'f1_score': 0.0,
        }
    
    def get_model_info(self):
        """Retorna información del modelo"""
        return {
            'fecha_entrenamiento': self.fecha_entrenamiento.isoformat() if self.fecha_entrenamiento else 'Desconocido',
            'model_type': self.model_type,
            'accuracy': self.accuracy,
            'n_features': len(self.feature_names),
            'features': self.feature_names[:10],
        }

    # ============================================
    # PREDICCIÓN
    # ============================================
    
    def predecir_estudiante(self, estudiante_id):
        """
        Predice el riesgo de deserción para un estudiante específico
        """
        if self.modelo is None:
            if not self.cargar_modelo():
                # Si no hay modelo, entrenar uno
                self.entrenar()
                if self.modelo is None:
                    raise ValueError("No se pudo cargar o entrenar el modelo")
        
        try:
            estudiante = Estudiante.objects.get(idEstudiante=estudiante_id)
        except Estudiante.DoesNotExist:
            raise ValueError(f"Estudiante con ID {estudiante_id} no encontrado")
        
        # USAR FEATUREENGINEER PARA CALCULAR FEATURES
        feature_engineer = FeatureEngineer()
        features_dict = feature_engineer._calcular_features(estudiante)
        
        # Crear DataFrame con las mismas columnas que el entrenamiento
        df = pd.DataFrame([features_dict])
        
        # Asegurar que todas las columnas estén presentes
        for feature in self.feature_names:
            if feature not in df.columns:
                df[feature] = 0
        
        # Seleccionar solo las features necesarias
        X = df[self.feature_names]
        
        # Normalizar
        X_scaled = self.scaler.transform(X)
        
        # Predecir
        probabilidad = self.modelo.predict_proba(X_scaled)[0, 1]
        prediccion = self.modelo.predict(X_scaled)[0]
        
        # Obtener factores de importancia
        factores_importantes = self._obtener_factores_importantes()
        
        return {
            'estudiante_id': estudiante_id,
            'estudiante_nombre': f"{estudiante.nombre} {estudiante.apellido_paterno}",
            'carnet': estudiante.carnet,
            'carrera': estudiante.idCarrera.nombre if estudiante.idCarrera else 'Sin carrera',
            'probabilidad': round(float(probabilidad) * 100, 1),
            'nivel_riesgo': self._nivel_riesgo(probabilidad),
            'prediccion': 'Riesgo' if prediccion == 1 else 'Sin riesgo',
            'factores_importantes': factores_importantes,
            'recomendaciones': self._generar_recomendaciones(factores_importantes)
        }
    
    def predecir_multiples(self, estudiante_ids):
        """
        Predice el riesgo para múltiples estudiantes
        """
        resultados = []
        for estudiante_id in estudiante_ids:
            try:
                resultado = self.predecir_estudiante(estudiante_id)
                resultados.append(resultado)
            except Exception as e:
                logger.error(f"Error prediciendo estudiante {estudiante_id}: {str(e)}")
        
        return sorted(resultados, key=lambda x: x['probabilidad'], reverse=True)
    
    def _nivel_riesgo(self, probabilidad):
        """Determina el nivel de riesgo basado en la probabilidad"""
        if probabilidad >= 0.8:
            return 'Crítico'
        elif probabilidad >= 0.6:
            return 'Alto'
        elif probabilidad >= 0.4:
            return 'Medio'
        else:
            return 'Bajo'
    
    def _obtener_factores_importantes(self):
        """
        Obtiene los factores más importantes para la predicción
        """
        if self.modelo is None or not self.feature_names:
            return []
        
        # Obtener importancia de características
        importancia = self.modelo.feature_importances_
        
        # Crear lista de (feature, importancia)
        factores = list(zip(self.feature_names, importancia))
        
        # Ordenar por importancia (mayor a menor)
        factores.sort(key=lambda x: x[1], reverse=True)
        
        # Retornar top 5 factores
        return factores[:5]
    
    def _generar_recomendaciones(self, factores_importantes):
        """
        Genera recomendaciones basadas en los factores importantes
        """
        recomendaciones = []
        
        for factor, importancia in factores_importantes:
            if 'promedio' in factor.lower() and importancia > 0.1:
                recomendaciones.append({
                    'factor': factor,
                    'recomendacion': 'Programar tutorías académicas para mejorar el rendimiento',
                    'prioridad': 'Alta'
                })
            elif 'asistencia' in factor.lower() and importancia > 0.1:
                recomendaciones.append({
                    'factor': factor,
                    'recomendacion': 'Investigar causas de inasistencia y ofrecer apoyo',
                    'prioridad': 'Alta'
                })
            elif 'riesgo' in factor.lower() and importancia > 0.1:
                recomendaciones.append({
                    'factor': factor,
                    'recomendacion': 'Realizar intervención temprana con el tutor asignado',
                    'prioridad': 'Alta'
                })
            elif 'sentimiento' in factor.lower() and importancia > 0.05:
                recomendaciones.append({
                    'factor': factor,
                    'recomendacion': 'Programar reunión de seguimiento emocional',
                    'prioridad': 'Media'
                })
            elif 'entregas' in factor.lower() and importancia > 0.05:
                recomendaciones.append({
                    'factor': factor,
                    'recomendacion': 'Revisar carga académica y ofrecer apoyo en organización',
                    'prioridad': 'Media'
                })
            elif 'edad' in factor.lower() and importancia > 0.05:
                recomendaciones.append({
                    'factor': factor,
                    'recomendacion': 'Evaluar necesidades específicas según edad',
                    'prioridad': 'Baja'
                })
        
        return recomendaciones[:5]


class ServicioPrediccion:
    """
    Servicio para integrar la predicción con el resto del sistema
    """
    
    def __init__(self, auto_entrenar=False):
        self.modelo = ModeloPredictivoDesercion(auto_cargar=True)
        if not self.modelo.cargar_modelo():
            logger.info("No hay modelo guardado. Se entrenará automáticamente cuando sea necesario.")
            if auto_entrenar:
                logger.info("Entrenando modelo automáticamente...")
                try:
                    self.modelo.entrenar()
                except Exception as e:
                    logger.error(f"Error entrenando modelo automáticamente: {str(e)}")
    
    def obtener_estudiantes_riesgo(self, usuario, limit=50):
        """
        Obtiene estudiantes en riesgo para un usuario específico
        """
        if usuario is None:
            estudiantes_ids = Estudiante.objects.values_list('idEstudiante', flat=True)
        else:
            user_rol = getattr(usuario, 'rol', 'estudiante')
            universidad_id = getattr(usuario, 'idUniversidad_id', None)
            
            if user_rol == 'admin':
                if usuario.is_superuser:
                    estudiantes_ids = Estudiante.objects.values_list('idEstudiante', flat=True)
                else:
                    estudiantes_ids = Estudiante.objects.filter(
                        idCarrera__idUniversidad_id=universidad_id
                    ).values_list('idEstudiante', flat=True)
                
            elif user_rol == 'tutor':
                estudiantes_ids = UsuarioEstudiantes.objects.filter(
                    usuario=usuario
                ).values_list('estudiante_id', flat=True)
                
            elif user_rol == 'profesor':
                estudiantes_ids = Estudiante.objects.filter(
                    idCarrera__idUniversidad_id=universidad_id
                ).values_list('idEstudiante', flat=True)
                
            else:
                try:
                    estudiante = Estudiante.objects.get(idUsuario=usuario)
                    return [self.modelo.predecir_estudiante(estudiante.idEstudiante)]
                except Estudiante.DoesNotExist:
                    return []
        
        if not estudiantes_ids:
            return []
        
        estudiantes_list = list(estudiantes_ids)[:100]
        resultados = self.modelo.predecir_multiples(estudiantes_list)
        en_riesgo = [r for r in resultados if r['probabilidad'] > 30]
        
        return en_riesgo[:limit]
    
    def actualizar_riesgos_db(self):
        """
        Actualiza la base de datos con los riesgos calculados
        """
        estudiantes = Estudiante.objects.filter(estado='Activo')
        actualizados = 0
        errores = 0
        
        for estudiante in estudiantes:
            try:
                resultado = self.modelo.predecir_estudiante(estudiante.idEstudiante)
                
                factor, created = CatalogoFactorRiesgo.objects.get_or_create(
                    nombre='Riesgo predictivo IA',
                    defaults={
                        'peso': 1.0, 
                        'descripcion': 'Riesgo calculado por modelo de inteligencia artificial',
                        'activo': True
                    }
                )
                
                riesgo, created = RiesgoEstudiante.objects.get_or_create(
                    idEstudiante=estudiante,
                    idFactor=factor,
                    defaults={
                        'nivel': resultado['nivel_riesgo'],
                        'estado': 'Activo' if resultado['probabilidad'] > 30 else 'Resuelto',
                        'fecha_deteccion': timezone.now().date(),
                        'observaciones': f"Factores importantes: {resultado['factores_importantes'][:3]}",
                        'puntaje': resultado['probabilidad']
                    }
                )
                
                if not created:
                    riesgo.nivel = resultado['nivel_riesgo']
                    riesgo.puntaje = resultado['probabilidad']
                    riesgo.estado = 'Activo' if resultado['probabilidad'] > 30 else 'Resuelto'
                    riesgo.observaciones = f"Factores importantes: {resultado['factores_importantes'][:3]}"
                    riesgo.save()
                
                actualizados += 1
                    
            except Exception as e:
                errores += 1
                logger.error(f"Error actualizando riesgo para {estudiante.idEstudiante}: {str(e)}")
        
        logger.info(f"Riesgos actualizados: {actualizados} exitosos, {errores} errores")
        return actualizados, errores