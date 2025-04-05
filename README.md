# MP4 a WAV Conversor

Una aplicación gráfica para convertir archivos de video a audio en diversos formatos, optimizados para transcripción o uso general.

## Características

- Interfaz gráfica moderna e intuitiva
- Disponible en dos versiones: Tkinter (básica) y PyQt5 (avanzada)
- Soporta múltiples formatos de video (mp4, mov, avi, mkv, m4v, wmv, flv, ts, etc.)
- **Múltiples formatos de salida**: WAV, MP3, OGG, FLAC, AAC, M4A, OPUS y WMA
- Control de calidad de audio para cada formato
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

Versión mejorada con una interfaz más profesional, mejor manejo de checkboxes y selección de carpetas, y soporte para múltiples formatos de audio:

```
python mp4towav_qt.py
```

## Uso

1. Ejecute la versión deseada del script Python
2. Seleccione la carpeta de entrada que contiene sus videos
3. (Opcional) Seleccione la carpeta de salida donde se guardarán los archivos de audio
4. Configure las opciones (buscar subcarpetas, sobrescribir existentes)
5. Seleccione el formato de salida deseado y la calidad (versión PyQt5)
6. Use las pestañas para filtrar formatos específicos o seleccionar carpetas particulares
7. Haga clic en "Escanear Archivos" para ver qué archivos serán procesados
8. Haga clic en "Iniciar Conversión"

## Formatos de Audio Soportados (Versión PyQt5)

- **WAV** - Sin compresión, calidad perfecta (optimizado para Whisper)
- **MP3** - Compresión con pérdida, compatible universalmente
- **OGG** - Formato libre, mejor calidad que MP3 a mismo tamaño
- **FLAC** - Compresión sin pérdida, calidad perfecta, archivo más pequeño que WAV
- **AAC** - Mejor calidad que MP3 a mismo bitrate
- **M4A** - Contenedor para AAC, usado en ecosistema Apple
- **OPUS** - Formato más nuevo, excelente calidad a bitrates bajos
- **WMA** - Formato de Microsoft, buena compatibilidad en Windows

## Opciones

- **Buscar en subcarpetas**: Busca videos en todas las subcarpetas del directorio seleccionado
- **Sobrescribir archivos existentes**: Reemplaza archivos de audio que ya existen
- **Filtros de formato**: Seleccione qué formatos de video desea convertir
- **Selección de carpetas**: Elija qué carpetas específicas desea procesar
- **Nivel de calidad**: Ajuste la calidad del audio resultante (tamaño vs. calidad) 