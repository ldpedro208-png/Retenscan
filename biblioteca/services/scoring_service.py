# biblioteca/services/scoring_service.py
"""
Servicio que aporta señales de la biblioteca al sistema de scoring de riesgo.
La biblioteca NO crea factores; aporta evidencia a factores existentes.
"""
from django.utils import timezone
from datetime import timedelta
from django.db.models import Count
from ..models import AccesoRecurso


# ============================================
# FUNCIONES DE EVIDENCIA (0.0 - 1.0)
# ============================================

def _normalizar(valor, min_v, max_v):
    if max_v == min_v:
        return 0.0
    return max(0.0, min(1.0, (valor - min_v) / (max_v - min_v)))


def evidencia_sin_biblioteca_30d(estudiante):
    """Retorna 1.0 si NO accedió en 30 días, 0.0 si accedió normal."""
    desde = timezone.now() - timedelta(days=30)
    accesos = AccesoRecurso.objects.filter(
        idEstudiante=estudiante, created_at__gte=desde
    ).count()
    return 1.0 - _normalizar(accesos, 0, 10)


def evidencia_solo_descarga(estudiante):
    """Detecta patrón: descarga pero nunca lee completo."""
    desde = timezone.now() - timedelta(days=30)
    datos = AccesoRecurso.objects.filter(
        idEstudiante=estudiante, created_at__gte=desde
    ).values('accion').annotate(c=Count('id'))

    mapa = {d['accion']: d['c'] for d in datos}
    descargas = mapa.get('descarga', 0)
    lecturas = mapa.get('lectura_completa', 0)

    if descargas < 3:
        return 0.0
    ratio = lecturas / descargas if descargas else 0
    return 1.0 - _normalizar(ratio, 0.2, 0.7)


def evidencia_solo_material_obligatorio(estudiante):
    """Si solo accede a material obligatorio, señal de desmotivación."""
    desde = timezone.now() - timedelta(days=30)
    base = AccesoRecurso.objects.filter(idEstudiante=estudiante, created_at__gte=desde)
    total = base.count()
    obligatorios = base.filter(idRecurso__es_obligatorio=True).count()

    if total < 5:
        return 0.0
    ratio_voluntario = (total - obligatorios) / total
    return 1.0 - _normalizar(ratio_voluntario, 0.0, 0.4)


def evidencia_caida_uso_biblioteca(estudiante):
    """Caída brusca de actividad bibliotecaria."""
    ahora = timezone.now()
    mes_actual = AccesoRecurso.objects.filter(
        idEstudiante=estudiante, created_at__gte=ahora - timedelta(days=30)
    ).count()
    mes_anterior = AccesoRecurso.objects.filter(
        idEstudiante=estudiante,
        created_at__gte=ahora - timedelta(days=60),
        created_at__lt=ahora - timedelta(days=30)
    ).count()

    if mes_anterior < 5:
        return 0.0
    caida = (mes_anterior - mes_actual) / mes_anterior
    return _normalizar(caida, 0.3, 0.8)


def evidencia_biblioteca_nocturna(estudiante):
    """Accesos entre 23h y 5h → posible estrés."""
    desde = timezone.now() - timedelta(days=30)
    qs = AccesoRecurso.objects.filter(idEstudiante=estudiante, created_at__gte=desde)
    total = qs.count()
    if total < 5:
        return 0.0
    nocturnos = qs.filter(created_at__hour__gte=23).count() + \
                qs.filter(created_at__hour__lt=5).count()
    return _normalizar(nocturnos / total, 0.15, 0.4)


def evidencia_motivacional_intenso(estudiante):
    """Muchos accesos a material motivacional en poco tiempo = crisis."""
    desde = timezone.now() - timedelta(days=7)
    accesos = AccesoRecurso.objects.filter(
        idEstudiante=estudiante,
        created_at__gte=desde,
        idRecurso__idCategoria__nombre__in=['Motivacional', 'Salud Mental']
    ).count()
    return _normalizar(accesos, 2, 8)


# ============================================
# DICCIONARIO DE EVIDENCIAS POR FACTOR
# ============================================

EVIDENCIAS_BIBLIOTECA_POR_FACTOR = {
    'Bajo Rendimiento Académico': [
        {'nombre': 'solo_descarga_biblioteca', 'peso': 0.10, 'fn': evidencia_solo_descarga},
    ],
    'Desmotivación': [
        {'nombre': 'sin_biblioteca_30d', 'peso': 0.20, 'fn': evidencia_sin_biblioteca_30d},
        {'nombre': 'solo_material_obligatorio', 'peso': 0.15, 'fn': evidencia_solo_material_obligatorio},
        {'nombre': 'caida_uso_biblioteca', 'peso': 0.15, 'fn': evidencia_caida_uso_biblioteca},
    ],
    'Estrés Académico': [
        {'nombre': 'biblioteca_nocturna', 'peso': 0.20, 'fn': evidencia_biblioteca_nocturna},
        {'nombre': 'motivacional_intenso', 'peso': 0.20, 'fn': evidencia_motivacional_intenso},
    ],
}


def calcular_evidencias_biblioteca(estudiante):
    """
    Devuelve dict con evidencia por factor, para que el motor de scoring
    las combine con las demás fuentes (notas, asistencia, etc.).
    """
    resultado = {}
    for factor, evidencias in EVIDENCIAS_BIBLIOTECA_POR_FACTOR.items():
        detalle = []
        score = 0.0
        peso_total = 0.0
        for ev in evidencias:
            try:
                valor = float(ev['fn'](estudiante))
            except Exception:
                valor = 0.0
            valor = max(0.0, min(1.0, valor))
            score += valor * ev['peso']
            peso_total += ev['peso']
            detalle.append({'evidencia': ev['nombre'], 'valor': round(valor, 3), 'peso': ev['peso']})

        resultado[factor] = {
            'score_biblioteca': round(score / peso_total, 3) if peso_total else 0.0,
            'detalle': detalle,
        }
    return resultado


def reduccion_por_biblioteca(estudiante):
    """
    El uso positivo de biblioteca reduce el score de riesgo (máx 10 pts).
    Se usará en el cálculo global del score.
    """
    desde = timezone.now() - timedelta(days=15)
    base = AccesoRecurso.objects.filter(idEstudiante=estudiante, created_at__gte=desde)

    accesos_apoyo = base.filter(
        idRecurso__idCategoria__tipo='apoyo'
    ).count()
    lecturas = base.filter(accion='lectura_completa').count()
    diversidad = base.values('idRecurso__idCategoria').distinct().count()

    puntos = (
        min(accesos_apoyo * 1.0, 4) +
        min(lecturas * 0.5, 3) +
        min(diversidad * 0.5, 3)
    )
    return min(puntos, 10)