# core/utils.py


import secrets
import string
import logging
import unicodedata
import re
import logging

logger = logging.getLogger(__name__)

# ✅ Exportar logger
__all__ = [
    'logger',
    'generar_password_temporal',
    'generar_username_desde_nombre',
    'generar_username_unique',
    'parse_decimal',
    'formatear_fecha_mensaje',
    'obtener_iniciales',
    'truncar_texto',
    'slugify_username',
]

# ============================================
# FUNCIONES DE SEGURIDAD
# ============================================

def generar_password_temporal(longitud=10):
    """
    Genera una contraseña temporal segura.
    
    Args:
        longitud (int): Longitud de la contraseña (por defecto 10)
    
    Returns:
        str: Contraseña temporal
    """
    caracteres = string.ascii_letters + string.digits + "!@#$%^&*"
    return ''.join(secrets.choice(caracteres) for _ in range(longitud))


# ============================================
# FUNCIONES DE NORMALIZACIÓN
# ============================================

def _normalizar_texto(texto):
    """
    Normaliza un texto: quita acentos, espacios y caracteres especiales.
    Retorna solo letras minúsculas y números.
    
    Args:
        texto (str): Texto a normalizar
    
    Returns:
        str: Texto normalizado (solo letras minúsculas y números)
    """
    if not texto:
        return ''
    # Descomponer caracteres acentuados (José → Jose)
    texto = unicodedata.normalize('NFKD', texto)
    # Eliminar diacríticos (acentos, tildes)
    texto = texto.encode('ASCII', 'ignore').decode('ASCII')
    # Eliminar todo lo que no sea letra o número
    texto = re.sub(r'[^a-zA-Z0-9]', '', texto)
    return texto.lower()


def _dividir_nombre_apellido(first_name, last_name):
    """
    Divide el nombre y apellido en sus partes individuales normalizadas.
    
    Args:
        first_name (str): Nombre(s) del usuario
        last_name (str): Apellido(s) del usuario
    
    Returns:
        tuple: (partes_nombre, partes_apellido) como listas de strings normalizados
    """
    nombre_partes = [_normalizar_texto(p) for p in first_name.strip().split() if p.strip()]
    apellido_partes = [_normalizar_texto(p) for p in last_name.strip().split() if p.strip()]
    
    # Filtrar partes vacías
    nombre_partes = [p for p in nombre_partes if p]
    apellido_partes = [p for p in apellido_partes if p]
    
    return nombre_partes, apellido_partes


# ============================================
# GENERACIÓN DE USERNAME ÚNICO
# ============================================

def generar_username_desde_nombre(first_name, last_name, model=None):
    """
    Genera un username único y ORIGINAL basado en el nombre y apellido.
    
    Estrategia (en orden de prioridad):
    
    NIVEL 1 - Combinaciones simples y limpias:
    1. Primera letra del nombre + apellido completo → jperez, cdelacruz
    2. Nombre completo + primera letra del apellido → juanp, carlosd
    
    NIVEL 2 - Cortes de nombre/apellido:
    3. Primeras 2 letras del nombre + apellido completo → juperez
    4. Nombre completo + 2 primeras letras del apellido → juanpe
    5. Primeras 3 letras del nombre + primeras 3 del apellido → juaper
    
    NIVEL 3 - Con guion bajo (más legibles):
    6. juan_perez, j_perez, juan_p, j_pe
    
    NIVEL 4 - Iniciales y consonantes:
    7. Inicial + consonantes del apellido → jprz
    8. Iniciales completas → jpg
    
    NIVEL 5 - Combinaciones creativas:
    9. Nombre + apellido invertido corto → jper
    10. 3 letras nombre + 3 últimas del apellido → juarez
    11. Con año actual → jperez2024
    
    NIVEL 6 - Abreviaturas:
    12. Inicial + apellido + inicial → jperezp
    13. Nombre + iniciales de apellidos → juang
    
    ÚLTIMO RECURSO:
    14. Número incremental → jperez1
    15. Timestamp → jperez1234567890
    
    Args:
        first_name (str): Nombre(s) del usuario
        last_name (str): Apellido(s) del usuario
        model: Modelo de Usuario (por defecto Usuario)
    
    Returns:
        str: Username único y original
    
    Raises:
        ValueError: Si el nombre o apellido están vacíos
    """
    # ✅ Importar Usuario si no se pasa el modelo
    if model is None:
        from .models import Usuario
        model = Usuario
    
    # ✅ Normalizar nombre y apellido
    nombre_partes, apellido_partes = _dividir_nombre_apellido(first_name, last_name)
    
    if not nombre_partes:
        raise ValueError("El nombre es obligatorio para generar el username.")
    if not apellido_partes:
        raise ValueError("El apellido es obligatorio para generar el username.")
    
    # ✅ Extraer partes combinadas
    nombre_completo = ''.join(nombre_partes)
    apellido_completo = ''.join(apellido_partes)
    primer_nombre = nombre_partes[0]
    primer_apellido = apellido_partes[0]
    
    # ✅ Lista de candidatos en orden de prioridad
    candidatos = []
    
    # ============================================
    # NIVEL 1: Combinaciones simples y limpias
    # ============================================
    # 1. Primera letra del nombre + apellido completo → jperez, cdelacruz
    candidatos.append(f"{primer_nombre[0]}{apellido_completo}")
    
    # 2. Nombre completo + primera letra del apellido → juanp, carlosd
    candidatos.append(f"{nombre_completo}{apellido_completo[0]}")
    
    # ============================================
    # NIVEL 2: Cortes de nombre/apellido
    # ============================================
    # 3. Primeras 2 letras del nombre + apellido completo → juperez
    if len(primer_nombre) >= 2:
        candidatos.append(f"{primer_nombre[:2]}{apellido_completo}")
    
    # 4. Nombre completo + 2 primeras letras del apellido → juanpe
    if len(apellido_completo) >= 2:
        candidatos.append(f"{nombre_completo}{apellido_completo[:2]}")
    
    # 5. Primeras 3 letras del nombre + primeras 3 del apellido → juaper
    if len(primer_nombre) >= 3 and len(apellido_completo) >= 3:
        candidatos.append(f"{primer_nombre[:3]}{apellido_completo[:3]}")
    
    # ============================================
    # NIVEL 3: Con guion bajo (más legibles)
    # ============================================
    # 6. Combinaciones con guion bajo
    candidatos.append(f"{nombre_completo}_{apellido_completo}")
    candidatos.append(f"{primer_nombre[0]}_{apellido_completo}")
    candidatos.append(f"{nombre_completo}_{apellido_completo[0]}")
    if len(apellido_completo) >= 2:
        candidatos.append(f"{primer_nombre[0]}_{apellido_completo[:2]}")
    
    # ============================================
    # NIVEL 4: Iniciales y consonantes
    # ============================================
    # 7. Inicial del nombre + consonantes del apellido → jprz
    consonantes_apellido = re.sub(r'[aeiou]', '', apellido_completo)
    if consonantes_apellido:
        candidatos.append(f"{primer_nombre[0]}{consonantes_apellido}")
    
    # 8. Iniciales de todos los nombres y apellidos → jpg
    iniciales = ''.join([p[0] for p in nombre_partes + apellido_partes])
    if len(iniciales) >= 2:
        candidatos.append(iniciales)
        if len(primer_apellido) >= 3:
            candidatos.append(f"{iniciales}{primer_apellido[:3]}")
    
    # ============================================
    # NIVEL 5: Combinaciones creativas
    # ============================================
    # 9. Nombre + apellido invertido corto → jper
    if len(apellido_completo) >= 3:
        candidatos.append(f"{nombre_completo}{apellido_completo[-3:]}")
    
    # 10. 3 letras del nombre + 3 últimas del apellido → juarez (jua + rez)
    if len(primer_nombre) >= 3 and len(apellido_completo) >= 3:
        candidatos.append(f"{primer_nombre[:3]}{apellido_completo[-3:]}")
    
    # 11. Con año actual → jperez2024
    from datetime import datetime
    anio_actual = datetime.now().year
    candidatos.append(f"{primer_nombre[0]}{apellido_completo}{anio_actual}")
    candidatos.append(f"{nombre_completo}{apellido_completo}{anio_actual}")
    
    # ============================================
    # NIVEL 6: Abreviaturas
    # ============================================
    # 12. Inicial + apellido + inicial (si hay segundo nombre) → jperezp
    if len(nombre_partes) > 1:
        candidatos.append(f"{primer_nombre[0]}{apellido_completo}{nombre_partes[1][0]}")
    
    # 13. Nombre + iniciales de apellidos → juang
    if len(apellido_partes) > 1:
        iniciales_apellido = ''.join([p[0] for p in apellido_partes])
        candidatos.append(f"{nombre_completo}{iniciales_apellido}")
    
    # ============================================
    # Filtrar y validar candidatos
    # ============================================
    candidatos_unicos = []
    vistos = set()
    for c in candidatos:
        # Validar: mínimo 3, máximo 30 caracteres
        if c and len(c) >= 3 and c not in vistos:
            c_limpio = c[:30]  # Truncar si es muy largo
            if c_limpio not in vistos:
                candidatos_unicos.append(c_limpio)
                vistos.add(c_limpio)
    
    # ✅ Buscar el primer candidato disponible
    for candidato in candidatos_unicos:
        if not model.objects.filter(username=candidato).exists():
            logger.info(f"✅ Username generado: '{candidato}' para {first_name} {last_name}")
            return candidato
    
    # ============================================
    # ÚLTIMO RECURSO: número incremental
    # ============================================
    base = candidatos_unicos[0] if candidatos_unicos else f"{primer_nombre[0]}{apellido_completo}"
    base = base[:28]
    
    for counter in range(1, 1000):
        candidato = f"{base}{counter}"
        if not model.objects.filter(username=candidato).exists():
            logger.warning(f"⚠️ Username generado con número: '{candidato}'")
            return candidato
    
    # Si todo falla, usar timestamp
    import time
    candidato = f"{base}{int(time.time())}"
    logger.warning(f"⚠️ Username generado con timestamp: '{candidato}'")
    return candidato


def generar_username_unique(base_username, model):
    """
    Genera un username único basado en uno base (método simple).
    
    Args:
        base_username (str): Username base
        model: Modelo de Usuario
    
    Returns:
        str: Username único
    """
    username = base_username
    counter = 1
    while model.objects.filter(username=username).exists():
        username = f"{base_username}{counter}"
        counter += 1
    return username


# ============================================
# FUNCIONES AUXILIARES
# ============================================

def parse_decimal(value, default=0):
    """
    Convierte un valor a Decimal de forma segura.
    
    Args:
        value: Valor a convertir
        default: Valor por defecto si falla
    
    Returns:
        Decimal: Valor convertido
    """
    from decimal import Decimal
    if value is None or value == '':
        return Decimal(str(default))
    try:
        return Decimal(str(value))
    except (ValueError, TypeError):
        return Decimal(str(default))


def formatear_fecha_mensaje(fecha):
    """
    Formatea una fecha para mostrar en mensajes.
    
    Args:
        fecha: Objeto datetime
    
    Returns:
        str: Fecha formateada (ej: "Hace 5 minutos", "Ayer", etc.)
    """
    from django.utils import timezone
    
    ahora = timezone.now()
    diferencia = ahora - fecha
    
    if diferencia.days == 0:
        if diferencia.seconds < 60:
            return "Hace unos segundos"
        elif diferencia.seconds < 3600:
            minutos = diferencia.seconds // 60
            return f"Hace {minutos} minuto{'s' if minutos > 1 else ''}"
        else:
            horas = diferencia.seconds // 3600
            return f"Hace {horas} hora{'s' if horas > 1 else ''}"
    elif diferencia.days == 1:
        return "Ayer"
    elif diferencia.days < 7:
        return f"Hace {diferencia.days} día{'s' if diferencia.days > 1 else ''}"
    else:
        return fecha.strftime('%d/%m/%Y %H:%M')


def obtener_iniciales(nombre_completo):
    """
    Obtiene las iniciales de un nombre completo.
    
    Args:
        nombre_completo (str): Nombre completo
    
    Returns:
        str: Iniciales en mayúsculas (ej: "Juan Pérez" → "JP")
    """
    if not nombre_completo:
        return ''
    
    partes = nombre_completo.strip().split()
    iniciales = ''.join([p[0].upper() for p in partes if p])
    return iniciales


def truncar_texto(texto, longitud_maxima=50, sufijo='...'):
    """
    Trunca un texto a una longitud máxima.
    
    Args:
        texto (str): Texto a truncar
        longitud_maxima (int): Longitud máxima
        sufijo (str): Sufijo a agregar
    
    Returns:
        str: Texto truncado
    """
    if not texto:
        return ''
    
    if len(texto) <= longitud_maxima:
        return texto
    
    return texto[:longitud_maxima - len(sufijo)] + sufijo


def slugify_username(texto):
    """
    Convierte un texto en un slug válido para username.
    
    Args:
        texto (str): Texto a convertir
    
    Returns:
        str: Slug válido para username
    """
    return _normalizar_texto(texto)