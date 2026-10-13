# chat/apps.py
from django.apps import AppConfig

class ChatConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'chat'
    verbose_name = 'Sistema de Chat'
    
    def ready(self):
        # Importar señales aquí si las tienes
        pass