# biblioteca/utils/sanitizer.py
"""
Sanitizador de HTML para contenido de materiales de apoyo.

Usa bleach para eliminar todo HTML peligroso (scripts, eventos, iframes, etc.)
y dejar solo un subconjunto seguro de etiquetas para renderizar con |safe.
"""
import bleach
from bleach.css_sanitizer import CSSSanitizer


# ============================================
# CONFIGURACIÓN DE LISTA BLANCA
# ============================================

# Etiquetas HTML permitidas en el contenido
ALLOWED_TAGS = [
    # Texto y formato
    'p', 'br', 'hr',
    'strong', 'b', 'em', 'i', 'u', 's', 'del', 'ins',
    'sub', 'sup', 'small', 'mark',
    # Encabezados
    'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
    # Listas
    'ul', 'ol', 'li',
    # Citas y bloques
    'blockquote', 'pre', 'code',
    # Enlaces
    'a',
    # Imágenes (controladas)
    'img', 'figure', 'figcaption',
    # Tablas
    'table', 'thead', 'tbody', 'tfoot', 'tr', 'th', 'td',
    # Separadores
    'div', 'span',
]

# Atributos permitidos por etiqueta
ALLOWED_ATTRIBUTES = {
    'a': ['href', 'title', 'target', 'rel'],
    'img': ['src', 'alt', 'title', 'width', 'height', 'loading'],
    'td': ['colspan', 'rowspan'],
    'th': ['colspan', 'rowspan'],
    'div': ['class'],
    'span': ['class'],
    'p': ['class'],
    'h1': ['class'],
    'h2': ['class'],
    'h3': ['class'],
    'h4': ['class'],
    'h5': ['class'],
    'h6': ['class'],
    'blockquote': ['class'],
    'pre': ['class'],
    'code': ['class'],
    'table': ['class'],
}

# Protocolos permitidos en URLs
ALLOWED_PROTOCOLS = ['http', 'https', 'mailto']

# Reglas CSS permitidas (solo si usamos estilos inline controlados)
ALLOWED_CSS_PROPERTIES = [
    'color', 'background-color', 'text-align',
    'font-weight', 'font-style', 'text-decoration',
    'margin', 'padding', 'border',
]

# Sanitizador de CSS (por si permitimos estilos inline en el futuro)
_css_sanitizer = CSSSanitizer(allowed_css_properties=ALLOWED_CSS_PROPERTIES)


# ============================================
# FUNCIÓN PRINCIPAL
# ============================================

def sanitizar_html(html: str, linkify: bool = True) -> str:
    """
    Limpia el HTML eliminando todo lo que no esté en la lista blanca.

    Args:
        html: contenido HTML crudo del usuario
        linkify: si True, convierte URLs planas en enlaces

    Returns:
        HTML seguro listo para renderizar con |safe
    """
    if not html:
        return ''

    # 1. Limpieza principal
    limpio = bleach.clean(
        html,
        tags=ALLOWED_TAGS,
        attributes=ALLOWED_ATTRIBUTES,
        protocols=ALLOWED_PROTOCOLS,
        css_sanitizer=_css_sanitizer,
        strip=True,            # elimina etiquetas no permitidas (no las escapa)
        strip_comments=True,   # elimina comentarios HTML
    )

    # 2. Convertir URLs planas en enlaces (opcional)
    if linkify:
        limpio = bleach.linkify(
            limpio,
            callbacks=[
                bleach.callbacks.nofollow,   # agrega rel="nofollow"
                _agregar_target_blank,       # agrega target="_blank" + rel seguro
            ],
        )

    return limpio


def _agregar_target_blank(attrs, new=False):
    """
    Callback para añadir target="_blank" y rel seguro a enlaces externos.
    Evita reverse tabnabbing.
    """
    href = attrs.get((None, 'href'), '')
    if href and (href.startswith('http://') or href.startswith('https://')):
        attrs[(None, 'target')] = '_blank'
        # rel=noopener evita que la nueva pestaña acceda a window.opener
        # rel=noreferrer no envía el header Referer
        rel = attrs.get((None, 'rel'), '')
        rel_partes = set(filter(None, (rel + ' noopener noreferrer').split()))
        attrs[(None, 'rel')] = ' '.join(sorted(rel_partes))
    return attrs


# ============================================
# VALIDACIÓN: DETECTAR CONTENIDO PELIGROSO
# ============================================

def contiene_html_peligroso(html: str) -> bool:
    """
    Detecta si el HTML contiene elementos potencialmente peligrosos.
    Útil para logging/auditoría, no para bloquear (usar sanitizar_html).
    """
    if not html:
        return False

    patrones_sospechosos = [
        '<script', '</script',
        'javascript:',
        'onerror=', 'onload=', 'onclick=',
        '<iframe', '</iframe',
        '<object', '</object',
        '<embed', '</embed',
        '<form', '</form',
        'data:text/html',
        'vbscript:',
    ]
    html_lower = html.lower()
    return any(p in html_lower for p in patrones_sospechosos)


def extraer_texto_plano(html: str) -> str:
    """
    Extrae solo el texto del HTML, útil para previews y búsquedas.
    """
    if not html:
        return ''
    limpio = bleach.clean(html, tags=[], strip=True)
    return limpio.strip()