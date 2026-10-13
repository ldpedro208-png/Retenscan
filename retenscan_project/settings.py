"""
Django settings for retenscan_project project.
"""

import os
from pathlib import Path
import sys
import logging

# ============================================
# ✅ CONFIGURACIÓN DE ENCODING PARA WINDOWS
# ============================================
if sys.platform == 'win32':
    import codecs
    try:
        if hasattr(sys.stdout, 'buffer'):
            sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
            sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')
    except (AttributeError, ValueError):
        pass

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent


# Quick-start development settings - unsuitable for production
SECRET_KEY = 'django-insecure-71t#)%wmdfie7$7569s&q#qf#ff@3qx3g)m8r2nh3pipr+pyv4'
DEBUG = True
ALLOWED_HOSTS = ['127.0.0.1', 'localhost']


# ============================================
# ✅ APLICACIONES - ORDEN CORRECTO
# ============================================
INSTALLED_APPS = [
    'daphne',  # ✅ DEBE SER EL PRIMERO
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',  # ✅ Después de daphne
    'rest_framework',
    'channels',
    'corsheaders',
    'chat',
    'core',
    'biblioteca',
]


MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'core.middleware.ForzarCambioPasswordMiddleware',
    'core.middleware.SessionControlMiddleware',
    'core.middleware.ConfiguracionDinamicaMiddleware',
    'core.middleware.SistemaMantenimientoMiddleware', 
]

ROOT_URLCONF = 'retenscan_project.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates/layout'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'core.context_processors.user_rol',
                'core.context_processors.configuracion_sistema', 
                'core.context_processors.mensajes_no_leidos',
            ],
        },
    },
]

# ============================================
# ✅ ASGI Y CHANNEL LAYERS
# ============================================

ASGI_APPLICATION = 'retenscan_project.asgi.application'

# ✅ Usar InMemory (NO requiere Redis - para desarrollo)
CHANNEL_LAYERS = {
    'default': {
        'BACKEND': 'channels.layers.InMemoryChannelLayer'
    },
}

# ✅ Si tienes Redis instalado, usa esta configuración:
# CHANNEL_LAYERS = {
#     'default': {
#         'BACKEND': 'channels_redis.core.RedisChannelLayer',
#         'CONFIG': {
#             "hosts": [('127.0.0.1', 6379)],
#         },
#     },
# }

# Static files
STATIC_URL = '/static/'
STATICFILES_DIRS = [
    BASE_DIR / "static",
]

WSGI_APPLICATION = 'retenscan_project.wsgi.application'


# Database
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'RetenScan',
        'USER': 'postgres',
        'PASSWORD': 'postgres',
        'HOST': 'localhost',
        'PORT': '5432',
    }
}

REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework.authentication.SessionAuthentication',
        'rest_framework.authentication.BasicAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
    'DEFAULT_RENDERER_CLASSES': [
        'rest_framework.renderers.JSONRenderer',
        'rest_framework.renderers.BrowsableAPIRenderer',
    ],
}

# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]


# Internationalization
LANGUAGE_CODE = 'es-es'
TIME_ZONE = 'America/La_Paz'
USE_I18N = True
USE_TZ = True


# ============================================
# ✅ CONFIGURACIÓN DE ARCHIVOS ESTÁTICOS
# ============================================

STATIC_URL = '/static/'
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')

STATICFILES_DIRS = [
    os.path.join(BASE_DIR, 'static'),
]

STATICFILES_STORAGE = 'django.contrib.staticfiles.storage.StaticFilesStorage'

MEDIA_URL = '/media/'
MEDIA_ROOT = os.path.join(BASE_DIR, 'media')


#cerrar el tema de seguridad al 100%
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_BROWSER_XSS_FILTER = True
X_FRAME_OPTIONS = 'DENY'
SECURE_REFERRER_POLICY = 'strict-origin-when-cross-origin'

# ============================================
# AUTENTICACIÓN
# ============================================

LOGIN_URL = 'login'
LOGIN_REDIRECT_URL = 'dashboard'
LOGOUT_REDIRECT_URL = 'login'
AUTH_USER_MODEL = 'core.Usuario'


# ============================================
# CONFIGURACIÓN DE EMAIL
# ============================================

EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = 'smtp.gmail.com'
EMAIL_PORT = 587
EMAIL_USE_TLS = True
EMAIL_HOST_USER = 'tu_correo@gmail.com'
EMAIL_HOST_PASSWORD = 'tu_contraseña_app'
DEFAULT_FROM_EMAIL = f'RetenScan <{EMAIL_HOST_USER}>'

SITE_URL = 'http://127.0.0.1:8000'


# ============================================
# TWILIO (WhatsApp)
# ============================================

TWILIO_ACCOUNT_SID = 'tu_account_sid'
TWILIO_AUTH_TOKEN = 'tu_auth_token'
TWILIO_WHATSAPP_NUMBER = 'whatsapp:+14155238886'
TWILIO_WHATSAPP_FROM = 'whatsapp:+14155238886'


# ============================================
# ✅ LOGGING
# ============================================

LOGS_DIR = BASE_DIR / 'logs'
if not LOGS_DIR.exists():
    LOGS_DIR.mkdir(parents=True, exist_ok=True)

class UTF8ConsoleHandler(logging.StreamHandler):
    def __init__(self, stream=None):
        if stream is None:
            stream = sys.stdout
        super().__init__(stream)
        if hasattr(stream, 'reconfigure'):
            try:
                stream.reconfigure(encoding='utf-8', errors='ignore')
            except:
                pass
    
    def emit(self, record):
        try:
            msg = self.format(record)
            stream = self.stream
            try:
                stream.write(msg + self.terminator)
            except UnicodeEncodeError:
                msg = msg.encode('ascii', 'ignore').decode('ascii')
                stream.write(msg + self.terminator)
            self.flush()
        except Exception:
            self.handleError(record)

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {process:d} {thread:d} {message}',
            'style': '{',
        },
        'simple': {
            'format': '{levelname} {asctime} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'stream': sys.stdout,
            'formatter': 'simple',
        },
        'console_utf8': {
            '()': UTF8ConsoleHandler,
            'formatter': 'simple',
        },
        'file': {
            'class': 'logging.FileHandler',
            'filename': LOGS_DIR / 'retenscan.log',
            'formatter': 'verbose',
            'encoding': 'utf-8',
        },
    },
    'root': {
        'handlers': ['console_utf8', 'file'],
        'level': 'INFO',
    },
    'loggers': {
        'django': {
            'handlers': ['console_utf8'],
            'level': 'INFO',
            'propagate': False,
        },
        'django.db.backends': {
            'handlers': ['console_utf8'],
            'level': 'INFO',
            'propagate': False,
        },
        'core': {
            'handlers': ['console_utf8', 'file'],
            'level': 'INFO',
            'propagate': False,
        },
        'chat': {
            'handlers': ['console_utf8', 'file'],
            'level': 'DEBUG',
            'propagate': False,
        },
        'channels': {
            'handlers': ['console_utf8'],
            'level': 'INFO',
            'propagate': False,
        },
        'daphne': {
            'handlers': ['console_utf8'],
            'level': 'INFO',
            'propagate': False,
        },
    },
}


# ============================================
# SEGURIDAD
# ============================================

SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False
SESSION_COOKIE_HTTPONLY = True
CSRF_COOKIE_HTTPONLY = True
X_FRAME_OPTIONS = 'DENY'
SECURE_CONTENT_TYPE_NOSNIFF = True

DATA_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024
FILE_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024


# ============================================
# SESIONES
# ============================================

SESSION_ENGINE = 'django.contrib.sessions.backends.db'
SESSION_COOKIE_AGE = 14400
SESSION_EXPIRE_AT_BROWSER_CLOSE = False
SESSION_SAVE_EVERY_REQUEST = True
SESSION_COOKIE_SECURE = False
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = 'Lax'
SESSION_COOKIE_NAME = 'retenscan_session'


# ============================================
# CACHÉ
# ============================================

CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'retenscan_cache',
        'TIMEOUT': 300,
        'OPTIONS': {
            'MAX_ENTRIES': 1000,
        }
    }
}

CACHE_MIDDLEWARE_ALIAS = 'default'
CACHE_MIDDLEWARE_SECONDS = 300
CACHE_MIDDLEWARE_KEY_PREFIX = 'retenscan'

CACHE_TIMEOUTS = {
    'dashboard': 600,
    'estudiante_list': 300,
    'encuesta_list': 300,
    'tarea_list': 300,
    'estadisticas': 600,
}


# ============================================
# ⚠️ DEPURACIÓN
# ============================================

if DEBUG:
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(sys.stdout)
        ]
    )
    
    LOGGING['loggers']['django.db.backends'] = {
        'level': 'DEBUG',
        'handlers': ['console_utf8'],
        'propagate': False,
    }