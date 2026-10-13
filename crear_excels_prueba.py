# crear_excels_prueba.py
"""
Genera 8 archivos Excel de prueba para validar el importador de estudiantes.
Cada archivo cubre un caso de uso distinto.
"""
import pandas as pd
from pathlib import Path

# Carpeta donde se guardarán
BASE_DIR = Path(r'D:\Mis Proyectos\RetenScan')
CARPETA_PRUEBAS = BASE_DIR / 'excels_prueba'
CARPETA_PRUEBAS.mkdir(exist_ok=True)


def guardar(nombre, datos, columnas):
    """Guarda un DataFrame respetando el orden de columnas."""
    df = pd.DataFrame(datos, columns=columnas)
    ruta = CARPETA_PRUEBAS / nombre
    df.to_excel(ruta, index=False, sheet_name='Estudiantes')
    print(f"✅ {nombre}: {len(df)} filas, {len(df.columns)} columnas")


# ============================================
# 1. CASO BÁSICO: solo columnas obligatorias
# ============================================
# Valida: importación mínima sin campos opcionales
print("\n📄 1. Caso básico (solo obligatorias)")
guardar(
    '01_basico.xlsx',
    [
        {'nombre': 'Ana', 'apellido_paterno': 'Torres', 'apellido_materno': 'Vega',
         'carnet': '2024-101', 'email': 'ana.torres@test.com'},
        {'nombre': 'Luis', 'apellido_paterno': 'Ramírez', 'apellido_materno': 'Castro',
         'carnet': '2024-102', 'email': 'luis.ramirez@test.com'},
    ],
    ['nombre', 'apellido_paterno', 'apellido_materno', 'carnet', 'email']
)


# ============================================
# 2. CASO COMPLETO: todas las columnas
# ============================================
# Valida: importación con todos los campos + historial
print("\n📄 2. Caso completo (todas las columnas)")
guardar(
    '02_completo.xlsx',
    [
        {
            'nombre': 'Diego', 'apellido_paterno': 'Fernández', 'apellido_materno': 'Rojas',
            'carnet': '2024-201', 'email': 'diego.fernandez@test.com', 'telefono': '777-1111',
            'carrera': 'Ingeniería de Sistemas', 'codigo_carrera': 'ING-SIS-2024',
            'ano_ingreso': 2024, 'semestre_actual': 2, 'genero': 'M',
            'fecha_nacimiento': '2002-03-10', 'nacionalidad': 'Boliviana',
            'direccion': 'Av. América #100', 'telefono_emergencia': '777-9999',
            'contacto_emergencia': 'María Fernández', 'estado': 'Activo',
            'materia_1': 'Programación I', 'nota_1': 85,
            'materia_2': 'Matemáticas I', 'nota_2': 72,
            'semestre_historial': '2024-1',
        },
        {
            'nombre': 'Sofía', 'apellido_paterno': 'Mendoza', 'apellido_materno': 'Silva',
            'carnet': '2024-202', 'email': 'sofia.mendoza@test.com', 'telefono': '777-2222',
            'carrera': 'Administración de Empresas', 'codigo_carrera': 'ADM-EMP-2024',
            'ano_ingreso': 2024, 'semestre_actual': 1, 'genero': 'F',
            'fecha_nacimiento': '2003-07-22', 'nacionalidad': 'Boliviana',
            'direccion': 'Calle Sucre #50', 'telefono_emergencia': '777-8888',
            'contacto_emergencia': 'Pedro Mendoza', 'estado': 'Activo',
            'materia_1': 'Contabilidad I', 'nota_1': 90,
            'materia_2': 'Economía I', 'nota_2': 88,
            'semestre_historial': '2024-1',
        },
    ],
    ['nombre', 'apellido_paterno', 'apellido_materno', 'carnet', 'email', 'telefono',
     'carrera', 'codigo_carrera', 'ano_ingreso', 'semestre_actual', 'genero',
     'fecha_nacimiento', 'nacionalidad', 'direccion', 'telefono_emergencia',
     'contacto_emergencia', 'estado', 'materia_1', 'nota_1', 'materia_2', 'nota_2',
     'semestre_historial']
)


# ============================================
# 3. APELLIDO UNIFICADO: en vez de paterno/materno
# ============================================
# Valida: normalización de 'apellido' (sin separar)
print("\n📄 3. Apellido unificado")
guardar(
    '03_apellido_unificado.xlsx',
    [
        {'nombre': 'Pedro', 'apellido': 'Gutiérrez López',
         'carnet': '2024-301', 'email': 'pedro.gutierrez@test.com',
         'carrera': 'Psicología', 'codigo_carrera': 'PSI-2024'},
        {'nombre': 'Carmen', 'apellido': 'Vargas Ríos',
         'carnet': '2024-302', 'email': 'carmen.vargas@test.com',
         'carrera': 'Psicología', 'codigo_carrera': 'PSI-2024'},
    ],
    ['nombre', 'apellido', 'carnet', 'email', 'carrera', 'codigo_carrera']
)


# ============================================
# 4. SOLO UN APELLIDO: sin materno
# ============================================
# Valida: apellido_paterno sin materno
print("\n📄 4. Solo apellido paterno")
guardar(
    '04_solo_paterno.xlsx',
    [
        {'nombre': 'Marco', 'apellido_paterno': 'Quispe',
         'carnet': '2024-401', 'email': 'marco.quispe@test.com',
         'carrera': 'Ingeniería de Sistemas', 'codigo_carrera': 'ING-SIS-2024'},
        {'nombre': 'Lucía', 'apellido_materno': 'Condori',
         'carnet': '2024-402', 'email': 'lucia.condori@test.com',
         'carrera': 'Psicología', 'codigo_carrera': 'PSI-2024'},
    ],
    ['nombre', 'apellido_paterno', 'apellido_materno', 'carnet', 'email',
     'carrera', 'codigo_carrera']
)


# ============================================
# 5. ACTUALIZACIÓN PARCIAL: solo algunos campos
# ============================================
# Valida: actualización selectiva (no borra los demás campos)
print("\n📄 5. Actualización parcial")
guardar(
    '05_actualizacion_parcial.xlsx',
    [
        # Solo cambia nombre y email. NO trae carrera, teléfono, dirección, etc.
        {'nombre': 'Juan Carlos', 'apellido_paterno': 'Pérez',
         'apellido_materno': 'Ramírez', 'carnet': '2024-001',
         'email': 'juan.nuevo@test.com'},
    ],
    ['nombre', 'apellido_paterno', 'apellido_materno', 'carnet', 'email']
)


# ============================================
# 6. CON ERRORES: filas inválidas
# ============================================
# Valida: manejo de errores (no debe romper el importador)
print("\n📄 6. Con errores controlados")
guardar(
    '06_con_errores.xlsx',
    [
        # Válido
        {'nombre': 'Valentina', 'apellido_paterno': 'Núñez', 'apellido_materno': 'Ortiz',
         'carnet': '2024-601', 'email': 'valentina.nunez@test.com',
         'carrera': 'Ingeniería de Sistemas', 'codigo_carrera': 'ING-SIS-2024'},
        # Sin carnet (debe fallar)
        {'nombre': 'Sin', 'apellido_paterno': 'Carnet', 'apellido_materno': 'Test',
         'carnet': '', 'email': 'sin.carnet@test.com'},
        # Sin email (debe fallar)
        {'nombre': 'Sin', 'apellido_paterno': 'Email', 'apellido_materno': 'Test',
         'carnet': '2024-603', 'email': ''},
        # Sin nombre (debe fallar)
        {'nombre': '', 'apellido_paterno': 'Sin', 'apellido_materno': 'Nombre',
         'carnet': '2024-604', 'email': 'sin.nombre@test.com'},
        # Válido
        {'nombre': 'Andrés', 'apellido_paterno': 'Salazar', 'apellido_materno': 'Peña',
         'carnet': '2024-605', 'email': 'andres.salazar@test.com',
         'carrera': 'Psicología', 'codigo_carrera': 'PSI-2024'},
    ],
    ['nombre', 'apellido_paterno', 'apellido_materno', 'carnet', 'email',
     'carrera', 'codigo_carrera']
)


# ============================================
# 7. MATERIAS NUEVAS: auto-crear en catálogo
# ============================================
# Valida: auto-creación de materias que no existen
print("\n📄 7. Materias nuevas (auto-crear)")
guardar(
    '07_materias_nuevas.xlsx',
    [
        {
            'nombre': 'Roberto', 'apellido_paterno': 'Flores', 'apellido_materno': 'Chávez',
            'carnet': '2024-701', 'email': 'roberto.flores@test.com',
            'carrera': 'Ingeniería de Sistemas', 'codigo_carrera': 'ING-SIS-2024',
            'ano_ingreso': 2024, 'semestre_actual': 3,
            'materia_1': 'Inteligencia Artificial', 'nota_1': 78,
            'materia_2': 'Redes Neuronales', 'nota_2': 82,
            'materia_3': 'Machine Learning', 'nota_3': 91,
            'semestre_historial': '2024-2',
        },
    ],
    ['nombre', 'apellido_paterno', 'apellido_materno', 'carnet', 'email',
     'carrera', 'codigo_carrera', 'ano_ingreso', 'semestre_actual',
     'materia_1', 'nota_1', 'materia_2', 'nota_2', 'materia_3', 'nota_3',
     'semestre_historial']
)


# ============================================
# 8. MUCHAS MATERIAS: hasta materia_10
# ============================================
# Valida: el límite de MAX_MATERIAS = 10
print("\n📄 8. Muchas materias (hasta 10)")
guardar(
    '08_muchas_materias.xlsx',
    [
        {
            'nombre': 'Gabriela', 'apellido_paterno': 'Ríos', 'apellido_materno': 'Molina',
            'carnet': '2024-801', 'email': 'gabriela.rios@test.com',
            'carrera': 'Ingeniería de Sistemas', 'codigo_carrera': 'ING-SIS-2024',
            'ano_ingreso': 2024, 'semestre_actual': 5,
            'materia_1': 'Cálculo I', 'nota_1': 85,
            'materia_2': 'Física I', 'nota_2': 78,
            'materia_3': 'Química', 'nota_3': 92,
            'materia_4': 'Álgebra Lineal', 'nota_4': 88,
            'materia_5': 'Estadística', 'nota_5': 75,
            'materia_6': 'Base de Datos II', 'nota_6': 95,
            'materia_7': 'Sistemas Operativos', 'nota_7': 83,
            'materia_8': 'Compiladores', 'nota_8': 70,
            'materia_9': 'Ingeniería de Software', 'nota_9': 89,
            'materia_10': 'Ética Profesional', 'nota_10': 98,
            'semestre_historial': '2024-1',
        },
    ],
    ['nombre', 'apellido_paterno', 'apellido_materno', 'carnet', 'email',
     'carrera', 'codigo_carrera', 'ano_ingreso', 'semestre_actual',
     'materia_1', 'nota_1', 'materia_2', 'nota_2', 'materia_3', 'nota_3',
     'materia_4', 'nota_4', 'materia_5', 'nota_5', 'materia_6', 'nota_6',
     'materia_7', 'nota_7', 'materia_8', 'nota_8', 'materia_9', 'nota_9',
     'materia_10', 'nota_10', 'semestre_historial']
)


print("\n" + "=" * 60)
print(f"✅ Todos los archivos generados en: {CARPETA_PRUEBAS}")
print("=" * 60)
print("\nArchivos creados:")
for f in sorted(CARPETA_PRUEBAS.glob('*.xlsx')):
    print(f"  📄 {f.name}")