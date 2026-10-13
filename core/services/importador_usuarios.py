# core/services/importador_usuarios.py

"""
Importador de usuarios (admin, tutor, profesor) desde archivos,
PostgreSQL, MySQL o API REST.

✅ Acepta fuente= (archivo, BD, API)
✅ Actualización selectiva: no sobrescribe con vacíos
✅ Normaliza rol
"""
from django.contrib.auth.hashers import make_password
from django.db import transaction
from django.db.models import Q

from ..models import Usuario, CatalogoUniversidad
from .importador_base import ImportadorBase
from ..utils import generar_password_temporal
from ..logging_config import logger
from .alert_service import AlertaService

class ImportadorUsuarios(ImportadorBase):
    """
    Importador de usuarios (admin, tutor, profesor, estudiante).

    Uso:
        # Desde archivo
        imp = ImportadorUsuarios(archivo=request.FILES['archivo'],
                                 universidad=u, usuario=request.user,
                                 actualizar_existentes=True)

        # Desde API
        fuente = FuenteAPI('https://api.edu/usuarios',
                           headers={'Authorization': 'Bearer XYZ'})
        imp = ImportadorUsuarios(fuente=fuente, universidad=u, usuario=request.user)
    """

    COLUMNAS_REQUERIDAS = ['username', 'email', 'nombre', 'apellido', 'rol']

    ROLES_VALIDOS = ['admin', 'tutor', 'profesor', 'estudiante']

    # Normalización de roles
    MAPA_ROLES = {
        'admin': 'admin', 'administrador': 'admin', 'administrator': 'admin',
        'tutor': 'tutor', 'tutoría': 'tutor', 'tutoria': 'tutor',
        'profesor': 'profesor', 'docente': 'profesor', 'teacher': 'profesor',
        'estudiante': 'estudiante', 'alumno': 'estudiante', 'student': 'estudiante',
    }

    def __init__(self, archivo=None, universidad=None, usuario=None,
                 actualizar_existentes=False, fuente=None):
        super().__init__(archivo=archivo, universidad=universidad,
                         usuario=usuario, fuente=fuente)
        self.actualizar_existentes = actualizar_existentes

    # ============================================
    # HELPERS
    # ============================================

    def _normalizar_rol(self, rol_raw):
        """Convierte el rol a su forma canónica."""
        if not rol_raw:
            return None
        clave = str(rol_raw).strip().lower()
        return self.MAPA_ROLES.get(clave)

    # ============================================
    # PROCESAMIENTO DE FILA
    # ============================================

    def procesar_fila(self, fila, indice):
        """Procesa una fila de usuarios."""

        # --- Lectura ---
        username = self.limpiar_valor(fila.get('username', '')).lower()
        email = self.limpiar_valor(fila.get('email', '')).lower()
        nombre = self.limpiar_valor(fila.get('nombre', ''))
        apellido = self.limpiar_valor(fila.get('apellido', ''))
        carnet = self.limpiar_valor(fila.get('carnet', ''))
        rol_raw = self.limpiar_valor(fila.get('rol', ''))
        telefono = self.limpiar_valor(fila.get('telefono', ''))

        # --- Validaciones ---
        if not username:
            raise ValueError("Username es obligatorio")
        if not email:
            raise ValueError("Email es obligatorio")
        if not nombre:
            raise ValueError("Nombre es obligatorio")
        if not apellido:
            raise ValueError("Apellido es obligatorio")

        rol = self._normalizar_rol(rol_raw)
        if rol is None:
            raise ValueError(
                f"Rol '{rol_raw}' inválido. Usa: {', '.join(self.ROLES_VALIDOS)}"
            )

        # --- Buscar existente ---
        try:
            usuario_existente = Usuario.objects.get(
                Q(username=username) | Q(email=email)
            )
        except Usuario.DoesNotExist:
            usuario_existente = None
        except Usuario.MultipleObjectsReturned:
            raise ValueError(
                f"Múltiples usuarios con username '{username}' o email '{email}'"
            )

        if usuario_existente and not self.actualizar_existentes:
            self.advertencias.append(f"Usuario '{username}' ya existe (omitido)")
            return

        with transaction.atomic():
            if usuario_existente:
                usuario = usuario_existente
                # ✅ ACTUALIZACIÓN SELECTIVA
                self.actualizar_campos_si_vienen(usuario, {
                    'email': email,
                    'first_name': nombre,
                    'last_name': apellido,
                    'rol': rol,
                    'carnet': carnet,
                    'telefono': telefono,
                }, permitir_limpiar=True)
                usuario.save()
                self.actualizados += 1
                logger.info(f"✅ Usuario actualizado: {usuario.username}")
            else:
                password_temporal = generar_password_temporal()

                usuario = Usuario.objects.create(
                    username=username,
                    email=email,
                    first_name=nombre,
                    last_name=apellido,
                    carnet=carnet or username,
                    rol=rol,
                    telefono=telefono or None,
                    is_active=True,
                    cambiar_password=True,
                    idUniversidad=self.universidad,
                    es_admin_universidad=(rol == 'admin'),
                    password=make_password(password_temporal),
                )
                self.exitos += 1
                logger.info(f"✅ Usuario creado: @{username} (rol: {rol})")

                try:
                    from .alert_service import AlertaService
                    AlertaService.notificar_credenciales_usuario(
                        usuario=usuario,
                        password_temporal=password_temporal,
                        request=None
                    )
                except Exception as e:
                    logger.error(f"Error enviando credenciales: {str(e)}")
                    self.advertencias.append(f"No se pudo enviar credenciales a {email}")