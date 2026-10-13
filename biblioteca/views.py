# biblioteca/views.py
import mimetypes
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.db.models import Q, Count, Sum, Avg
from django.http import FileResponse, Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.views.generic import ListView, DetailView, CreateView, UpdateView
from django.utils import timezone
from datetime import timedelta

from core.models import CatalogoMateria, HistorialAcademico
from .forms import RecursoBibliotecaForm, MaterialApoyoForm
from .models import RecursoBiblioteca, AccesoRecurso, CategoriaRecurso, MaterialApoyo
from .services.biblioteca_service import BibliotecaService


# ============================================
# HELPER: universidad del usuario
# ============================================

def _get_universidad_id(user):
    """Obtiene el ID de universidad del usuario (None si es superuser)."""
    if user.is_superuser:
        return None
    return getattr(user, 'idUniversidad_id', None)


# ============================================
# MIXIN DE PERMISOS
# ============================================

class PuedeSubirRecursosMixin(LoginRequiredMixin, UserPassesTestMixin):
    """Admin, profesor (con materia) o tutor."""
    def test_func(self):
        u = self.request.user
        if not u.is_authenticated:
            return False
        return u.is_staff or u.rol in ['admin', 'profesor', 'tutor']

    def handle_no_permission(self):
        messages.error(self.request, "No tienes permisos para esta acción.")
        return redirect('biblioteca:lista')


class PuedeGestionarApoyoMixin(LoginRequiredMixin, UserPassesTestMixin):
    def test_func(self):
        u = self.request.user
        return u.is_authenticated and (u.is_staff or u.rol in ['admin', 'tutor'])

    def handle_no_permission(self):
        messages.error(self.request, "Solo administradores y tutores pueden gestionar material de apoyo.")
        return redirect('biblioteca:lista')


# ============================================
# LISTA / BÚSQUEDA
# ============================================

class ListaRecursosView(LoginRequiredMixin, ListView):
    model = RecursoBiblioteca
    template_name = 'biblioteca/lista_recursos.html'
    context_object_name = 'recursos'
    paginate_by = 12

    def get_queryset(self):
        u = self.request.user
        universidad_id = _get_universidad_id(u)

        query = self.request.GET.get('q', '').strip()
        materia_id = self.request.GET.get('materia') or None
        tipo = self.request.GET.get('tipo') or None
        categoria_id = self.request.GET.get('categoria') or None

        return BibliotecaService.buscar(
            query=query,
            universidad_id=universidad_id,
            materia_id=materia_id,
            tipo=tipo,
            categoria_id=categoria_id,
        )

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        u = self.request.user
        universidad_id = _get_universidad_id(u)

        if universidad_id:
            ctx['materias'] = CatalogoMateria.objects.filter(
                idCarrera__idUniversidad_id=universidad_id
            ).order_by('nombre')
        else:
            ctx['materias'] = CatalogoMateria.objects.all().order_by('nombre')

        ctx['categorias'] = CategoriaRecurso.objects.filter(activo=True)
        ctx['tipos'] = RecursoBiblioteca.TIPO_CHOICES
        ctx['q'] = self.request.GET.get('q', '')
        return ctx


# ============================================
# DETALLE
# ============================================

class DetalleRecursoView(LoginRequiredMixin, DetailView):
    model = RecursoBiblioteca
    template_name = 'biblioteca/detalle_recurso.html'
    context_object_name = 'recurso'

    def get_queryset(self):
        """Filtrar por universidad."""
        qs = super().get_queryset()
        u = self.request.user
        universidad_id = _get_universidad_id(u)

        if universidad_id:
            qs = qs.filter(idUniversidad_id=universidad_id)
        return qs

    def get(self, request, *args, **kwargs):
        self.object = self.get_object()
        if hasattr(request.user, 'estudiante'):
            BibliotecaService.registrar_acceso(
                estudiante=request.user.estudiante,
                recurso=self.object,
                accion='vista',
                request=request,
            )
        return super().get(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        """Maneja la calificación vía AJAX."""
        self.object = self.get_object()

        if not hasattr(request.user, 'estudiante'):
            return JsonResponse({'error': 'Solo estudiantes'}, status=403)

        accion = request.POST.get('accion')
        if accion == 'calificacion':
            calificacion = request.POST.get('calificacion')
            comentario = request.POST.get('comentario', '')

            try:
                calificacion = int(calificacion)
                if not 1 <= calificacion <= 5:
                    raise ValueError
            except (TypeError, ValueError):
                return JsonResponse({'error': 'Calificación inválida'}, status=400)

            BibliotecaService.registrar_acceso(
                estudiante=request.user.estudiante,
                recurso=self.object,
                accion='calificacion',
                request=request,
                calificacion=calificacion,
                comentario=comentario,
            )
            return JsonResponse({'ok': True})

        return JsonResponse({'error': 'Acción no soportada'}, status=400)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)

        if self.object.idMateria:
            ctx['relacionados'] = RecursoBiblioteca.objects.filter(
                estado='publicado',
                idMateria=self.object.idMateria,
                idUniversidad_id=self.object.idUniversidad_id,
            ).exclude(pk=self.object.pk).order_by('-total_vistas')[:5]
        else:
            ctx['relacionados'] = []

        return ctx


# ============================================
# SUBIR RECURSO
# ============================================

class SubirRecursoView(PuedeSubirRecursosMixin, CreateView):
    model = RecursoBiblioteca
    form_class = RecursoBibliotecaForm
    template_name = 'biblioteca/subir_recurso.html'
    success_url = reverse_lazy('biblioteca:mis_recursos')

    def get_form_kwargs(self):
        kw = super().get_form_kwargs()
        kw['user'] = self.request.user
        return kw

    def form_valid(self, form):
        recurso = form.save(commit=False)
        recurso.subido_por = self.request.user

        # Universidad obligatoria (excepto superuser)
        u = self.request.user
        if u.is_superuser:
            if not recurso.idUniversidad_id:
                messages.error(self.request, "Debes especificar una universidad.")
                return redirect('biblioteca:lista')
        else:
            if not u.idUniversidad_id:
                messages.error(self.request, "No tienes universidad asignada.")
                return redirect('biblioteca:lista')
            recurso.idUniversidad = u.idUniversidad

        recurso.save()
        messages.success(self.request, f"Recurso '{recurso.titulo}' creado correctamente.")
        return redirect(self.success_url)


class EditarRecursoView(PuedeSubirRecursosMixin, UpdateView):
    model = RecursoBiblioteca
    form_class = RecursoBibliotecaForm
    template_name = 'biblioteca/subir_recurso.html'
    success_url = reverse_lazy('biblioteca:mis_recursos')

    def get_queryset(self):
        """
        Filtrar por universidad + permisos.
        - Admin: todos los recursos de su universidad
        - Otros: solo los suyos, dentro de su universidad
        """
        qs = super().get_queryset()
        u = self.request.user
        universidad_id = _get_universidad_id(u)

        if universidad_id:
            qs = qs.filter(idUniversidad_id=universidad_id)

        if u.is_staff or u.rol == 'admin':
            return qs
        return qs.filter(subido_por=u)

    def get_form_kwargs(self):
        kw = super().get_form_kwargs()
        kw['user'] = self.request.user
        return kw

    def form_valid(self, form):
        messages.success(self.request, "Recurso actualizado.")
        return super().form_valid(form)


class MisRecursosView(PuedeSubirRecursosMixin, ListView):
    template_name = 'biblioteca/mis_recursos.html'
    context_object_name = 'recursos'
    paginate_by = 15

    def get_queryset(self):
        """Filtrar por universidad + subido_por."""
        u = self.request.user
        universidad_id = _get_universidad_id(u)

        qs = RecursoBiblioteca.objects.filter(
            subido_por=u
        ).select_related('idMateria', 'idCategoria').order_by('-created_at')

        if universidad_id:
            qs = qs.filter(idUniversidad_id=universidad_id)

        estado = self.request.GET.get('estado')
        if estado in ('publicado', 'borrador', 'archivado'):
            qs = qs.filter(estado=estado)

        q = self.request.GET.get('q', '').strip()
        if q:
            qs = qs.filter(
                Q(titulo__icontains=q) |
                Q(autor__icontains=q) |
                Q(palabras_clave__icontains=q)
            )
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        u = self.request.user
        universidad_id = _get_universidad_id(u)

        base = RecursoBiblioteca.objects.filter(subido_por=u)
        if universidad_id:
            base = base.filter(idUniversidad_id=universidad_id)

        agregados = base.aggregate(
            vistas=Sum('total_vistas'),
            descargas=Sum('total_descargas'),
            promedio=Avg('promedio_calificacion'),
        )

        ctx['stats'] = {
            'total': base.count(),
            'publicados': base.filter(estado='publicado').count(),
            'borradores': base.filter(estado='borrador').count(),
            'archivados': base.filter(estado='archivado').count(),
            'vistas_totales': agregados['vistas'] or 0,
            'descargas_totales': agregados['descargas'] or 0,
            'promedio_general': agregados['promedio'] or 0,
        }
        ctx['q'] = self.request.GET.get('q', '')
        return ctx


# ============================================
# DESCARGA CONTROLADA
# ============================================

@login_required
def descargar_recurso(request, pk):
    """Filtra por universidad."""
    u = request.user
    universidad_id = _get_universidad_id(u)

    qs = RecursoBiblioteca.objects.filter(pk=pk, estado='publicado')
    if universidad_id:
        qs = qs.filter(idUniversidad_id=universidad_id)

    recurso = get_object_or_404(qs)

    if not recurso.archivo:
        messages.error(request, "Este recurso no tiene archivo descargable.")
        return redirect('biblioteca:detalle', pk=pk)

    if hasattr(request.user, 'estudiante'):
        BibliotecaService.registrar_acceso(
            estudiante=request.user.estudiante,
            recurso=recurso,
            accion='descarga',
            request=request,
        )

    try:
        response = FileResponse(recurso.archivo.open('rb'))
        filename = recurso.archivo.name.split('/')[-1]
        content_type, _ = mimetypes.guess_type(filename)
        response['Content-Type'] = content_type or 'application/octet-stream'
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response
    except FileNotFoundError:
        raise Http404("Archivo no encontrado.")


# ============================================
# MARCAR LECTURA COMPLETA / FAVORITO (AJAX)
# ============================================

@login_required
def marcar_lectura_completa(request, pk):
    """Filtra por universidad."""
    if request.method != 'POST':
        return JsonResponse({'error': 'Método no permitido'}, status=405)

    u = request.user
    universidad_id = _get_universidad_id(u)

    qs = RecursoBiblioteca.objects.all()
    if universidad_id:
        qs = qs.filter(idUniversidad_id=universidad_id)

    recurso = get_object_or_404(qs, pk=pk)

    if not hasattr(request.user, 'estudiante'):
        return JsonResponse({'error': 'Solo estudiantes'}, status=403)

    tiempo = int(request.POST.get('tiempo', 0))
    BibliotecaService.registrar_acceso(
        estudiante=request.user.estudiante,
        recurso=recurso,
        accion='lectura_completa',
        request=request,
        tiempo_lectura=tiempo,
    )
    return JsonResponse({'ok': True})


@login_required
def marcar_favorito(request, pk):
    """Filtra por universidad."""
    if request.method != 'POST':
        return JsonResponse({'error': 'Método no permitido'}, status=405)

    u = request.user
    universidad_id = _get_universidad_id(u)

    qs = RecursoBiblioteca.objects.all()
    if universidad_id:
        qs = qs.filter(idUniversidad_id=universidad_id)

    recurso = get_object_or_404(qs, pk=pk)

    if not hasattr(request.user, 'estudiante'):
        return JsonResponse({'error': 'Solo estudiantes'}, status=403)

    BibliotecaService.registrar_acceso(
        estudiante=request.user.estudiante,
        recurso=recurso,
        accion='favorito',
        request=request,
    )
    return JsonResponse({'ok': True})


@login_required
def cambiar_estado_recurso(request, pk):
    """Cambia el estado de un recurso vía AJAX. Filtra por universidad."""
    if request.method != 'POST':
        return JsonResponse({'error': 'Método no permitido'}, status=405)

    u = request.user
    universidad_id = _get_universidad_id(u)

    qs = RecursoBiblioteca.objects.all()
    if universidad_id:
        qs = qs.filter(idUniversidad_id=universidad_id)

    recurso = get_object_or_404(qs, pk=pk)

    if not (u.is_staff or u.rol == 'admin' or recurso.subido_por == u):
        return JsonResponse({'error': 'Sin permisos'}, status=403)

    nuevo_estado = request.POST.get('estado')
    if nuevo_estado not in ('publicado', 'borrador', 'archivado'):
        return JsonResponse({'error': 'Estado inválido'}, status=400)

    recurso.estado = nuevo_estado
    recurso.save(update_fields=['estado', 'updated_at'])
    return JsonResponse({'ok': True, 'estado': nuevo_estado})


@login_required
def eliminar_recurso(request, pk):
    """Elimina un recurso vía AJAX. Filtra por universidad."""
    if request.method != 'POST':
        return JsonResponse({'error': 'Método no permitido'}, status=405)

    u = request.user
    universidad_id = _get_universidad_id(u)

    qs = RecursoBiblioteca.objects.all()
    if universidad_id:
        qs = qs.filter(idUniversidad_id=universidad_id)

    recurso = get_object_or_404(qs, pk=pk)

    if not (u.is_staff or u.rol == 'admin' or recurso.subido_por == u):
        return JsonResponse({'error': 'Sin permisos'}, status=403)

    try:
        if recurso.archivo:
            recurso.archivo.delete(save=False)
        if recurso.portada:
            recurso.portada.delete(save=False)
    except Exception:
        pass

    recurso.delete()
    return JsonResponse({'ok': True})


# ============================================
# MATERIAL DE APOYO
# ============================================

class ListaMaterialApoyoView(LoginRequiredMixin, ListView):
    model = MaterialApoyo
    template_name = 'biblioteca/material_apoyo.html'
    context_object_name = 'materiales'
    paginate_by = 24

    def get_queryset(self):
        u = self.request.user
        qs = MaterialApoyo.objects.filter(activo=True).select_related(
            'idFactorRiesgo', 'creado_por'
        )

        # ✅ Aislamiento por universidad
        if u.is_superuser:
            pass  # superuser ve todo
        elif u.idUniversidad_id:
            qs = qs.filter(idUniversidad_id=u.idUniversidad_id)
        else:
            qs = qs.filter(idUniversidad__isnull=True)

        tipo = self.request.GET.get('tipo')
        tipos_validos = [t[0] for t in MaterialApoyo.TIPO_CHOICES]
        if tipo in tipos_validos:
            qs = qs.filter(tipo=tipo)

        return qs.order_by('tipo', 'titulo')

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        u = self.request.user

        base = MaterialApoyo.objects.filter(activo=True)
        if not u.is_superuser and u.idUniversidad_id:
            base = base.filter(idUniversidad_id=u.idUniversidad_id)

        conteos = {}
        for value, _ in MaterialApoyo.TIPO_CHOICES:
            conteos[value] = base.filter(tipo=value).count()

        ctx['tipos'] = MaterialApoyo.TIPO_CHOICES
        ctx['total_materiales'] = base.count()
        ctx['total_por_tipo'] = conteos
        return ctx


class CrearMaterialApoyoView(PuedeGestionarApoyoMixin, CreateView):
    model = MaterialApoyo
    form_class = MaterialApoyoForm
    template_name = 'biblioteca/crear_material_apoyo.html'
    success_url = reverse_lazy('biblioteca:material_apoyo')

    def get_form_kwargs(self):
        kw = super().get_form_kwargs()
        kw['user'] = self.request.user
        return kw

    def form_valid(self, form):
        material = form.save(commit=False)
        material.creado_por = self.request.user

        u = self.request.user
        if not u.is_superuser:
            if not u.idUniversidad_id:
                messages.error(self.request, "No tienes universidad asignada.")
                return redirect('biblioteca:material_apoyo')
            material.idUniversidad = u.idUniversidad

        material.save()
        messages.success(self.request, f"Material '{material.titulo}' creado correctamente.")
        return redirect(self.success_url)


class EditarMaterialApoyoView(PuedeGestionarApoyoMixin, UpdateView):
    model = MaterialApoyo
    form_class = MaterialApoyoForm
    template_name = 'biblioteca/crear_material_apoyo.html'
    success_url = reverse_lazy('biblioteca:material_apoyo')

    def get_queryset(self):
        """Filtra por universidad."""
        qs = super().get_queryset()
        u = self.request.user
        universidad_id = _get_universidad_id(u)

        if universidad_id:
            qs = qs.filter(idUniversidad_id=universidad_id)

        if u.is_staff or u.rol == 'admin':
            return qs
        return qs.filter(creado_por=u)

    def get_form_kwargs(self):
        kw = super().get_form_kwargs()
        kw['user'] = self.request.user
        return kw

    def form_valid(self, form):
        messages.success(self.request, "Material actualizado correctamente.")
        return super().form_valid(form)


# ============================================
# RECOMENDACIONES PERSONALIZADAS
# ============================================

@login_required
def mis_recomendaciones(request):
    """
    Vista personalizada para el estudiante: muestra material de apoyo
    según sus factores de riesgo activos + recursos académicos de sus
    materias críticas.
    """
    if not hasattr(request.user, 'estudiante'):
        messages.error(request, "Solo estudiantes pueden ver recomendaciones personalizadas.")
        return redirect('biblioteca:lista')

    estudiante = request.user.estudiante
    universidad_id = estudiante.idUniversidad_id

    # ============================================
    # 1. FACTORES DE RIESGO ACTIVOS
    # ============================================
    from core.models import RiesgoEstudiante
    riesgos_activos = RiesgoEstudiante.objects.filter(
        idEstudiante=estudiante,
        estado__in=['Activo', 'En seguimiento']
    ).select_related('idFactor').order_by('-nivel', '-fecha_deteccion')

    # ============================================
    # 2. MATERIAL DE APOYO POR FACTOR DE RIESGO
    # ============================================
    materiales_por_factor = []
    materiales_vistos_ids = set()

    for riesgo in riesgos_activos:
        materiales = MaterialApoyo.objects.filter(
            activo=True,
            idFactorRiesgo=riesgo.idFactor
        ).filter(
            Q(idUniversidad_id=universidad_id) | Q(idUniversidad__isnull=True)
        ).exclude(
            pk__in=materiales_vistos_ids
        ).select_related('creado_por')[:4]

        if not materiales:
            materiales = MaterialApoyo.objects.filter(
                activo=True,
                idUniversidad_id=universidad_id
            ).exclude(
                pk__in=materiales_vistos_ids
            ).order_by('-created_at')[:3]

        materiales_lista = list(materiales)
        materiales_vistos_ids.update(m.pk for m in materiales_lista)

        if materiales_lista:
            materiales_por_factor.append({
                'riesgo': riesgo,
                'factor': riesgo.idFactor,
                'nivel': riesgo.nivel,
                'materiales': materiales_lista,
            })

    # ============================================
    # 3. MATERIAS CRÍTICAS Y RECURSOS ACADÉMICOS
    # ============================================
    materias_criticas_ids = HistorialAcademico.objects.filter(
        idEstudiante=estudiante,
        estado_materia__in=['Reprobada', 'Cursando']
    ).values_list('idMateria_id', flat=True).distinct()[:4]

    materias_criticas = CatalogoMateria.objects.filter(
        idMateria__in=materias_criticas_ids
    ).annotate(
        total_recursos=Count(
            'recursos_biblioteca',
            filter=Q(recursos_biblioteca__estado='publicado')
        )
    )[:4]

    recursos_academicos = RecursoBiblioteca.objects.filter(
        estado='publicado',
        idMateria_id__in=materias_criticas_ids,
        idUniversidad_id=universidad_id
    ).select_related('idMateria', 'idCategoria').order_by(
        '-destacado', '-total_descargas', '-total_vistas'
    )[:8]

    # ============================================
    # 4. RECURSOS DESTACADOS / POPULARES
    # ============================================
    recursos_populares = RecursoBiblioteca.objects.filter(
        estado='publicado',
        idUniversidad_id=universidad_id
    ).exclude(
        pk__in=[r.pk for r in recursos_academicos]
    ).order_by('-total_vistas', '-total_descargas')[:4]

    # ============================================
    # 5. MÉTRICAS DE USO
    # ============================================
    metricas = BibliotecaService.resumen_actividad(estudiante, dias=30)

    desde_semana = timezone.now() - timedelta(days=7)
    lecturas_semana = AccesoRecurso.objects.filter(
        idEstudiante=estudiante,
        created_at__gte=desde_semana,
        accion__in=['vista', 'descarga', 'lectura_completa']
    ).count()

    # ============================================
    # 6. ESTADO GENERAL
    # ============================================
    total_riesgos = riesgos_activos.count()

    if total_riesgos == 0:
        estado_general = {
            'tipo': 'success',
            'mensaje': '¡Vas muy bien! No tienes factores de riesgo activos.',
            'icono': 'bi-emoji-smile-fill',
        }
    elif total_riesgos <= 2:
        estado_general = {
            'tipo': 'info',
            'mensaje': 'Tienes algunas señales que podemos ayudarte a mejorar.',
            'icono': 'bi-info-circle-fill',
        }
    else:
        estado_general = {
            'tipo': 'warning',
            'mensaje': 'Queremos apoyarte. Aquí tienes recursos que te pueden ayudar.',
            'icono': 'bi-heart-fill',
        }

    contexto = {
        'estudiante': estudiante,
        'riesgos_activos': riesgos_activos,
        'total_riesgos': total_riesgos,
        'materiales_por_factor': materiales_por_factor,
        'materias_criticas': materias_criticas,
        'recursos_academicos': recursos_academicos,
        'recursos_populares': recursos_populares,
        'metricas': metricas,
        'lecturas_semana': lecturas_semana,
        'estado_general': estado_general,
    }
    return render(request, 'biblioteca/mis_recomendaciones.html', contexto)