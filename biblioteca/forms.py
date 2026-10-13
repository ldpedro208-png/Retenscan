# biblioteca/forms.py
from django import forms
from django.conf import settings
from .models import RecursoBiblioteca, MaterialApoyo, CategoriaRecurso
from .utils.sanitizer import sanitizar_html, contiene_html_peligroso
import logging

logger = logging.getLogger(__name__)

class RecursoBibliotecaForm(forms.ModelForm):
    """Formulario para subir recursos por profesores/tutores."""

    class Meta:
        model = RecursoBiblioteca
        fields = [
            'titulo', 'autor', 'editorial', 'anio_publicacion', 'isbn',
            'idMateria', 'idCategoria', 'tipo', 'nivel_dificultad',
            'archivo', 'url_externa', 'portada',
            'descripcion', 'palabras_clave', 'idioma',
            'es_obligatorio', 'destacado', 'estado',
        ]
        widgets = {
            'titulo': forms.TextInput(attrs={'class': 'form-control'}),
            'autor': forms.TextInput(attrs={'class': 'form-control'}),
            'editorial': forms.TextInput(attrs={'class': 'form-control'}),
            'anio_publicacion': forms.NumberInput(attrs={'class': 'form-control', 'min': 1900, 'max': 2100}),
            'isbn': forms.TextInput(attrs={'class': 'form-control'}),
            'idMateria': forms.Select(attrs={'class': 'form-select'}),
            'idCategoria': forms.Select(attrs={'class': 'form-select'}),
            'tipo': forms.Select(attrs={'class': 'form-select'}),
            'nivel_dificultad': forms.Select(attrs={'class': 'form-select'}),
            'archivo': forms.ClearableFileInput(attrs={'class': 'form-control'}),
            'url_externa': forms.URLInput(attrs={'class': 'form-control'}),
            'portada': forms.ClearableFileInput(attrs={'class': 'form-control', 'accept': 'image/*'}),
            'descripcion': forms.Textarea(attrs={'class': 'form-control', 'rows': 4}),
            'palabras_clave': forms.TextInput(attrs={'class': 'form-control',
                                                     'placeholder': 'Ej: cálculo, derivadas, ejercicios'}),
            'idioma': forms.TextInput(attrs={'class': 'form-control'}),
            'estado': forms.Select(attrs={'class': 'form-select'}),
            'es_obligatorio': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'destacado': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)

        # Solo mostrar materias de la universidad del usuario
        from core.models import CatalogoMateria
        if self.user and self.user.idUniversidad:
            self.fields['idMateria'].queryset = CatalogoMateria.objects.filter(
                idCarrera__idUniversidad=self.user.idUniversidad
            ).order_by('nombre')
        else:
            self.fields['idMateria'].queryset = CatalogoMateria.objects.none()

        self.fields['idCategoria'].queryset = CategoriaRecurso.objects.filter(activo=True)
        self.fields['idMateria'].empty_label = "— Sin materia (transversal) —"
        self.fields['idCategoria'].empty_label = "— Selecciona categoría —"
        self.fields['idMateria'].required = False
        self.fields['autor'].required = False
        self.fields['editorial'].required = False
        self.fields['isbn'].required = False
        self.fields['anio_publicacion'].required = False
        self.fields['palabras_clave'].required = False
        self.fields['url_externa'].required = False
        self.fields['portada'].required = False

    def clean(self):
        cleaned = super().clean()
        archivo = cleaned.get('archivo')
        url = cleaned.get('url_externa')
        tipo = cleaned.get('tipo')

        # Debe tener archivo O url
        if not archivo and not url:
            raise forms.ValidationError(
                "Debes adjuntar un archivo o proporcionar una URL externa."
            )

        # Validar tamaño (20 MB máximo)
        if archivo and archivo.size > 20 * 1024 * 1024:
            self.add_error('archivo', 'El archivo no puede superar los 20MB.')

        # Validar extensiones
        if archivo:
            import os
            ext = os.path.splitext(archivo.name)[1].lower()
            permitidas = ['.pdf', '.epub', '.doc', '.docx', '.ppt', '.pptx',
                          '.xls', '.xlsx', '.mp4', '.mp3', '.zip']
            if ext not in permitidas:
                self.add_error('archivo', f'Extensión {ext} no permitida.')

        return cleaned


class MaterialApoyoForm(forms.ModelForm):
    """Formulario para material de apoyo (solo admin/tutores)."""

    class Meta:
        model = MaterialApoyo
        fields = ['titulo', 'tipo', 'descripcion', 'contenido',
                  'archivo', 'url_externa', 'idFactorRiesgo', 'activo']
        widgets = {
            'titulo': forms.TextInput(attrs={'class': 'form-control'}),
            'tipo': forms.Select(attrs={'class': 'form-select'}),
            'descripcion': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'contenido': forms.Textarea(attrs={'class': 'form-control', 'rows': 8}),
            'archivo': forms.ClearableFileInput(attrs={'class': 'form-control'}),
            'url_externa': forms.URLInput(attrs={'class': 'form-control'}),
            'idFactorRiesgo': forms.Select(attrs={'class': 'form-select'}),
            'activo': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)

        from core.models import CatalogoFactorRiesgo
        self.fields['idFactorRiesgo'].queryset = CatalogoFactorRiesgo.objects.filter(activo=True)
        self.fields['idFactorRiesgo'].empty_label = "— No mitigar ningún factor específico —"
        self.fields['idFactorRiesgo'].required = False
        self.fields['contenido'].required = False
        self.fields['archivo'].required = False
        self.fields['url_externa'].required = False

    def clean(self):
        cleaned = super().clean()
        contenido = cleaned.get('contenido')
        archivo = cleaned.get('archivo')
        url = cleaned.get('url_externa')

        if not (contenido or archivo or url):
            raise forms.ValidationError(
                "Debes proporcionar contenido, un archivo o una URL."
            )
        return cleaned

    
    def clean_contenido(self):
        contenido = self.cleaned_data.get('contenido', '')
        if not contenido:
            return ''

        # Log de intentos sospechosos
        if contiene_html_peligroso(contenido):
            logger.warning(
                f"[XSS-Intento] Usuario {getattr(self, 'user', None)} "
                f"intentó guardar HTML sospechoso en material de apoyo"
            )

        # Sanitizar (esta es la defensa real)
        return sanitizar_html(contenido)