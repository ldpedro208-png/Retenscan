# fix_migrations.py
import os
import shutil
import sys
import django
from django.db import connection
from django.core.management import call_command

# Configurar Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'retenscan_project.settings')
django.setup()

def fix_migrations():
    print("=" * 60)
    print("🔄 ARREGLANDO INCONSISTENCIA DE MIGRACIONES")
    print("=" * 60)
    
    # 1. Mostrar estado actual
    print("\n📊 Estado actual de migraciones:")
    with connection.cursor() as cursor:
        cursor.execute("SELECT app, name, applied FROM django_migrations ORDER BY app, name")
        rows = cursor.fetchall()
        for row in rows:
            print(f"   {row[0]}.{row[1]} - {row[2]}")
    
    # 2. Eliminar migraciones problemáticas
    print("\n🗑️ Eliminando migraciones de core...")
    with connection.cursor() as cursor:
        cursor.execute("DELETE FROM django_migrations WHERE app = 'core'")
        print(f"   Core eliminado: {cursor.rowcount}")
    
    print("\n🗑️ Eliminando migraciones de chat...")
    with connection.cursor() as cursor:
        cursor.execute("DELETE FROM django_migrations WHERE app = 'chat'")
        print(f"   Chat eliminado: {cursor.rowcount}")
    
    # 3. Eliminar migraciones de admin (opcional, pero ayuda)
    print("\n🗑️ Eliminando migraciones de admin...")
    with connection.cursor() as cursor:
        cursor.execute("DELETE FROM django_migrations WHERE app = 'admin'")
        print(f"   Admin eliminado: {cursor.rowcount}")
    
    # 4. Eliminar archivos de migración
    print("\n🗑️ Eliminando archivos de migración...")
    
    def clean_migrations(app_name):
        migrations_dir = f'{app_name}/migrations'
        if os.path.exists(migrations_dir):
            for file in os.listdir(migrations_dir):
                file_path = os.path.join(migrations_dir, file)
                if file != '__init__.py' and file.endswith('.py'):
                    os.remove(file_path)
                    print(f"   Eliminado: {file_path}")
            print(f"✅ Migraciones de {app_name} limpiadas")
        else:
            print(f"⚠️ Directorio {migrations_dir} no existe")
    
    clean_migrations('core')
    clean_migrations('chat')
    
    # 5. Crear migraciones en el orden correcto
    print("\n📝 Paso 5: Creando migraciones en orden...")
    
    print("   Creando migraciones para core...")
    call_command('makemigrations', 'core', verbosity=1)
    
    print("   Creando migraciones para chat...")
    call_command('makemigrations', 'chat', verbosity=1)
    
    # 6. Aplicar migraciones
    print("\n🔄 Paso 6: Aplicando migraciones...")
    call_command('migrate', verbosity=1)
    
    # 7. Verificar
    print("\n✅ Paso 7: Verificando estado...")
    call_command('showmigrations')
    
    print("\n" + "=" * 60)
    print("✅ MIGRACIONES ARREGLADAS EXITOSAMENTE")
    print("=" * 60)

if __name__ == "__main__":
    try:
        fix_migrations()
    except Exception as e:
        print(f"\n❌ Error: {e}")
        print("\nSi el error persiste, ejecuta:")
        print("   python manage.py migrate --fake")