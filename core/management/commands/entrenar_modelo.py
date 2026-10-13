# core/management/commands/entrenar_modelo.py
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from django.db import connection
from core.ml.models import ModeloPredictivoDesercion
from core.ml.features import FeatureEngineer
import logging
import time
import json
from datetime import datetime
import os

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Entrena el modelo predictivo de deserción con opciones avanzadas'

    def add_arguments(self, parser):
        """Define los argumentos de línea de comandos"""
        parser.add_argument(
            '--force',
            action='store_true',
            help='Forzar reentrenamiento incluso si el modelo ya existe',
        )
        parser.add_argument(
            '--min-samples',
            type=int,
            default=10,
            help='Número mínimo de muestras requeridas para entrenar (default: 10)',
        )
        parser.add_argument(
            '--test-size',
            type=float,
            default=0.2,
            help='Proporción de datos para prueba (default: 0.2)',
        )
        parser.add_argument(
            '--random-state',
            type=int,
            default=42,
            help='Semilla aleatoria para reproducibilidad (default: 42)',
        )
        parser.add_argument(
            '--verbose',
            action='store_true',
            help='Mostrar información detallada del entrenamiento',
        )
        parser.add_argument(
            '--save-metrics',
            action='store_true',
            help='Guardar métricas de rendimiento en archivo JSON',
        )
        parser.add_argument(
            '--no-cache',
            action='store_true',
            help='No usar datos en caché para el entrenamiento',
        )
        parser.add_argument(
            '--model-type',
            choices=['random_forest', 'xgboost', 'lightgbm', 'all'],
            default='all',
            help='Tipo de modelo a entrenar (default: all)',
        )
    def handle(self, *args, **options):
        """Maneja la ejecución del comando"""
        start_time = time.time()
        
        self.stdout.write('=' * 60)
        self.stdout.write(self.style.SUCCESS('🚀 INICIANDO ENTRENAMIENTO DEL MODELO PREDICTIVO'))
        self.stdout.write('=' * 60)
        self.stdout.write(f'📅 Fecha y hora: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}')
        
        # Verificar dependencias
        if not self._check_dependencies():
            raise CommandError('Dependencias faltantes. Instala: scikit-learn, pandas, numpy')
        
        # Verificar si el modelo ya existe
        modelo = ModeloPredictivoDesercion(auto_cargar=False)
        modelo_existente = modelo.cargar_modelo()
        
        if modelo_existente and not options['force']:
            self.stdout.write(self.style.WARNING('⚠️  El modelo ya existe. Usa --force para reentrenar.'))
            self._show_model_info(modelo)
            return
        
        try:
            self.stdout.write('\n🔄 Entrenando modelo...')
            
            training_metrics = {}
            best_model = None
            best_score = 0
            models_trained = []
            
            model_types = self._get_model_types(options['model_type'])
            
            for model_type in model_types:
                self.stdout.write(f'\n📊 Entrenando modelo: {model_type.upper()}')
                
                try:
                    result = modelo.entrenar(
                        test_size=options['test_size'],
                        random_state=options['random_state']
                    )
                    
                    if result and modelo.modelo is not None:
                        models_trained.append(model_type)
                        metrics = self._obtener_metricas_modelo(modelo)
                        training_metrics[model_type] = metrics
                        
                        if metrics.get('accuracy', 0) > best_score:
                            best_score = metrics['accuracy']
                            best_model = model_type
                            
                        self._print_model_metrics(model_type, metrics)
                    else:
                        self.stdout.write(self.style.WARNING(f'⚠️ No se pudo entrenar {model_type}'))
                        
                except Exception as e:
                    self.stdout.write(self.style.ERROR(f'❌ Error entrenando {model_type}: {str(e)}'))
                    logger.error(f"Error entrenando {model_type}: {str(e)}", exc_info=True)
            
            elapsed_time = time.time() - start_time
            
            self.stdout.write('\n' + '=' * 60)
            if best_model:
                self.stdout.write(self.style.SUCCESS('✅ ENTRENAMIENTO COMPLETADO'))
                self.stdout.write(f'⏱️  Tiempo total: {elapsed_time:.2f} segundos')
                self.stdout.write(f'🏆 Mejor modelo: {best_model.upper()}')
                self.stdout.write(f'📈 Precisión: {best_score:.2%}')
                self.stdout.write(f'📊 Modelos entrenados: {", ".join(models_trained)}')
                self.stdout.write('=' * 60)
                
                # Guardar el mejor modelo
                self._save_best_model(modelo, best_model, training_metrics, options)
                
                if options['save_metrics']:
                    self._save_metrics_to_file(training_metrics, best_model)
                
                # ✅ NUEVO: invalidar la caché del servicio para que
                # el siguiente request cargue el modelo recién entrenado
                try:
                    from core.services.ai_service import reset_all
                    reset_all()
                    self.stdout.write(self.style.SUCCESS('🔄 Caché de IA invalidada'))
                except Exception as e:
                    self.stdout.write(self.style.WARNING(f'⚠️ No se pudo invalidar caché: {e}'))
            else:
                self.stdout.write(self.style.WARNING('⚠️ No se pudo entrenar ningún modelo. Verifica los datos.'))
                
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'❌ Error: {str(e)}'))
            logger.error(f"Error en entrenamiento: {str(e)}", exc_info=True)
            raise CommandError(f'Error en entrenamiento: {str(e)}')
    def _obtener_metricas_modelo(self, modelo):
        """Obtiene métricas del modelo entrenado"""
        metrics = {
            'accuracy': 0.0,
            'precision': 0.0,
            'recall': 0.0,
            'f1_score': 0.0,
        }
        
        try:
            # Si el modelo tiene el atributo de métricas
            if hasattr(modelo, 'metricas'):
                return modelo.metricas
            
            # Si el modelo tiene el método get_metrics
            if hasattr(modelo, 'get_metrics'):
                return modelo.get_metrics()
            
            # Si el modelo de sklearn tiene el método score
            if modelo.modelo is not None and hasattr(modelo.modelo, 'score'):
                # Intentar calcular métricas con los datos de prueba
                if hasattr(modelo, 'X_test') and hasattr(modelo, 'y_test'):
                    from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score
                    
                    y_pred = modelo.modelo.predict(modelo.X_test)
                    metrics['accuracy'] = accuracy_score(modelo.y_test, y_pred)
                    metrics['precision'] = precision_score(modelo.y_test, y_pred, average='weighted', zero_division=0)
                    metrics['recall'] = recall_score(modelo.y_test, y_pred, average='weighted', zero_division=0)
                    metrics['f1_score'] = f1_score(modelo.y_test, y_pred, average='weighted', zero_division=0)
                    
        except Exception as e:
            logger.warning(f"Error obteniendo métricas: {str(e)}")
        
        return metrics

    def _count_available_samples(self):
        """Cuenta el número total de muestras disponibles para entrenamiento"""
        try:
            from core.models import Estudiante, HistorialAcademico, Asistencia
            from django.db.models import Q
            
            # Obtener IDs de estudiantes con historial
            estudiantes_con_historial = HistorialAcademico.objects.values_list('idEstudiante', flat=True).distinct()
            estudiantes_con_asistencias = Asistencia.objects.values_list('idEstudiante', flat=True).distinct()
            
            # Convertir a listas para poder usarlas en el filter
            ids_historial = list(estudiantes_con_historial)
            ids_asistencias = list(estudiantes_con_asistencias)
            
            # Filtrar estudiantes que tienen AMBAS cosas usando Q objects
            estudiantes_validos = Estudiante.objects.filter(
                Q(idEstudiante__in=ids_historial) & Q(idEstudiante__in=ids_asistencias)
            )
            
            total = estudiantes_validos.count()
            
            self.stdout.write(f'   - Estudiantes con historial: {len(ids_historial)}')
            self.stdout.write(f'   - Estudiantes con asistencias: {len(ids_asistencias)}')
            self.stdout.write(f'   - Estudiantes con ambos: {total}')
            
            return total
            
        except Exception as e:
            self.stdout.write(f'   ⚠️ Error contando muestras: {str(e)}')
            return 0

    def _check_dependencies(self):
        """Verifica que todas las dependencias necesarias estén instaladas"""
        try:
            import sklearn
            import pandas
            import numpy
            return True
        except ImportError as e:
            self.stdout.write(self.style.ERROR(f'❌ Dependencia faltante: {e}'))
            return False

    def _get_model_types(self, model_type_param):
        """Determina qué modelos entrenar basado en el parámetro"""
        if model_type_param == 'all':
            return ['random_forest', 'xgboost', 'lightgbm']
        return [model_type_param]

    def _print_model_metrics(self, model_type, metrics):
        """Imprime las métricas del modelo de forma formateada"""
        self.stdout.write(f'\n📊 Métricas del modelo {model_type.upper()}:')
        
        if isinstance(metrics, dict):
            accuracy = metrics.get('accuracy', 0)
            precision = metrics.get('precision', 0)
            recall = metrics.get('recall', 0)
            f1_score = metrics.get('f1_score', 0)
            
            self.stdout.write(f'  ✅ Precisión: {accuracy:.2%}')
            self.stdout.write(f'  ✅ Precisión (precision): {precision:.2%}')
            self.stdout.write(f'  ✅ Recuperación (recall): {recall:.2%}')
            self.stdout.write(f'  ✅ F1-Score: {f1_score:.2%}')
            
            if 'confusion_matrix' in metrics:
                cm = metrics['confusion_matrix']
                self.stdout.write(f'  📋 Matriz de confusión:')
                self.stdout.write(f'     Verdaderos Negativos: {cm[0][0]}')
                self.stdout.write(f'     Falsos Positivos: {cm[0][1]}')
                self.stdout.write(f'     Falsos Negativos: {cm[1][0]}')
                self.stdout.write(f'     Verdaderos Positivos: {cm[1][1]}')
            
            if 'feature_importance' in metrics:
                self.stdout.write('  📊 Características más importantes:')
                for feature, importance in list(metrics['feature_importance'].items())[:5]:
                    self.stdout.write(f'     - {feature}: {importance:.3f}')
        else:
            self.stdout.write(f'  ✅ Resultado: {metrics}')

    def _show_model_info(self, modelo):
        """Muestra información del modelo existente"""
        try:
            if hasattr(modelo, 'get_model_info'):
                info = modelo.get_model_info()
                self.stdout.write('\n📊 Información del modelo existente:')
                self.stdout.write(f'  📅 Entrenado: {info.get("fecha_entrenamiento", "Desconocido")}')
                self.stdout.write(f'  📈 Precisión: {info.get("accuracy", 0):.2%}')
                self.stdout.write(f'  📊 Tipo: {info.get("model_type", "Desconocido")}')
            else:
                self.stdout.write('ℹ️ El modelo existe pero no hay información detallada disponible.')
        except Exception as e:
            logger.warning(f"Error obteniendo información del modelo: {str(e)}")

    def _save_best_model(self, modelo, best_model, metrics, options):
        """Guarda el mejor modelo entrenado"""
        try:
            metadata = {
                'fecha_entrenamiento': timezone.now().isoformat(),
                'mejor_modelo': best_model,
                'metricas': metrics.get(best_model, {}),
                'test_size': options.get('test_size', 0.2),
                'random_state': options.get('random_state', 42),
                'model_type': options.get('model_type', 'all'),
            }
            
            model_dir = os.path.join(os.path.dirname(__file__), '..', '..', 'ml', 'models')
            os.makedirs(model_dir, exist_ok=True)
            
            metadata_path = os.path.join(model_dir, 'model_metadata.json')
            with open(metadata_path, 'w') as f:
                json.dump(metadata, f, indent=2, default=str)
            
            self.stdout.write(f'💾 Metadatos guardados en: {metadata_path}')
            
        except Exception as e:
            logger.warning(f"Error guardando metadatos del modelo: {str(e)}")

    def _save_metrics_to_file(self, metrics, best_model):
        """Guarda las métricas en un archivo JSON para seguimiento histórico"""
        try:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            metrics_dir = os.path.join(os.path.dirname(__file__), '..', '..', 'ml', 'metrics')
            os.makedirs(metrics_dir, exist_ok=True)
            
            filename = f'metrics_{timestamp}.json'
            filepath = os.path.join(metrics_dir, filename)
            
            with open(filepath, 'w') as f:
                json.dump({
                    'timestamp': timestamp,
                    'best_model': best_model,
                    'metrics': metrics,
                }, f, indent=2, default=str)
            
            self.stdout.write(f'💾 Métricas guardadas en: {filepath}')
            
        except Exception as e:
            logger.warning(f"Error guardando métricas: {str(e)}")

    def _validate_data_quality(self, df):
        """Valida la calidad de los datos antes de entrenar"""
        issues = []
        
        # Verificar valores nulos
        null_counts = df.isnull().sum()
        for column, count in null_counts.items():
            if count > 0:
                null_percent = (count / len(df)) * 100
                if null_percent > 20:
                    issues.append(f'⚠️ {column}: {null_percent:.1f}% valores nulos')
        
        # Verificar desbalanceo de clases
        if 'abandono' in df.columns:
            class_counts = df['abandono'].value_counts()
            if len(class_counts) > 1:
                min_class = class_counts.min()
                max_class = class_counts.max()
                if min_class / max_class < 0.3:
                    issues.append(f'⚠️ Desbalanceo de clases: {min_class} vs {max_class}')
        
        # Verificar valores atípicos
        numeric_cols = df.select_dtypes(include=['float64', 'int64']).columns
        for col in numeric_cols:
            if col != 'abandono':
                q1 = df[col].quantile(0.25)
                q3 = df[col].quantile(0.75)
                iqr = q3 - q1
                outliers = df[(df[col] < q1 - 1.5 * iqr) | (df[col] > q3 + 1.5 * iqr)]
                if len(outliers) > len(df) * 0.1:
                    issues.append(f'⚠️ {col}: {len(outliers)} valores atípicos')
        
        if issues:
            self.stdout.write('\n⚠️ Problemas de calidad de datos detectados:')
            for issue in issues:
                self.stdout.write(f'  {issue}')
            self.stdout.write('💡 Considera limpiar los datos antes de entrenar.')
        
        return len(issues) == 0