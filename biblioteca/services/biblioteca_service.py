# biblioteca/services/biblioteca_service.py
from django.db.models import Count, Q, F, Avg
from django.utils import timezone
from datetime import timedelta
from ..models import RecursoBiblioteca, AccesoRecurso, MaterialApoyo


class BibliotecaService:
    """Servicio central de la biblioteca digital."""
    # ============================================
    # PERMISOS
    # ============================================

    @staticmethod
    def puede_subir_recurso(user, materia_id=None):
        """
        Regla:
        - Admin/staff: siempre.
        - Profesor: solo si tiene la materia asignada en MateriaProfesor.
        - Tutor: solo material de apoyo (sin materia).
        """
        if not user.is_authenticated:
            return False

        if user.is_staff or user.rol == 'admin':
            return True

        if user.rol == 'profesor':
            if not materia_id:
                return False
            from core.models import MateriaProfesor
            return MateriaProfesor.objects.filter(
                usuario=user, materia_id=materia_id
            ).exists()

        return False

    @staticmethod
    def puede_gestionar_material_apoyo(user):
        """Material de apoyo: admin o tutor."""
        if not user.is_authenticated:
            return False
        return user.is_staff or user.rol in ['admin', 'tutor']

    # ============================================
    # REGISTRO DE ACCESO
    # ============================================

    @classmethod
    def registrar_acceso(cls, estudiante, recurso, accion, request=None,
                          calificacion=None, comentario=None, tiempo_lectura=0):
        """Registra una interacción y actualiza métricas del recurso."""
        ip = None
        if request:
            x_forwarded = request.META.get('HTTP_X_FORWARDED_FOR')
            ip = x_forwarded.split(',')[0] if x_forwarded else request.META.get('REMOTE_ADDR')

        acceso = AccesoRecurso.objects.create(
            idEstudiante=estudiante,
            idRecurso=recurso,
            accion=accion,
            calificacion=calificacion,
            comentario=comentario,
            tiempo_lectura_minutos=tiempo_lectura,
            ip_address=ip,
        )

        # Actualizar contadores del recurso
        update_fields = {}
        if accion == 'vista':
            update_fields['total_vistas'] = F('total_vistas') + 1
        elif accion == 'descarga':
            update_fields['total_descargas'] = F('total_descargas') + 1

        if update_fields:
            RecursoBiblioteca.objects.filter(pk=recurso.pk).update(**update_fields)

        # Recalcular promedio de calificaciones
        if accion == 'calificacion' and calificacion:
            avg = AccesoRecurso.objects.filter(
                idRecurso=recurso, accion='calificacion'
            ).aggregate(p=Avg('calificacion'))['p'] or 0
            RecursoBiblioteca.objects.filter(pk=recurso.pk).update(
                promedio_calificacion=round(avg, 2)
            )

        return acceso

    # ============================================
    # CONSULTAS
    # ============================================

    @staticmethod
    def recursos_para_estudiante(estudiante, universidad_id=None):
        """Recursos visibles para un estudiante (publicados, de su universidad)."""
        qs = RecursoBiblioteca.objects.filter(
            estado='publicado',
            idUniversidad_id=universidad_id or estudiante.idUniversidad_id
        ).select_related('idMateria', 'idCategoria', 'subido_por')
        return qs

    @staticmethod
    def buscar(query, universidad_id, materia_id=None, tipo=None, categoria_id=None):
        """Búsqueda con filtros. Usa icontains; para producción migrar a full-text."""
        qs = RecursoBiblioteca.objects.filter(
            estado='publicado',
            idUniversidad_id=universidad_id
        )

        if query:
            qs = qs.filter(
                Q(titulo__icontains=query) |
                Q(autor__icontains=query) |
                Q(descripcion__icontains=query) |
                Q(palabras_clave__icontains=query)
            )
        if materia_id:
            qs = qs.filter(idMateria_id=materia_id)
        if tipo:
            qs = qs.filter(tipo=tipo)
        if categoria_id:
            qs = qs.filter(idCategoria_id=categoria_id)

        return qs.order_by('-destacado', '-created_at')

    # ============================================
    # MÉTRICAS PARA SCORING
    # ============================================

    @staticmethod
    def accesos_ultimos_dias(estudiante, dias=30):
        desde = timezone.now() - timedelta(days=dias)
        return AccesoRecurso.objects.filter(
            idEstudiante=estudiante, created_at__gte=desde
        )

    @staticmethod
    def resumen_actividad(estudiante, dias=30):
        """Resumen consolidado para scoring e interfaz de tutor."""
        qs = BibliotecaService.accesos_ultimos_dias(estudiante, dias)
        return {
            'total_accesos': qs.count(),
            'vistas': qs.filter(accion='vista').count(),
            'descargas': qs.filter(accion='descarga').count(),
            'lecturas_completas': qs.filter(accion='lectura_completa').count(),
            'favoritos': qs.filter(accion='favorito').count(),
            'categorias_distintas': qs.values('idRecurso__idCategoria').distinct().count(),
            'materias_distintas': qs.values('idRecurso__idMateria').distinct().count(),
        }

    # ============================================
    # RECOMENDACIONES
    # ============================================

    @staticmethod
    def recomendar_material_apoyo(factor_riesgo, limite=5):
        """Sugiere materiales según el factor de riesgo del estudiante."""
        if not factor_riesgo:
            return MaterialApoyo.objects.filter(activo=True)[:limite]

        return MaterialApoyo.objects.filter(
            activo=True,
            idFactorRiesgo=factor_riesgo
        )[:limite] or MaterialApoyo.objects.filter(activo=True)[:limite]

    @staticmethod
    def recomendar_recursos_academicos(estudiante, limite=5):
        """Sugiere recursos de las materias donde el estudiante va mal."""
        from core.models import HistorialAcademico
        materias_criticas = HistorialAcademico.objects.filter(
            idEstudiante=estudiante,
            estado_materia__in=['Reprobada', 'Cursando']
        ).values_list('idMateria_id', flat=True)[:3]

        return RecursoBiblioteca.objects.filter(
            estado='publicado',
            idMateria_id__in=materias_criticas
        ).order_by('-destacado', '-total_descargas')[:limite]