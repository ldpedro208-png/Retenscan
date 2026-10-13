# core/templatetags/custom_filters.py
from django import template
from django.utils.safestring import mark_safe
import re

register = template.Library()

@register.filter
def highlight_code(text):
    """
    Detecta bloques de código en el texto y los envuelve con etiquetas para Highlight.js
    """
    if not text:
        return text
    
    # Patrón para detectar bloques de código con triple backtick
    # ```python
    # código aquí
    # ```
    pattern = r'```(\w*)\s*\n(.*?)```'
    
    def replace_code(match):
        language = match.group(1) or 'text'
        code = match.group(2)
        return f'<div class="code-block-wrapper"><span class="code-language-badge">{language}</span><pre><code class="language-{language}">{code}</code></pre></div>'
    
    # Reemplazar bloques de código
    result = re.sub(pattern, replace_code, text, flags=re.DOTALL)
    
    # También detectar código inline con `código`
    # inline_pattern = r'`([^`]+)`'
    # result = re.sub(inline_pattern, r'<code class="inline-code">\1</code>', result)
    
    return mark_safe(result)


@register.filter
def get_item(dictionary, key):
    """Obtiene un valor de un diccionario por su clave"""
    if dictionary is None:
        return None
    return dictionary.get(key)