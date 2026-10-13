# core/templatetags/custom_filters.py
from django import template
from django.utils.safestring import mark_safe
import re

register = template.Library()


@register.filter
def multiply(value, arg):
    """
    Multiplica un valor por un argumento
    Ejemplo: {{ 5|multiply:2 }} -> 10
    """
    try:
        return float(value) * float(arg)
    except (ValueError, TypeError):
        return 0


@register.filter
def divide(value, arg):
    """
    Divide un valor por un argumento
    Ejemplo: {{ 10|divide:2 }} -> 5
    """
    try:
        if float(arg) == 0:
            return 0
        return float(value) / float(arg)
    except (ValueError, TypeError):
        return 0


@register.filter
def percentage(value, arg):
    """
    Calcula el porcentaje de value sobre arg
    Ejemplo: {{ 5|percentage:20 }} -> 25.0
    """
    try:
        if float(arg) == 0:
            return 0
        return (float(value) / float(arg)) * 100
    except (ValueError, TypeError):
        return 0


@register.filter
def highlight_code(text):
    """
    Detecta bloques de código en el texto y los envuelve con etiquetas para Highlight.js
    """
    if not text:
        return text
    
    # Patrón para detectar bloques de código con triple backtick
    pattern = r'```(\w*)\s*\n(.*?)```'
    
    def replace_code(match):
        language = match.group(1) or 'text'
        code = match.group(2)
        code = code.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
        return f'<div class="code-block-wrapper"><span class="code-language-badge">{language}</span><pre><code class="language-{language}">{code}</code></pre></div>'
    
    result = re.sub(pattern, replace_code, text, flags=re.DOTALL)
    result = result.replace('\n', '<br>')
    
    return mark_safe(result)


@register.filter
def get_item(dictionary, key):
    """Obtiene un valor de un diccionario por su clave"""
    if dictionary is None:
        return None
    return dictionary.get(key)


@register.filter
def get_item(dictionary, key):
    """
    Obtiene un valor de un diccionario usando una clave.
    Uso: {{ diccionario|get_item:clave }}
    """
    if dictionary is None:
        return None
    return dictionary.get(key)

@register.filter
def get_attr(obj, attr_name):
    """
    Obtiene un atributo de un objeto usando su nombre como string.
    Uso: {{ objeto|get_attr:"nombre_atributo" }}
    """
    return getattr(obj, attr_name, None)