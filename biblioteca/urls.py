# biblioteca/urls.py
from django.urls import path
from . import views

app_name = 'biblioteca'

urlpatterns = [
    # Recursos
    path('', views.ListaRecursosView.as_view(), name='lista'),
    path('recurso/<int:pk>/', views.DetalleRecursoView.as_view(), name='detalle'),
    path('recurso/<int:pk>/descargar/', views.descargar_recurso, name='descargar'),
    path('recurso/<int:pk>/lectura-completa/', views.marcar_lectura_completa, name='lectura_completa'),
    path('recurso/<int:pk>/favorito/', views.marcar_favorito, name='favorito'),

    # Subida / edición
    path('subir/', views.SubirRecursoView.as_view(), name='subir'),
    path('recurso/<int:pk>/editar/', views.EditarRecursoView.as_view(), name='editar'),
    path('mis-recursos/', views.MisRecursosView.as_view(), name='mis_recursos'),
    path('recurso/<int:pk>/cambiar-estado/', views.cambiar_estado_recurso, name='cambiar_estado'),
    path('recurso/<int:pk>/eliminar/', views.eliminar_recurso, name='eliminar'),

    # Material de apoyo
    path('apoyo/', views.ListaMaterialApoyoView.as_view(), name='material_apoyo'),
    path('apoyo/crear/', views.CrearMaterialApoyoView.as_view(), name='crear_material_apoyo'),
    path('apoyo/<int:pk>/editar/', views.EditarMaterialApoyoView.as_view(), name='editar_material_apoyo'),
    path('recomendaciones/', views.mis_recomendaciones, name='mis_recomendaciones'),

    # Recomendaciones
    path('recomendaciones/', views.mis_recomendaciones, name='mis_recomendaciones'),
    



]