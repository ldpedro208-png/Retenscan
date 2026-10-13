# scripts/migrate_imports.py
"""
Script para migrar imports de core.services a core.services (paquete)
"""
import os
import re
import glob

def migrar_imports_en_archivo(ruta_archivo):
    """Migra los imports en un archivo específico"""
    try:
        with open(ruta_archivo, 'r', encoding='utf-8') as f:
            contenido = f.read()
        
        contenido_original = contenido
        
        # Patrones de import a migrar
        patrones = [
            # from core.services import X
            (r'from core\.services import (.+)', r'from core.services import \1'),
            # from .services import X (dentro de core)
            (r'from \.services import (.+)', r'from core.services import \1'),
            # import core.services
            (r'import core\.services', r'import core.services'),
        ]
        
        for patron, reemplazo in patrones:
            contenido = re.sub(patron, reemplazo, contenido)
        
        # Solo escribir si hubo cambios
        if contenido != contenido_original:
            with open(ruta_archivo, 'w', encoding='utf-8') as f:
                f.write(contenido)
            return True
        
        return False
        
    except Exception as e:
        print(f"Error procesando {ruta_archivo}: {str(e)}")
        return False

def main():
    """Función principal del script"""
    # Buscar todos los archivos Python en el proyecto
    archivos_python = []
    
    # Directorios a buscar
    directorios = ['core', 'templates', 'static']
    
    for directorio in directorios:
        if os.path.exists(directorio):
            archivos_python.extend(
                glob.glob(f'{directorio}/**/*.py', recursive=True)
            )
    
    # También buscar en la raíz
    archivos_python.extend(glob.glob('*.py'))
    
    # Eliminar duplicados
    archivos_python = list(set(archivos_python))
    
    # Excluir el archivo de compatibilidad si existe
    if 'core/services.py' in archivos_python:
        archivos_python.remove('core/services.py')
    
    # Migrar cada archivo
    archivos_migrados = 0
    for archivo in archivos_python:
        if migrar_imports_en_archivo(archivo):
            print(f"✓ Migrado: {archivo}")
            archivos_migrados += 1
    
    print(f"\nTotal de archivos migrados: {archivos_migrados}")

if __name__ == '__main__':
    main()