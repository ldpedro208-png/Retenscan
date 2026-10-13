# core/services/importador_estudiantes.py - VERSIÓN CORREGIDA

import re
from datetime import datetime
from decimal import Decimal

from django.contrib.auth.hashers import make_password
from django.db import transaction
from django.db.models import Q, Avg

from ..models import (
    Estudiante, Usuario, CatalogoCarrera, CatalogoUniversidad,
    CatalogoMateria, HistorialAcademico,
)
from ..utils import (
    generar_password_temporal,
    generar_username_desde_nombre,
    logger
)
from .importador_base import ImportadorBase


class ImportadorEstudiantes(ImportadorBase):
    """
    Importador de estudiantes.

    Uso:
        # Desde archivo
        imp = ImportadorEstudiantes(archivo=request.FILES['archivo'],
                                    universidad=u, usuario=request.user,
                                    actualizar_existentes=True)

        # Desde PostgreSQL externo
        fuente = FuentePostgres('bd_externa',
                                'SELECT carnet, nombres AS nombre, '
                                'apellidos AS apellido, email FROM alumnos')
        imp = ImportadorEstudiantes(fuente=fuente, universidad=u, usuario=request.user)
    """

    COLUMNAS_REQUERIDAS = ['carnet', 'email', 'nombre', 'apellido']

    MAPEO_COLUMNAS = {
        'contacto_emergencia': 'contacto_emergencia_nombre',
        'estado': 'estado_academico',
    }

    ESTADOS_ACADEMICOS_VALIDOS = [
        'Activo', 'Inactivo', 'Suspendido', 'Egresado', 'Abandonado'
    ]

    MAPA_GENERO = {
        'm': 'M', 'masculino': 'M', 'hombre': 'M',
        'f': 'F', 'femenino': 'F', 'mujer': 'F',
        'otro': 'Otro', 'no especificado': 'No especificado',
    }

    NOTA_APROBACION = 11
    MAX_MATERIAS = 10

    def __init__(self, archivo=None, universidad=None, usuario=None,
                 crear_usuarios=True, actualizar_existentes=False,
                 fuente=None):
        super().__init__(archivo=archivo, universidad=universidad,
                         usuario=usuario, fuente=fuente)
        self.crear_usuarios = crear_usuarios
        self.actualizar_existentes = actualizar_existentes
        self.carreras_cache = {}
        self.materias_cache = {}

    # ============================================
    # HOOK: normalización de apellidos
    # ============================================

    def pre_procesar(self):
        self._normalizar_apellidos()

    def _normalizar_apellidos(self):
        if not self.datos:
            return

        columnas_normalizadas = {
            str(c).strip().lower().replace(' ', '_'): c
            for c in (self.columnas or [])
        }
        cols = set(columnas_normalizadas.keys())

        tiene_apellido = 'apellido' in cols
        tiene_paterno = 'apellido_paterno' in cols
        tiene_materno = 'apellido_materno' in cols

        if tiene_apellido and not (tiene_paterno or tiene_materno):
            for fila in self.datos:
                fila.setdefault('apellido_materno', '')
            return

        for fila in self.datos:
            apellido_actual = self.limpiar_valor(
                fila.get(columnas_normalizadas.get('apellido', 'apellido'), '')
            ) if tiene_apellido else ''

            paterno = self.limpiar_valor(
                fila.get(columnas_normalizadas.get('apellido_paterno', 'apellido_paterno'), '')
            ) if tiene_paterno else ''

            materno = self.limpiar_valor(
                fila.get(columnas_normalizadas.get('apellido_materno', 'apellido_materno'), '')
            ) if tiene_materno else ''

            if tiene_apellido:
                if materno and materno not in apellido_actual:
                    fila['apellido'] = f"{apellido_actual} {materno}".strip()
                else:
                    fila['apellido'] = apellido_actual
                fila['apellido_materno'] = ''
            elif tiene_paterno and tiene_materno:
                fila['apellido'] = f"{paterno} {materno}".strip()
                fila['apellido_materno'] = ''
            elif tiene_paterno:
                fila['apellido'] = paterno
                fila['apellido_materno'] = ''
            elif tiene_materno:
                fila['apellido'] = materno
                fila['apellido_materno'] = ''

        cols_lower = [str(c).strip().lower() for c in self.columnas]
        if 'apellido' not in cols_lower:
            self.columnas = list(self.columnas) + ['apellido']
        if 'apellido_materno' not in cols_lower:
            self.columnas = list(self.columnas) + ['apellido_materno']

    # ============================================
    # HELPERS
    # ============================================

    def _parse_fecha(self, valor):
        if not valor:
            return None
        if hasattr(valor, 'date'):
            return valor.date()
        if hasattr(valor, 'year'):
            return valor

        valor = str(valor).strip()
        formatos = ['%Y-%m-%d', '%d/%m/%Y', '%d-%m-%Y', '%Y/%m/%d']
        for fmt in formatos:
            try:
                return datetime.strptime(valor, fmt).date()
            except ValueError:
                continue
        return None

    def _normalizar_codigo_carrera(self, codigo):
        if not codigo:
            return None
        codigo = str(codigo).strip().upper()
        return re.sub(r'[-_]\d{4}$', '', codigo)

    def _normalizar_genero(self, genero):
        if not genero:
            return None
        clave = str(genero).strip().lower()
        return self.MAPA_GENERO.get(clave)

    def _generar_codigo_carrera_unico(self, base):
        """✅ NUEVO: Genera un código único para auto-crear carreras."""
        base = (base or 'AUTO')[:10].upper().replace(' ', '_')
        codigo = base
        counter = 1
        while CatalogoCarrera.objects.filter(codigo=codigo).exists():
            codigo = f"{base}-{counter}"
            counter += 1
        return codigo

    # ============================================
    # CARRERAS
    # ============================================

    def obtener_carrera(self, nombre, codigo=None):
        """Obtiene una carrera con búsqueda flexible."""
        cache_key = f"{nombre}_{codigo}"
        if cache_key in self.carreras_cache:
            return self.carreras_cache[cache_key]

        codigo_normalizado = self._normalizar_codigo_carrera(codigo)

        # 1. Por código normalizado
        if codigo_normalizado:
            carrera = CatalogoCarrera.objects.filter(
                codigo__iexact=codigo_normalizado,
                idUniversidad=self.universidad
            ).first()
            if carrera:
                self.carreras_cache[cache_key] = carrera
                return carrera

        # 2. Por código completo
        if codigo:
            carrera = CatalogoCarrera.objects.filter(
                codigo__iexact=str(codigo).strip(),
                idUniversidad=self.universidad
            ).first()
            if carrera:
                self.carreras_cache[cache_key] = carrera
                return carrera

        # 3. Por nombre exacto
        if nombre:
            carrera = CatalogoCarrera.objects.filter(
                nombre__iexact=nombre,
                idUniversidad=self.universidad
            ).first()
            if carrera:
                self.carreras_cache[cache_key] = carrera
                return carrera

        # 4. Por nombre parcial
        if nombre:
            carrera = CatalogoCarrera.objects.filter(
                nombre__icontains=nombre,
                idUniversidad=self.universidad
            ).first()
            if carrera:
                self.carreras_cache[cache_key] = carrera
                self.advertencias.append(
                    f"Carrera '{nombre}' encontrada como '{carrera.nombre}'"
                )
                return carrera

        # 5. Crear si no existe (solo admin)
        if nombre and self.usuario and self.usuario.rol == 'admin':
            try:
                with transaction.atomic():
                    # ✅ CAMBIO: usar helper para código único
                    codigo_final = codigo_normalizado or self._generar_codigo_carrera_unico(
                        f"AUTO_{nombre[:5]}"
                    )
                    carrera = CatalogoCarrera.objects.create(
                        nombre=nombre,
                        codigo=codigo_final,
                        idUniversidad=self.universidad
                    )
                    self.carreras_cache[cache_key] = carrera
                    self.advertencias.append(f"Carrera '{nombre}' creada automáticamente")
                    return carrera
            except Exception as e:
                self.errores.append(f"Error creando carrera '{nombre}': {str(e)}")
                return None

        self.errores.append(f"Carrera '{nombre}' no encontrada")
        return None

    # ============================================
    # MATERIAS
    # ============================================

    def obtener_materia(self, nombre, carrera):
        """
        Obtiene una materia por nombre dentro de una carrera.
        Si no existe y el usuario es admin, la crea automáticamente.
        """
        if not nombre:
            return None

        nombre_limpio = str(nombre).strip()
        cache_key = f"{nombre_limpio}_{carrera.pk if carrera else 'none'}"
        if cache_key in self.materias_cache:
            return self.materias_cache[cache_key]

        # 1. Por nombre exacto
        qs = CatalogoMateria.objects.filter(nombre__iexact=nombre_limpio)
        if carrera:
            qs = qs.filter(idCarrera=carrera)
        materia = qs.first()
        if materia:
            self.materias_cache[cache_key] = materia
            return materia

        # 2. Por nombre parcial
        qs = CatalogoMateria.objects.filter(nombre__icontains=nombre_limpio)
        if carrera:
            qs = qs.filter(idCarrera=carrera)
        materia = qs.first()
        if materia:
            self.materias_cache[cache_key] = materia
            self.advertencias.append(
                f"Materia '{nombre_limpio}' encontrada como '{materia.nombre}'"
            )
            return materia

        # 3. Crear si no existe (solo admin)
        if carrera and self.usuario and self.usuario.rol == 'admin':
            try:
                with transaction.atomic():
                    base_codigo = f"AUTO-{nombre_limpio[:8].upper().replace(' ', '_')}"
                    codigo = base_codigo
                    counter = 1
                    while CatalogoMateria.objects.filter(codigo=codigo).exists():
                        codigo = f"{base_codigo}-{counter}"
                        counter += 1

                    materia = CatalogoMateria.objects.create(
                        nombre=nombre_limpio,
                        codigo=codigo,
                        idCarrera=carrera,
                        creditos=3,
                    )
                    self.materias_cache[cache_key] = materia
                    self.advertencias.append(
                        f"Materia '{nombre_limpio}' creada automáticamente"
                    )
                    return materia
            except Exception as e:
                self.errores.append(f"Error creando materia '{nombre_limpio}': {str(e)}")
                return None

        return None

    # ============================================
    # HISTORIAL ACADÉMICO
    # ============================================

    def _procesar_historial(self, estudiante, fila):
        """
        Procesa las columnas materia_N / nota_N / semestre_historial
        y las guarda en HistorialAcademico.
        """
        semestre_hist = self.limpiar_valor(fila.get('semestre_historial', ''))
        if not semestre_hist:
            return

        for i in range(1, self.MAX_MATERIAS + 1):
            nombre_materia = self.limpiar_valor(fila.get(f'materia_{i}', ''))
            if not nombre_materia:
                continue

            nota_raw = fila.get(f'nota_{i}', None)

            materia = self.obtener_materia(nombre_materia, estudiante.idCarrera)
            if not materia:
                self.advertencias.append(
                    f"Materia '{nombre_materia}' no encontrada (omitida)"
                )
                continue

            nota = None
            if nota_raw not in (None, '', 'nan', 'NaN'):
                nota = self.parse_decimal(nota_raw, default=None)

            if nota is None:
                estado_materia = 'Cursando'
            elif nota >= self.NOTA_APROBACION:
                estado_materia = 'Aprobada'
            else:
                estado_materia = 'Reprobada'

            try:
                HistorialAcademico.objects.update_or_create(
                    idEstudiante=estudiante,
                    idMateria=materia,
                    semestre=semestre_hist,
                    defaults={
                        'nota_final': nota,
                        'estado_materia': estado_materia,
                    }
                )
            except Exception as e:
                self.advertencias.append(
                    f"No se pudo guardar historial de '{nombre_materia}': {str(e)}"
                )

    def _recalcular_promedio(self, estudiante):
        """Recalcula promedio_general del estudiante."""
        try:
            agregado = HistorialAcademico.objects.filter(
                idEstudiante=estudiante,
                nota_final__isnull=False,
            ).aggregate(promedio=Avg('nota_final'))

            promedio = agregado['promedio']
            if promedio is not None:
                estudiante.promedio_general = Decimal(str(round(float(promedio), 2)))
                estudiante.save(update_fields=['promedio_general'])
        except Exception as e:
            self.advertencias.append(
                f"No se pudo recalcular promedio de {estudiante}: {str(e)}"
            )

    # ============================================
    # PROCESAMIENTO DE FILA
    # ============================================

    def procesar_fila(self, fila, indice):
        """Procesa una fila de estudiantes."""
        from .alert_service import AlertaService

        # --- Lectura ---
        carnet = self.limpiar_valor(fila.get('carnet', ''))
        email = self.limpiar_valor(fila.get('email', '')).lower()
        nombre = self.limpiar_valor(fila.get('nombre', ''))
        apellido = self.limpiar_valor(fila.get('apellido', ''))
        apellido_materno = self.limpiar_valor(fila.get('apellido_materno', ''))
        telefono = self.limpiar_valor(fila.get('telefono', ''))
        carrera_nombre = self.limpiar_valor(fila.get('carrera', ''))
        carrera_codigo = self.limpiar_valor(fila.get('codigo_carrera', ''))
        ano_ingreso = self.parse_int(fila.get('ano_ingreso'), default=None)
        semestre = self.parse_int(fila.get('semestre_actual'), default=None)
        estado = self.limpiar_valor(fila.get('estado_academico', '')) or self.limpiar_valor(fila.get('estado', ''))

        # Campos extendidos
        genero = self._normalizar_genero(fila.get('genero', ''))
        fecha_nacimiento = self._parse_fecha(fila.get('fecha_nacimiento'))
        nacionalidad = self.limpiar_valor(fila.get('nacionalidad', ''))
        direccion = self.limpiar_valor(fila.get('direccion', ''))
        telefono_emergencia = self.limpiar_valor(fila.get('telefono_emergencia', ''))
        contacto_emergencia = self.limpiar_valor(fila.get('contacto_emergencia_nombre', ''))

        # --- Validaciones obligatorias ---
        if not carnet:
            raise ValueError("Carnet es obligatorio")
        if not email:
            raise ValueError("Email es obligatorio")
        if not nombre:
            raise ValueError("Nombre es obligatorio")
        if not apellido:
            raise ValueError("Apellido es obligatorio")

        # --- Buscar usuario existente ---
        usuario_existente = None
        try:
            usuario_existente = Usuario.objects.get(
                Q(carnet=carnet) | Q(email=email)
            )
        except Usuario.DoesNotExist:
            pass
        except Usuario.MultipleObjectsReturned:
            raise ValueError(
                f"Múltiples usuarios con carnet '{carnet}' o email '{email}'"
            )

        if usuario_existente and not self.actualizar_existentes:
            self.advertencias.append(f"Usuario '{carnet}' ya existe (omitido)")
            return

        # --- Carrera ---
        carrera = None
        if carrera_nombre or carrera_codigo:
            carrera = self.obtener_carrera(carrera_nombre, carrera_codigo)
            if not carrera and carrera_nombre:
                raise ValueError(f"Carrera '{carrera_nombre}' no encontrada")

        # --- Apellido completo ---
        apellido_completo = apellido
        if apellido_materno and apellido_materno not in apellido:
            apellido_completo = f"{apellido} {apellido_materno}"

        with transaction.atomic():
            actualizado_en_esta_fila = False

            # ============================================
            # USUARIO
            # ============================================
            if usuario_existente:
                usuario = usuario_existente
                campos_actualizados = self.actualizar_campos_si_vienen(usuario, {
                    'first_name': nombre,
                    'last_name': apellido_completo,
                    'email': email,
                    'telefono': telefono,
                    'genero': genero,
                    'fecha_nacimiento': fecha_nacimiento,
                }, permitir_limpiar=True)
                if campos_actualizados:
                    usuario.save()
                    actualizado_en_esta_fila = True
                logger.info(f"✅ Usuario procesado: {usuario.username}")
            else:
                try:
                    username = generar_username_desde_nombre(nombre, apellido)
                except ValueError as e:
                    logger.warning(
                        f"⚠️ No se pudo generar username desde nombre/apellido "
                        f"({nombre} {apellido}): {str(e)}. Usando carnet."
                    )
                    username = carnet.lower()
                    base = username
                    counter = 1
                    while Usuario.objects.filter(username=username).exists():
                        username = f"{base}{counter}"
                        counter += 1

                password_temporal = generar_password_temporal()

                usuario_kwargs = {
                    'username': username,
                    'email': email,
                    'first_name': nombre,
                    'last_name': apellido_completo,
                    'carnet': carnet,
                    'telefono': telefono or None,
                    'rol': 'estudiante',
                    'is_active': True,
                    'cambiar_password': True,
                    'notificaciones_email': True,
                    'idUniversidad': self.universidad,
                    'password': make_password(password_temporal),
                }
                if genero:
                    usuario_kwargs['genero'] = genero
                if fecha_nacimiento:
                    usuario_kwargs['fecha_nacimiento'] = fecha_nacimiento

                usuario = Usuario.objects.create(**usuario_kwargs)
                self.exitos += 1
                logger.info(f"✅ Usuario creado: @{username}")

                try:
                    AlertaService.notificar_credenciales_usuario(
                        usuario=usuario,
                        password_temporal=password_temporal,
                        request=None
                    )
                except Exception as e:
                    logger.warning(f"⚠️ No se pudo enviar credenciales a {email}: {str(e)}")
                    self.advertencias.append(f"No se pudo enviar credenciales a {email}")

            # ============================================
            # ESTUDIANTE
            # ============================================
            defaults_estudiante = {
                'idCarrera': carrera,
                'idUniversidad': self.universidad,
                'ano_ingreso': ano_ingreso if ano_ingreso else 2024,
                'semestre_actual': semestre if semestre else 1,
                'estado_academico': estado if estado in self.ESTADOS_ACADEMICOS_VALIDOS else 'Activo',
            }
            if nacionalidad:
                defaults_estudiante['nacionalidad'] = nacionalidad
            if direccion:
                defaults_estudiante['direccion'] = direccion
            if telefono_emergencia:
                defaults_estudiante['telefono_emergencia'] = telefono_emergencia
            if contacto_emergencia:
                defaults_estudiante['contacto_emergencia_nombre'] = contacto_emergencia

            estudiante, creado = Estudiante.objects.get_or_create(
                idUsuario=usuario,
                defaults=defaults_estudiante,
            )

            if not creado:
                campos_actualizados = self.actualizar_campos_si_vienen(estudiante, {
                    'idCarrera': carrera,
                    'ano_ingreso': ano_ingreso,
                    'semestre_actual': semestre,
                    'estado_academico': estado if estado in self.ESTADOS_ACADEMICOS_VALIDOS else None,
                    'nacionalidad': nacionalidad,
                    'direccion': direccion,
                    'telefono_emergencia': telefono_emergencia,
                    'contacto_emergencia_nombre': contacto_emergencia,
                }, permitir_limpiar=True)
                if campos_actualizados:
                    estudiante.save()
                    actualizado_en_esta_fila = True

            # ============================================
            # HISTORIAL ACADÉMICO
            # ============================================
            self._procesar_historial(estudiante, fila)

            # ============================================
            # RECALCULAR PROMEDIO
            # ============================================
            self._recalcular_promedio(estudiante)

            if actualizado_en_esta_fila:
                self.actualizados += 1