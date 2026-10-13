# core/forms.py
# ✅ VERSIÓN COMPLETA Y CORREGIDA

from django import forms
from django.contrib.auth.forms import UserCreationForm, UserChangeForm
from django.contrib.auth.hashers import make_password
from django.conf import settings
import logging


# ✅ CAMBIO: BecaEstudiante → Beca, BecaAsignacion
from .models import (
    Estudiante,
    HistorialAcademico,
    Asistencia,
    Beca,
    BecaAsignacion,
    Usuario,
    CatalogoCarrera,
    CatalogoAula,
    CatalogoTipoBeca,
    CatalogoFactorRiesgo,
    CatalogoUniversidad,
    CatalogoMateria,
    ConfiguracionSistema,
)
from .utils import (
    generar_password_temporal,
    generar_username_desde_nombre,
    logger
)


# ============================================
# FORMULARIO PARA USUARIO (CREACIÓN)
# ============================================

class UsuarioForm(UserCreationForm):
    """Formulario para crear/editar usuarios"""
    
    ROL_CHOICES = [
        ('admin', 'Administrador'),
        ('tutor', 'Tutor'),
        ('profesor', 'Profesor'),
        ('estudiante', 'Estudiante'),
    ]
    
    GENERO_CHOICES = [
        ('', 'Selecciona...'),
        ('M', 'Masculino'),
        ('F', 'Femenino'),
        ('Otro', 'Otro'),
    ]
    
    rol = forms.ChoiceField(choices=ROL_CHOICES, required=True)
    genero = forms.ChoiceField(choices=GENERO_CHOICES, required=False)
    carnet = forms.CharField(max_length=20, required=True, label='Carnet')
    telefono = forms.CharField(max_length=20, required=False)
    fecha_nacimiento = forms.DateField(required=False, widget=forms.DateInput(attrs={'type': 'date'}))
    idUniversidad = forms.ModelChoiceField(
        queryset=CatalogoUniversidad.objects.all(),
        required=False,
        label='Universidad'
    )
    
    class Meta:
        model = Usuario
        fields = [
            'username',
            'first_name',
            'last_name',
            'email',
            'carnet',
            'genero',
            'telefono',
            'fecha_nacimiento',
            'rol',
            'idUniversidad',
            'password1',
            'password2',
        ]
        labels = {
            'username': 'Nombre de usuario',
            'first_name': 'Nombre',
            'last_name': 'Apellidos',
            'email': 'Correo electrónico',
            'password1': 'Contraseña',
            'password2': 'Confirmar contraseña',
        }
    
    def clean_carnet(self):
        carnet = self.cleaned_data.get('carnet')
        if carnet and Usuario.objects.filter(carnet=carnet).exclude(pk=self.instance.pk).exists():
            raise forms.ValidationError('Este carnet ya está registrado.')
        return carnet
    
    def clean_email(self):
        email = self.cleaned_data.get('email')
        if email and Usuario.objects.filter(email=email).exclude(pk=self.instance.pk).exists():
            raise forms.ValidationError('Este email ya está registrado.')
        return email


# ============================================
# FORMULARIO PARA ESTUDIANTE
# ============================================

class EstudianteForm(forms.ModelForm):
    """Formulario para crear/editar estudiantes"""
    
    # Campos del usuario
    first_name = forms.CharField(max_length=150, required=True, label='Nombre')
    last_name = forms.CharField(max_length=150, required=True, label='Apellidos')
    email = forms.EmailField(required=True, label='Correo electrónico')
    carnet = forms.CharField(max_length=20, required=True, label='Carnet')
    genero = forms.ChoiceField(
        choices=[('', 'Selecciona...'), ('M', 'Masculino'), ('F', 'Femenino'), ('Otro', 'Otro')],
        required=False,
        label='Género'
    )
    telefono = forms.CharField(max_length=20, required=False, label='Teléfono')
    
    fecha_nacimiento = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
        label='Fecha de nacimiento',
        input_formats=['%Y-%m-%d', '%d/%m/%Y', '%m/%d/%Y']
    )
    
    foto = forms.ImageField(
        required=False,
        label='Foto del estudiante',
        widget=forms.ClearableFileInput(attrs={
            'class': 'form-control',
            'accept': 'image/*'
        })
    )
    
    foto_eliminar = forms.BooleanField(
        required=False,
        widget=forms.HiddenInput(),
        initial=False
    )
    
    generar_password_auto = forms.BooleanField(
        required=False,
        initial=True,
        label='Generar contraseña automáticamente',
        widget=forms.CheckboxInput(attrs={
            'class': 'form-check-input',
            'id': 'generar_password_auto',
            'onchange': 'togglePasswordFields(this)'
        })
    )
    
    password = forms.CharField(
        required=False,
        label='Contraseña',
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'id': 'password_manual',
            'placeholder': 'Escribe una contraseña...',
            'minlength': '6'
        }),
        help_text='Mínimo 6 caracteres. Solo si deseas establecer una contraseña manual.'
    )
    
    confirm_password = forms.CharField(
        required=False,
        label='Confirmar contraseña',
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'id': 'confirm_password',
            'placeholder': 'Repite la contraseña...'
        }),
        help_text='Repite la contraseña para confirmar.'
    )
    
    class Meta:
        model = Estudiante
        fields = [
            'idCarrera',
            'ano_ingreso',
            'semestre_actual',
            'estado_academico',
            'direccion',
            'telefono_emergencia',
            'contacto_emergencia_nombre',
            'nacionalidad',
            'foto',
        ]
        labels = {
            'idCarrera': 'Carrera',
            'ano_ingreso': 'Año de ingreso',
            'semestre_actual': 'Semestre actual',
            'estado_academico': 'Estado académico',
            'direccion': 'Dirección',
            'telefono_emergencia': 'Teléfono de emergencia',
            'contacto_emergencia_nombre': 'Contacto de emergencia',
            'nacionalidad': 'Nacionalidad',
            'foto': 'Fotografía',
        }
        widgets = {
            'ano_ingreso': forms.NumberInput(attrs={'min': 2000, 'max': 2030, 'class': 'form-control'}),
            'semestre_actual': forms.NumberInput(attrs={'min': 1, 'max': 20, 'class': 'form-control'}),
            'direccion': forms.Textarea(attrs={'rows': 2, 'class': 'form-control'}),
            'estado_academico': forms.Select(attrs={'class': 'form-select'}),
            'idCarrera': forms.Select(attrs={'class': 'form-select'}),
            'telefono_emergencia': forms.TextInput(attrs={'class': 'form-control'}),
            'contacto_emergencia_nombre': forms.TextInput(attrs={'class': 'form-control'}),
            'nacionalidad': forms.TextInput(attrs={'class': 'form-control'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        es_edicion = self.instance and self.instance.pk and self.instance.idUsuario
        
        if es_edicion:
            usuario = self.instance.idUsuario
            if usuario:
                self.fields['first_name'].initial = usuario.first_name
                self.fields['last_name'].initial = usuario.last_name
                self.fields['email'].initial = usuario.email
                self.fields['carnet'].initial = usuario.carnet
                self.fields['genero'].initial = usuario.genero
                self.fields['telefono'].initial = usuario.telefono
                
                if usuario.fecha_nacimiento:
                    self.fields['fecha_nacimiento'].initial = usuario.fecha_nacimiento.strftime('%Y-%m-%d')
            
            self.fields['generar_password_auto'].widget = forms.HiddenInput()
            self.fields['password'].widget = forms.HiddenInput()
            self.fields['confirm_password'].widget = forms.HiddenInput()
            self.fields['password'].required = False
            self.fields['confirm_password'].required = False
            self.fields['password'].help_text = None
            self.fields['confirm_password'].help_text = None
        else:
            self.fields['generar_password_auto'].initial = True
            self.fields['password'].required = False
            self.fields['confirm_password'].required = False
        
        self.fields['idCarrera'].queryset = CatalogoCarrera.objects.select_related('idUniversidad')
        self.fields['idCarrera'].label_from_instance = lambda obj: f"{obj.nombre} ({obj.idUniversidad.nombre})"
    
    def clean(self):
        cleaned_data = super().clean()
        
        carrera = cleaned_data.get('idCarrera')
        if carrera and not carrera.idUniversidad:
            raise forms.ValidationError(
                'La carrera seleccionada no tiene una universidad asociada.'
            )
        
        if not (self.instance and self.instance.pk):
            generar_auto = cleaned_data.get('generar_password_auto')
            password = cleaned_data.get('password')
            confirm_password = cleaned_data.get('confirm_password')
            
            if not generar_auto:
                if not password:
                    self.add_error('password', 'Debes escribir una contraseña.')
                elif len(password) < 6:
                    self.add_error('password', 'La contraseña debe tener al menos 6 caracteres.')
                elif password != confirm_password:
                    self.add_error('confirm_password', 'Las contraseñas no coinciden.')
        
        return cleaned_data
    
    def clean_fecha_nacimiento(self):
        fecha = self.cleaned_data.get('fecha_nacimiento')
        if not fecha:
            return None
        from datetime import date
        if fecha > date.today():
            raise forms.ValidationError('La fecha de nacimiento no puede ser futura.')
        return fecha
    
    def clean_foto(self):
        foto = self.cleaned_data.get('foto')
        foto_eliminar = self.cleaned_data.get('foto_eliminar', False)
        
        if foto_eliminar:
            return None
        
        if foto:
            if foto.size > 5 * 1024 * 1024:
                raise forms.ValidationError('La imagen no puede superar los 5MB.')
            import os
            ext = os.path.splitext(foto.name)[1].lower()
            if ext not in ['.jpg', '.jpeg', '.png', '.gif']:
                raise forms.ValidationError('Solo se permiten archivos JPG, PNG o GIF.')
        return foto
    
    def clean_carnet(self):
        carnet = self.cleaned_data.get('carnet')
        if carnet:
            existing = Usuario.objects.filter(carnet=carnet)
            if self.instance and self.instance.pk and self.instance.idUsuario:
                existing = existing.exclude(pk=self.instance.idUsuario.pk)
            if existing.exists():
                raise forms.ValidationError('Este carnet ya está registrado.')
        return carnet
    
    def clean_email(self):
        email = self.cleaned_data.get('email')
        if email:
            existing = Usuario.objects.filter(email=email)
            if self.instance and self.instance.pk and self.instance.idUsuario:
                existing = existing.exclude(pk=self.instance.idUsuario.pk)
            if existing.exists():
                raise forms.ValidationError('Este email ya está registrado.')
        return email
    
    def save(self, commit=True, request=None):
        """
        Guarda el estudiante y crea/actualiza el usuario asociado.
        
        IMPORTANTE:
        - La contraseña se guarda con set_password() UNA SOLA VEZ
        - La MISMA contraseña que se guarda es la que se envía por correo
        """
        logger.info("🔵 Iniciando save() en EstudianteForm")
        
        # Obtener el estudiante sin guardar
        estudiante = super().save(commit=False)
        es_nuevo = not (self.instance and self.instance.pk)
        
        logger.info(f"¿Es nuevo? {es_nuevo}")
        
        # ---- 1. Crear o recuperar el usuario ----
        if es_nuevo:
            usuario = Usuario()
            logger.info("✅ Nuevo usuario creado (instancia vacía)")
        else:
            usuario = estudiante.idUsuario
            if not usuario:
                usuario = Usuario()
                logger.info("✅ Usuario creado para estudiante existente sin usuario")
            else:
                logger.info(f"✅ Usuario existente: {usuario.username}")
        
        # ---- 2. Asignar datos al usuario ----
        usuario.first_name = self.cleaned_data.get('first_name', '')
        usuario.last_name = self.cleaned_data.get('last_name', '')
        usuario.email = self.cleaned_data.get('email', '')
        usuario.carnet = self.cleaned_data.get('carnet', '')
        usuario.genero = self.cleaned_data.get('genero') or None
        usuario.telefono = self.cleaned_data.get('telefono') or ''
        usuario.fecha_nacimiento = self.cleaned_data.get('fecha_nacimiento') or None
        
        # ---- 3. Asignar universidad ----
        carrera = self.cleaned_data.get('idCarrera')
        if carrera and carrera.idUniversidad:
            usuario.idUniversidad = carrera.idUniversidad
        elif request and hasattr(request.user, 'idUniversidad') and request.user.idUniversidad:
            usuario.idUniversidad = request.user.idUniversidad
        else:
            universidad_default = CatalogoUniversidad.objects.first()
            if not universidad_default:
                universidad_default = CatalogoUniversidad.objects.create(
                    nombre="Universidad Tecnológica",
                    tipo="Privada",
                    pais="Bolivia",
                    ciudad="La Paz"
                )
            usuario.idUniversidad = universidad_default
            logger.warning(f"⚠️ Universidad por defecto asignada: {universidad_default.nombre}")
        
        # ---- 4. Manejar foto ----
        foto = self.cleaned_data.get('foto')
        foto_eliminar = self.cleaned_data.get('foto_eliminar', False)
        if foto_eliminar:
            if usuario.foto:
                try:
                    usuario.foto.delete(save=False)
                except Exception:
                    pass
                usuario.foto = None
        elif foto:
            if usuario.foto:
                try:
                    usuario.foto.delete(save=False)
                except Exception:
                    pass
            usuario.foto = foto
        
        # ---- 5. Manejar contraseña y username (solo si es nuevo) ----
        password_para_enviar = None
        
        if es_nuevo:
            # ✅ GENERAR USERNAME desde nombre + apellido
            try:
                username = generar_username_desde_nombre(
                    self.cleaned_data.get('first_name', ''),
                    self.cleaned_data.get('last_name', '')
                )
                logger.info(f"✅ Username generado: {username}")
            except ValueError as e:
                # Fallback al carnet si no hay nombre/apellido válidos
                username_base = self.cleaned_data.get('carnet', '').lower() or 'estudiante'
                username = username_base
                counter = 1
                while Usuario.objects.filter(username=username).exists():
                    username = f"{username_base}{counter}"
                    counter += 1
                logger.warning(f"⚠️ Username generado desde carnet (fallback): {username}")
            
            usuario.username = username
            usuario.rol = 'estudiante'
            usuario.is_active = True
            
            # ✅ DECIDIR entre contraseña automática o manual
            generar_auto = self.cleaned_data.get('generar_password_auto', True)
            password_manual = self.cleaned_data.get('password', '').strip() if self.cleaned_data.get('password') else ''
            
            if generar_auto or not password_manual:
                # ✅ CONTRASEÑA AUTOMÁTICA
                password_final = generar_password_temporal()
                usuario.cambiar_password = True
                logger.info(f"🔑 Contraseña AUTOMÁTICA generada para @{username}")
            else:
                # ✅ CONTRASEÑA MANUAL
                password_final = password_manual
                usuario.cambiar_password = False
                logger.info(f"🔑 Contraseña MANUAL establecida para @{username}")
            
            # ⚠️ CRÍTICO: Hashear UNA SOLA VEZ
            usuario.set_password(password_final)
            password_para_enviar = password_final
        else:
            # Edición: mantener el username existente
            if not usuario.username:
                usuario.username = self.cleaned_data.get('carnet', '').lower()
        
        # ---- 6. Guardar usuario ----
        usuario.save()
        logger.info(f"✅ Usuario guardado: @{usuario.username} (ID: {usuario.id})")
        
        # ---- 7. Asignar usuario al estudiante ----
        estudiante.idUsuario = usuario
        estudiante.idUniversidad = usuario.idUniversidad
        
        # ---- 8. Asignar resto de campos al estudiante ----
        estudiante.direccion = self.cleaned_data.get('direccion') or None
        estudiante.nacionalidad = self.cleaned_data.get('nacionalidad') or 'Nacional'
        estudiante.telefono_emergencia = self.cleaned_data.get('telefono_emergencia') or None
        estudiante.contacto_emergencia_nombre = self.cleaned_data.get('contacto_emergencia_nombre') or None
        
        # ---- 9. Guardar estudiante ----
        if commit:
            estudiante.save()
            logger.info(f"✅ Estudiante guardado (ID: {estudiante.idEstudiante})")
        
        # ---- 10. Enviar credenciales por correo ----
        if es_nuevo and password_para_enviar and request:
            try:
                from .services.alert_service import AlertaService
                
                logger.info(f"📧 Enviando credenciales a {usuario.email}")
                
                resultado = AlertaService.notificar_credenciales(
                    usuario=usuario,
                    password_temporal=password_para_enviar,
                    es_primera_vez=True
                )
                
                if resultado:
                    logger.info(f"✅ Credenciales enviadas exitosamente a {usuario.email}")
                else:
                    logger.warning(f"⚠️ No se pudieron enviar credenciales a {usuario.email}")
            except Exception as e:
                logger.error(f"❌ Error enviando credenciales: {str(e)}", exc_info=True)
        
        logger.info("✅ Save() completado exitosamente")
        return estudiante


# ============================================
# FORMULARIO PARA HISTORIAL ACADÉMICO
# ============================================

class HistorialAcademicoForm(forms.ModelForm):
    """Formulario para agregar notas/historial académico"""
    
    class Meta:
        model = HistorialAcademico
        fields = [
            'idMateria',
            'semestre',
            'nota_final',
            'estado_materia',
            'intentos',
            'fecha_registro',
        ]
        labels = {
            'idMateria': 'Materia',
            'semestre': 'Semestre',
            'nota_final': 'Nota final',
            'estado_materia': 'Estado',
            'intentos': 'Intentos',
            'fecha_registro': 'Fecha de registro',
        }
        widgets = {
            'fecha_registro': forms.DateInput(attrs={'type': 'date'}),
        }


# ============================================
# FORMULARIO PARA ASISTENCIA
# ============================================

class AsistenciaForm(forms.ModelForm):
    """Formulario para registrar asistencia"""
    
    class Meta:
        model = Asistencia
        fields = [
            'idAula',
            'idMateria',
            'fecha',
            'hora_entrada',
            'hora_salida',
            'presente',
            'justificacion',
            'observaciones',
        ]
        labels = {
            'idAula': 'Aula',
            'idMateria': 'Materia',
            'fecha': 'Fecha',
            'hora_entrada': 'Hora de entrada',
            'hora_salida': 'Hora de salida',
            'presente': '¿Presente?',
            'justificacion': 'Justificación',
            'observaciones': 'Observaciones',
        }
        widgets = {
            'fecha': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'hora_entrada': forms.TimeInput(attrs={'type': 'time', 'class': 'form-control'}),
            'hora_salida': forms.TimeInput(attrs={'type': 'time', 'class': 'form-control'}),
            'idAula': forms.Select(attrs={'class': 'form-select'}),
            'idMateria': forms.Select(attrs={'class': 'form-select'}),
            'presente': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'justificacion': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Describe la justificación de la ausencia...'}),
            'observaciones': forms.Textarea(attrs={'class': 'form-control', 'rows': 2, 'placeholder': 'Observaciones adicionales...'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['idAula'].queryset = CatalogoAula.objects.all().order_by('codigo')
        self.fields['idAula'].empty_label = "Selecciona un aula"
        self.fields['idMateria'].queryset = CatalogoMateria.objects.all().order_by('nombre')
        self.fields['idMateria'].empty_label = "Selecciona una materia"
        self.fields['idMateria'].required = False
        self.fields['justificacion'].required = False
        self.fields['observaciones'].required = False


# ============================================
# ✅ FORMULARIO PARA BECAS (UNIFICADO)
# ============================================

class BecaAsignacionForm(forms.ModelForm):
    """
    Formulario unificado para asignar becas a estudiantes.
    Reemplaza a BecaEstudianteForm.
    """

    class Meta:
        model = BecaAsignacion
        fields = [
            'idBeca',
            'idEstudiante',
            'fecha_inicio',
            'fecha_fin',
            'estado',
            'monto_personalizado',
            'porcentaje_personalizado',
            'observaciones',
            'renovable',
        ]
        labels = {
            'idBeca': 'Beca',
            'idEstudiante': 'Estudiante',
            'fecha_inicio': 'Fecha de inicio',
            'fecha_fin': 'Fecha de fin',
            'estado': 'Estado',
            'monto_personalizado': 'Monto personalizado (opcional)',
            'porcentaje_personalizado': 'Porcentaje personalizado (opcional)',
            'observaciones': 'Observaciones',
            'renovable': '¿Es renovable?',
        }
        widgets = {
            'idBeca': forms.Select(attrs={'class': 'form-select'}),
            'idEstudiante': forms.Select(attrs={'class': 'form-select'}),
            'fecha_inicio': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'fecha_fin': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'estado': forms.Select(attrs={'class': 'form-select'}),
            'monto_personalizado': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'placeholder': 'Vacío = usar monto de la beca'}),
            'porcentaje_personalizado': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'placeholder': 'Vacío = usar porcentaje de la beca'}),
            'observaciones': forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
            'renovable': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
        help_texts = {
            'monto_personalizado': 'Si lo dejas vacío, se usa el monto de la beca.',
            'porcentaje_personalizado': 'Si lo dejas vacío, se usa el porcentaje de la beca.',
        }

    def clean(self):
        cleaned_data = super().clean()
        fecha_inicio = cleaned_data.get('fecha_inicio')
        fecha_fin = cleaned_data.get('fecha_fin')

        if fecha_inicio and fecha_fin and fecha_fin <= fecha_inicio:
            raise forms.ValidationError(
                "La fecha de fin debe ser posterior a la fecha de inicio."
            )

        idBeca = cleaned_data.get('idBeca')
        idEstudiante = cleaned_data.get('idEstudiante')

        # Verificar que no exista ya una asignación para este par
        if idBeca and idEstudiante:
            existe = BecaAsignacion.objects.filter(
                idBeca=idBeca,
                idEstudiante=idEstudiante
            )
            if self.instance.pk:
                existe = existe.exclude(pk=self.instance.pk)
            if existe.exists():
                raise forms.ValidationError(
                    "Este estudiante ya tiene una asignación para esta beca."
                )

        return cleaned_data


# ============================================
# FORMULARIO PARA CARGA MASIVA
# ============================================

class CargaMasivaEstudiantesForm(forms.Form):
    """Formulario para carga masiva de estudiantes desde Excel"""
    
    archivo = forms.FileField(
        label='Archivo Excel',
        help_text='Sube un archivo .xlsx o .xls con los datos de los estudiantes'
    )
    opcion_crear_usuarios = forms.BooleanField(
        required=False,
        initial=True,
        label='Crear usuarios automáticamente',
        help_text='Crea un usuario para cada estudiante con su carnet como username'
    )
    opcion_actualizar = forms.BooleanField(
        required=False,
        initial=True,
        label='Actualizar existentes',
        help_text='Actualiza los datos de estudiantes que ya existen por carnet'
    )
    
    def clean_archivo(self):
        archivo = self.cleaned_data.get('archivo')
        if archivo:
            extension = archivo.name.split('.')[-1].lower()
            if extension not in ['xlsx', 'xls']:
                raise forms.ValidationError('El archivo debe ser .xlsx o .xls')
        return archivo


# ============================================
# FORMULARIO PARA FACTORES DE RIESGO
# ============================================

class FactorRiesgoForm(forms.ModelForm):
    """Formulario para crear/editar factores de riesgo"""
    
    class Meta:
        model = CatalogoFactorRiesgo
        fields = ['nombre', 'peso', 'descripcion', 'activo']
        labels = {
            'nombre': 'Nombre',
            'peso': 'Peso',
            'descripcion': 'Descripción',
            'activo': 'Activo',
        }


# ============================================
# FORMULARIO PARA CONFIGURACIÓN DEL SISTEMA
# ============================================

class ConfiguracionSistemaForm(forms.ModelForm):
    """Formulario unificado para configuración del sistema"""
    
    class Meta:
        model = ConfiguracionSistema
        fields = [
            'sitio_nombre',
            'sitio_url',
            'sitio_descripcion',
            'sitio_logo',
            'sitio_favicon',
            'nombre_completo',
            'siglas',
            'telefono',
            'email_contacto',
            'direccion',
            'sitio_web',
            'fecha_fundacion',
            'rector',
            'mision',
            'vision',
            'valores',
            'email_host',
            'email_port',
            'email_use_tls',
            'email_host_user',
            'email_host_password',
            'email_from',
            'email_test_recipient',
            'twilio_enabled',
            'twilio_account_sid',
            'twilio_auth_token',
            'twilio_whatsapp_number',
            'session_timeout_minutes',
            'session_expire_at_browser_close',
            'limite_intentos_login',
            'require_https',
            'allowed_hosts',
            'mante_sistema',
            'permite_registro',
            'notificaciones_email',
            'notificaciones_whatsapp',
            'color_primario',
            'color_secundario',
            'color_fondo',
            'mostrar_estadisticas',
            'cache_timeout',
            'cache_max_entries',
        ]
        widgets = {
            'sitio_descripcion': forms.Textarea(attrs={'rows': 2, 'class': 'form-control'}),
            'direccion': forms.Textarea(attrs={'rows': 2, 'class': 'form-control'}),
            'mision': forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
            'vision': forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
            'valores': forms.Textarea(attrs={'rows': 2, 'class': 'form-control'}),
            'allowed_hosts': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'localhost,127.0.0.1,dominio.com'}),
            'email_host_password': forms.PasswordInput(attrs={'class': 'form-control', 'render_value': True}),
            'twilio_auth_token': forms.PasswordInput(attrs={'class': 'form-control', 'render_value': True}),
            'sitio_logo': forms.FileInput(attrs={'class': 'form-control'}),
            'sitio_favicon': forms.FileInput(attrs={'class': 'form-control'}),
            'fecha_fundacion': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'color_primario': forms.TextInput(attrs={'type': 'color', 'class': 'form-control form-control-color', 'style': 'padding: 0.2rem; height: 50px;'}),
            'color_secundario': forms.TextInput(attrs={'type': 'color', 'class': 'form-control form-control-color', 'style': 'padding: 0.2rem; height: 50px;'}),
            'color_fondo': forms.TextInput(attrs={'type': 'color', 'class': 'form-control form-control-color', 'style': 'padding: 0.2rem; height: 50px;'}),
        }
    
    def clean_allowed_hosts(self):
        allowed_hosts = self.cleaned_data.get('allowed_hosts', '')
        hosts = [h.strip() for h in allowed_hosts.split(',') if h.strip()]
        if not hosts:
            raise forms.ValidationError('Debes especificar al menos un host permitido.')
        return allowed_hosts


# ============================================
# FORMULARIO UNIFICADO PARA CREAR/EDITAR USUARIOS
# ============================================

class UsuarioCreateForm(forms.ModelForm):
    """
    Formulario unificado para crear/editar usuarios (admin, tutor, profesor).
    Reutiliza la lógica de EstudianteForm para consistencia.
    """
    
    # ============================================
    # CAMPOS DEL USUARIO
    # ============================================
    first_name = forms.CharField(
        max_length=150, 
        required=True, 
        label='Nombre',
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej: Juan'})
    )
    last_name = forms.CharField(
        max_length=150, 
        required=True, 
        label='Apellidos',
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej: Pérez García'})
    )
    email = forms.EmailField(
        required=True, 
        label='Correo electrónico',
        widget=forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'Ej: jperez@email.com'})
    )
    carnet = forms.CharField(
        max_length=20, 
        required=False,
        label='Carnet',
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej: 2024-001'})
    )
    genero = forms.ChoiceField(
        choices=[('', 'Selecciona...'), ('M', 'Masculino'), ('F', 'Femenino'), ('Otro', 'Otro')],
        required=False,
        label='Género',
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    telefono = forms.CharField(
        max_length=20, 
        required=False, 
        label='Teléfono',
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej: 555-1234'})
    )
    whatsapp_telefono = forms.CharField(
        max_length=20,
        required=False,
        label='WhatsApp',
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej: +591 71234567'})
    )
    fecha_nacimiento = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
        label='Fecha de nacimiento',
        input_formats=['%Y-%m-%d', '%d/%m/%Y', '%m/%d/%Y']
    )
    
    rol = forms.ChoiceField(
        choices=[
            ('admin', 'Administrador'),
            ('tutor', 'Tutor'),
            ('profesor', 'Profesor'),
        ],
        required=True,
        label='Rol',
        widget=forms.Select(attrs={'class': 'form-select', 'id': 'rolSelect'})
    )
    
    foto = forms.ImageField(
        required=False,
        label='Fotografía',
        widget=forms.ClearableFileInput(attrs={
            'class': 'form-control',
            'accept': 'image/*'
        })
    )
    
    foto_eliminar = forms.BooleanField(
        required=False,
        widget=forms.HiddenInput(),
        initial=False
    )
    
    # ============================================
    # CAMPOS DE CONTRASEÑA
    # ============================================
    generar_password_auto = forms.BooleanField(
        required=False,
        initial=True,
        label='Generar contraseña automáticamente',
        widget=forms.CheckboxInput(attrs={
            'class': 'form-check-input',
            'id': 'generar_password_auto',
            'onchange': 'togglePasswordFields(this)'
        })
    )
    
    password = forms.CharField(
        required=False,
        label='Contraseña',
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'id': 'password_manual',
            'placeholder': 'Escribe una contraseña...',
            'minlength': '8'
        }),
        help_text='Mínimo 8 caracteres. Solo si deseas establecer una contraseña manual.'
    )
    
    confirm_password = forms.CharField(
        required=False,
        label='Confirmar contraseña',
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'id': 'confirm_password',
            'placeholder': 'Repite la contraseña...'
        }),
        help_text='Repite la contraseña para confirmar.'
    )
    
    # ============================================
    # CAMPOS ESPECÍFICOS PARA TUTOR
    # ============================================
    especialidad = forms.CharField(
        max_length=200,
        required=False,
        label='Especialidad',
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'id': 'especialidad',
            'placeholder': 'Ej: Matemáticas, Programación...'
        })
    )
    max_estudiantes = forms.IntegerField(
        required=False,
        initial=10,
        min_value=1,
        max_value=50,
        label='Máximo de estudiantes',
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'id': 'max_estudiantes',
            'min': 1,
            'max': 50
        })
    )
    tutor_activo = forms.BooleanField(
        required=False,
        initial=True,
        label='Tutor activo',
        widget=forms.CheckboxInput(attrs={
            'class': 'form-check-input',
            'id': 'tutor_activo'
        })
    )
    
    class Meta:
        model = Usuario
        fields = [
            'first_name',
            'last_name',
            'email',
            'carnet',
            'genero',
            'telefono',
            'whatsapp_telefono',
            'fecha_nacimiento',
            'rol',
            'foto',
        ]
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        es_edicion = self.instance and self.instance.pk
        
        if es_edicion:
            self.fields['first_name'].initial = self.instance.first_name
            self.fields['last_name'].initial = self.instance.last_name
            self.fields['email'].initial = self.instance.email
            self.fields['carnet'].initial = self.instance.carnet
            self.fields['genero'].initial = self.instance.genero
            self.fields['telefono'].initial = self.instance.telefono
            self.fields['whatsapp_telefono'].initial = self.instance.whatsapp_telefono
            
            if self.instance.fecha_nacimiento:
                self.fields['fecha_nacimiento'].initial = self.instance.fecha_nacimiento.strftime('%Y-%m-%d')
            
            if self.instance.rol == 'tutor':
                try:
                    from .models import Tutor
                    tutor = Tutor.objects.filter(usuario=self.instance).first()
                    if tutor:
                        self.fields['especialidad'].initial = tutor.especialidad
                        self.fields['max_estudiantes'].initial = tutor.max_estudiantes
                        self.fields['tutor_activo'].initial = tutor.activo
                except Exception:
                    pass
            
            self.fields['generar_password_auto'].widget = forms.HiddenInput()
            self.fields['password'].widget = forms.HiddenInput()
            self.fields['confirm_password'].widget = forms.HiddenInput()
            self.fields['password'].required = False
            self.fields['confirm_password'].required = False
            self.fields['password'].help_text = None
            self.fields['confirm_password'].help_text = None
            
            self.fields['rol'].widget = forms.HiddenInput()
            self.fields['rol'].initial = self.instance.rol
            self.fields['rol'].required = False
        else:
            self.fields['generar_password_auto'].initial = True
            self.fields['password'].required = False
            self.fields['confirm_password'].required = False
    
    def clean(self):
        cleaned_data = super().clean()
        
        es_edicion = self.instance and self.instance.pk
        
        if not es_edicion:
            rol = cleaned_data.get('rol')
            generar_auto = cleaned_data.get('generar_password_auto')
            password = cleaned_data.get('password')
            confirm_password = cleaned_data.get('confirm_password')
            
            if not generar_auto:
                if not password:
                    self.add_error('password', 'Debes escribir una contraseña.')
                elif len(password) < 8:
                    self.add_error('password', 'La contraseña debe tener al menos 8 caracteres.')
                elif password != confirm_password:
                    self.add_error('confirm_password', 'Las contraseñas no coinciden.')
            
            if rol == 'tutor':
                especialidad = cleaned_data.get('especialidad')
                max_estudiantes = cleaned_data.get('max_estudiantes')
                
                if not especialidad:
                    self.add_error('especialidad', 'La especialidad es obligatoria para tutores.')
                
                if max_estudiantes and (max_estudiantes < 1 or max_estudiantes > 50):
                    self.add_error('max_estudiantes', 'Debe ser entre 1 y 50.')
        
        return cleaned_data
    
    def clean_fecha_nacimiento(self):
        fecha = self.cleaned_data.get('fecha_nacimiento')
        if not fecha:
            return None
        from datetime import date
        if fecha > date.today():
            raise forms.ValidationError('La fecha de nacimiento no puede ser futura.')
        return fecha
    
    def clean_email(self):
        email = self.cleaned_data.get('email', '').lower()
        if email:
            existing = Usuario.objects.filter(email=email)
            if self.instance and self.instance.pk:
                existing = existing.exclude(pk=self.instance.pk)
            if existing.exists():
                raise forms.ValidationError('Este email ya está registrado.')
        return email
    
    def clean_carnet(self):
        carnet = self.cleaned_data.get('carnet')
        if carnet:
            existing = Usuario.objects.filter(carnet=carnet)
            if self.instance and self.instance.pk:
                existing = existing.exclude(pk=self.instance.pk)
            if existing.exists():
                raise forms.ValidationError('Este carnet ya está registrado.')
        return carnet
    
    def clean_foto(self):
        foto = self.cleaned_data.get('foto')
        foto_eliminar = self.cleaned_data.get('foto_eliminar', False)
        
        if foto_eliminar:
            return None
        
        if foto:
            if foto.size > 5 * 1024 * 1024:
                raise forms.ValidationError('La imagen no puede superar los 5MB.')
            import os
            ext = os.path.splitext(foto.name)[1].lower()
            if ext not in ['.jpg', '.jpeg', '.png', '.gif']:
                raise forms.ValidationError('Solo se permiten archivos JPG, PNG o GIF.')
        return foto
    
    def save(self, commit=True, request=None):
        """Guarda el usuario (crear o editar)."""
        logger.info("🔵 Iniciando save() en UsuarioCreateForm")
        
        usuario = super().save(commit=False)
        es_nuevo = not (self.instance and self.instance.pk)
        
        logger.info(f"¿Es nuevo? {es_nuevo}")
        
        # ============================================
        # DATOS BÁSICOS
        # ============================================
        usuario.first_name = self.cleaned_data.get('first_name', '')
        usuario.last_name = self.cleaned_data.get('last_name', '')
        usuario.email = self.cleaned_data.get('email', '').lower()
        usuario.carnet = self.cleaned_data.get('carnet') or None
        usuario.genero = self.cleaned_data.get('genero') or None
        usuario.telefono = self.cleaned_data.get('telefono') or None
        usuario.whatsapp_telefono = self.cleaned_data.get('whatsapp_telefono') or None
        usuario.fecha_nacimiento = self.cleaned_data.get('fecha_nacimiento') or None
        
        if es_nuevo:
            usuario.rol = self.cleaned_data.get('rol')
            usuario.is_active = True
        
        # ============================================
        # ASIGNAR UNIVERSIDAD
        # ============================================
        if request and hasattr(request.user, 'idUniversidad') and request.user.idUniversidad:
            usuario.idUniversidad = request.user.idUniversidad
        elif not usuario.idUniversidad:
            universidad_default = CatalogoUniversidad.objects.first()
            if not universidad_default:
                universidad_default = CatalogoUniversidad.objects.create(
                    nombre="Universidad Tecnológica",
                    tipo="Privada",
                    pais="Bolivia",
                    ciudad="La Paz"
                )
            usuario.idUniversidad = universidad_default
            logger.warning(f"⚠️ Universidad por defecto asignada: {universidad_default.nombre}")
        
        # ============================================
        # MANEJAR FOTO
        # ============================================
        foto = self.cleaned_data.get('foto')
        foto_eliminar = self.cleaned_data.get('foto_eliminar', False)
        if foto_eliminar:
            if usuario.foto:
                try:
                    usuario.foto.delete(save=False)
                except Exception:
                    pass
                usuario.foto = None
        elif foto:
            if usuario.foto:
                try:
                    usuario.foto.delete(save=False)
                except Exception:
                    pass
            usuario.foto = foto
        
        # ============================================
        # USERNAME Y CONTRASEÑA (SOLO SI ES NUEVO)
        # ============================================
        password_para_enviar = None
        
        if es_nuevo:
            try:
                username = generar_username_desde_nombre(
                    self.cleaned_data.get('first_name', ''),
                    self.cleaned_data.get('last_name', '')
                )
                logger.info(f"✅ Username generado: {username}")
            except ValueError as e:
                username_base = (
                    self.cleaned_data.get('carnet', '').lower() or 
                    self.cleaned_data.get('email', '').split('@')[0].lower() or 
                    'usuario'
                )
                username = username_base
                counter = 1
                while Usuario.objects.filter(username=username).exists():
                    username = f"{username_base}{counter}"
                    counter += 1
                logger.warning(f"⚠️ Username generado desde fallback: {username}")
            
            usuario.username = username
            
            generar_auto = self.cleaned_data.get('generar_password_auto', True)
            password_manual = self.cleaned_data.get('password', '').strip() if self.cleaned_data.get('password') else ''
            
            if generar_auto or not password_manual:
                password_final = generar_password_temporal()
                usuario.cambiar_password = True
                logger.info(f"🔑 Contraseña AUTOMÁTICA para @{username}")
            else:
                password_final = password_manual
                usuario.cambiar_password = False
                logger.info(f"🔑 Contraseña MANUAL para @{username}")
            
            usuario.set_password(password_final)
            password_para_enviar = password_final
        else:
            if not usuario.username:
                usuario.username = self.cleaned_data.get('email', '').split('@')[0].lower() or 'usuario'
        
        # ============================================
        # GUARDAR USUARIO
        # ============================================
        usuario.save()
        logger.info(f"✅ Usuario guardado: @{usuario.username} (ID: {usuario.id})")
        
        # ============================================
        # CREAR/ACTUALIZAR REGISTRO DE TUTOR SI APLICA
        # ============================================
        if usuario.rol == 'tutor':
            from .models import Tutor
            
            especialidad = self.cleaned_data.get('especialidad', '').strip()
            max_estudiantes = self.cleaned_data.get('max_estudiantes') or 10
            tutor_activo = self.cleaned_data.get('tutor_activo', True)
            
            Tutor.objects.update_or_create(
                usuario=usuario,
                defaults={
                    'especialidad': especialidad,
                    'max_estudiantes': int(max_estudiantes),
                    'activo': tutor_activo,
                }
            )
            logger.info(f"✅ Tutor creado/actualizado para @{usuario.username}")
        
        # ============================================
        # ENVIAR CREDENCIALES POR CORREO (SOLO SI ES NUEVO)
        # ============================================
        if es_nuevo and password_para_enviar and request:
            try:
                from .services.alert_service import AlertaService
                
                logger.info(f"📧 Enviando credenciales a {usuario.email}")
                
                resultado = AlertaService.notificar_credenciales(
                    usuario=usuario,
                    password_temporal=password_para_enviar,
                    es_primera_vez=True
                )
                
                if resultado:
                    logger.info(f"✅ Credenciales enviadas a {usuario.email}")
                else:
                    logger.warning(f"⚠️ No se pudieron enviar credenciales a {usuario.email}")
            except Exception as e:
                logger.error(f"❌ Error enviando credenciales: {str(e)}", exc_info=True)
        
        logger.info(f"✅ Save() completado para @{usuario.username}")
        return usuario