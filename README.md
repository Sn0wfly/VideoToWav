# MP4 a WAV Conversor

Una aplicación gráfica para convertir archivos de video a WAV optimizados para transcripción con Whisper.

## Características

- Interfaz gráfica moderna e intuitiva
- Disponible en dos versiones: Tkinter (básica) y PyQt5 (avanzada)
- Soporta múltiples formatos de video (mp4, mov, avi, mkv, m4v, wmv, flv, ts, etc.)
- Convierte a formato WAV optimizado para Whisper (PCM 16-bit, mono, 16kHz)
- Preserva la estructura de carpetas al procesar subcarpetas
- Multithreading para mantener la GUI responsive durante las conversiones
- Barra de progreso y registro detallado de operaciones

## Requisitos

- Python 3.6 o superior
- ffmpeg instalado y disponible en el PATH del sistema
- Para la versión PyQt5: biblioteca PyQt5 (`pip install PyQt5`)

## Versiones disponibles

### 1. Versión Tkinter (mp4towav_gui.py)

Versión ligera que usa la biblioteca tkinter incluida con Python:

```
python mp4towav_gui.py
```

### 2. Versión PyQt5 (mp4towav_qt.py) - Recomendada

Versión mejorada con una interfaz más profesional y mejor manejo de checkboxes y selección de carpetas:

```
python mp4towav_qt.py
```

## Uso

1. Ejecute la versión deseada del script Python
2. Seleccione la carpeta de entrada que contiene sus videos
3. (Opcional) Seleccione la carpeta de salida donde se guardarán los archivos WAV
4. Configure las opciones (buscar subcarpetas, sobrescribir existentes)
5. Use las pestañas para filtrar formatos específicos o seleccionar carpetas particulares
6. Haga clic en "Escanear Archivos" para ver qué archivos serán procesados
7. Haga clic en "Iniciar Conversión"

## Opciones

- **Buscar en subcarpetas**: Busca videos en todas las subcarpetas del directorio seleccionado
- **Sobrescribir archivos existentes**: Reemplaza archivos WAV que ya existen 