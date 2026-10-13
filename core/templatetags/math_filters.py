# core/templatetags/math_filters.py
"""
Filtros personalizados para operaciones matemáticas en plantillas Django
"""
from django import template

register = template.Library()


@register.filter
def add(value, arg):
    """Suma arg a value"""
    try:
        return float(value) + float(arg)
    except (ValueError, TypeError):
        return 0


@register.filter
def multiply(value, arg):
    """Multiplica value por arg"""
    try:
        return float(value) * float(arg)
    except (ValueError, TypeError):
        return 0


@register.filter
def divisibleby(value, arg):
    """Divide value entre arg (para uso en widthratio)"""
    try:
        if float(arg) == 0:
            return 0
        return float(value) / float(arg)
    except (ValueError, TypeError):
        return 0