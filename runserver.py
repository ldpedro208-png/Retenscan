# runserver.py
#!/usr/bin/env python
"""
Script para iniciar el servidor Django con Redis integrado.
Uso: python runserver.py [opciones]
"""
import os
import sys
import subprocess
import time
import signal
import atexit
import platform

def main():
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'retenscan_project.settings')
    
    # Iniciar Redis
    redis_process = None
    print("🔄 Iniciando Redis...")
    
    try:
        system = platform.system()
        if system == "Windows":
            redis_cmd = ["redis-server"]
        else:
            redis_cmd = ["redis-server", "--daemonize", "no"]
        
        redis_process = subprocess.Popen(
            redis_cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if system == "Windows" else 0,
            text=True
        )
        
        time.sleep(2)
        
        if redis_process.poll() is None:
            print(f"✅ Redis iniciado (PID: {redis_process.pid})")
        else:
            stdout, stderr = redis_process.communicate()
            print("❌ Error iniciando Redis:", stderr if stderr else "Desconocido")
            redis_process = None
            
    except FileNotFoundError:
        print("❌ Redis no instalado. Instálalo desde:")
        print("  Windows: https://github.com/microsoftarchive/redis/releases")
        print("  Linux: sudo apt-get install redis-server")
        print("  Mac: brew install redis")
        print("\n⚠️ Continuando sin Redis...")
    
    # Función para detener Redis
    def stop_redis():
        if redis_process and redis_process.poll() is None:
            print("\n🔄 Deteniendo Redis...")
            try:
                if platform.system() == "Windows":
                    redis_process.terminate()
                else:
                    redis_process.send_signal(signal.SIGTERM)
                redis_process.wait(timeout=5)
                print("✅ Redis detenido")
            except:
                redis_process.kill()
                print("⚠️ Redis detenido forzosamente")
    
    # Registrar para limpiar al salir
    atexit.register(stop_redis)
    
    # Manejar señales
    def signal_handler(sig, frame):
        stop_redis()
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Ejecutar Django
    try:
        from django.core.management import execute_from_command_line
        sys.argv = ['manage.py', 'runserver'] + sys.argv[1:]
        execute_from_command_line(sys.argv)
    finally:
        stop_redis()

if __name__ == '__main__':
    main()