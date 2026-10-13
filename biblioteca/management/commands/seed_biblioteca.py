# biblioteca/management/commands/seed_biblioteca.py
from django.core.management.base import BaseCommand
from biblioteca.models import CategoriaRecurso, MaterialApoyo
from core.models import CatalogoUniversidad, CatalogoFactorRiesgo


class Command(BaseCommand):
    help = 'Crea categorías y materiales de apoyo iniciales'

    def handle(self, *args, **kwargs):
        # Categorías académicas
        cats = [
            ('Libros', 'academico', 'fa-book', 1),
            ('Apuntes', 'academico', 'fa-file-alt', 2),
            ('Papers', 'academico', 'fa-scroll', 3),
            ('Videos', 'academico', 'fa-video', 4),
            ('Ejercicios', 'academico', 'fa-pencil', 5),
            # Categorías de apoyo
            ('Motivacional', 'apoyo', 'fa-heart', 10),
            ('Hábitos de Estudio', 'apoyo', 'fa-clock', 11),
            ('Salud Mental', 'apoyo', 'fa-brain', 12),
            ('Educación Financiera', 'apoyo', 'fa-coins', 13),
        ]
        for nombre, tipo, icono, orden in cats:
            CategoriaRecurso.objects.get_or_create(
                nombre=nombre,
                defaults={'tipo': tipo, 'icono': icono, 'orden': orden}
            )
        self.stdout.write(self.style.SUCCESS('✅ Categorías creadas'))