# chat/management/commands/runserver_with_redis.py
import sys
import subprocess
import threading
import time
import os
from django.core.management.base import BaseCommand
from django.core.management import call_command

class Command(BaseCommand):
    help = 'Ejecuta el servidor de desarrollo con Redis y Daphne'

    def add_arguments(self, parser):
        parser.add_argument(
            '--no-redis',
            action='store_true',
            help='No iniciar Redis automáticamente',
        )
        parser.add_argument(
            '--port',
            type=int,
            default=8000,
            help='Puerto para el servidor',
        )

    def handle(self, *args, **options):
        port = options.get('port', 8000)
        no_redis = options.get('no_redis', False)
        
        self.stdout.write(self.style.SUCCESS('=' * 60))
        self.stdout.write(self.style.SUCCESS('🚀 Iniciando servidor con WebSockets y Redis'))
        self.stdout.write(self.style.SUCCESS(f'📌 Servidor en: http://127.0.0.1:{port}'))
        self.stdout.write(self.style.SUCCESS('=' * 60))
        
        if not no_redis:
            self.start_redis()
        
        self.run_daphne(port)
    
    def start_redis(self):
        """Iniciar Redis en segundo plano"""
        try:
            import redis
            try:
                r = redis.Redis(host='localhost', port=6379, decode_responses=True)
                r.ping()
                self.stdout.write(self.style.SUCCESS('✅ Redis ya está corriendo'))
                return
            except:
                pass
        except:
            pass
        
        self.stdout.write(self.style.WARNING('⏳ Iniciando Redis...'))
        
        redis_paths = [
            'redis-server',
            'C:\\Program Files\\Redis\\redis-server.exe',
            'C:\\Redis\\redis-server.exe',
            os.path.expanduser('~\\AppData\\Local\\Programs\\Redis\\redis-server.exe'),
        ]
        
        for redis_path in redis_paths:
            try:
                if sys.platform == 'win32':
                    subprocess.Popen([redis_path], 
                                   creationflags=subprocess.CREATE_NEW_CONSOLE,
                                   stdout=subprocess.DEVNULL,
                                   stderr=subprocess.DEVNULL)
                else:
                    subprocess.Popen([redis_path], 
                                   stdout=subprocess.DEVNULL,
                                   stderr=subprocess.DEVNULL)
                self.stdout.write(self.style.SUCCESS('✅ Redis iniciado correctamente'))
                time.sleep(2)
                return
            except:
                continue
        
        self.stdout.write(self.style.WARNING('⚠️ No se pudo iniciar Redis automáticamente'))
    
    def run_daphne(self, port):
        """Ejecutar Daphne para WebSockets"""
        self.stdout.write(self.style.SUCCESS('🔄 Iniciando Daphne...'))
        args = [
            sys.executable, '-m', 'daphne',
            '-b', '127.0.0.1',
            '-p', str(port),
            'retenscan_project.asgi:application'
        ]
        subprocess.run(args)