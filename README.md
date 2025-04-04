# MP4 a WAV Conversor (GUI)

Una aplicación gráfica para convertir archivos de video a WAV optimizados para transcripción con Whisper.

## Características

- Interfaz gráfica intuitiva hecha con Tkinter
- Soporta múltiples formatos de video (mp4, mov, avi, mkv, m4v, wmv, flv, ts)
- Convierte a formato WAV optimizado para Whisper (PCM 16-bit, mono, 16kHz)
- Preserva la estructura de carpetas al procesar subcarpetas
- Multithreading para mantener la GUI responsive durante las conversiones
- Barra de progreso y registro detallado de operaciones

## Requisitos

- Python 3.6 o superior
- ffmpeg instalado y disponible en el PATH del sistema

## Uso

1. Ejecute el script Python:
   ```
   python mp4towav_gui.py
   ```
2. Seleccione la carpeta de entrada que contiene sus videos
3. Seleccione la carpeta de salida donde se guardarán los archivos WAV
4. Configure las opciones (buscar subcarpetas, sobrescribir existentes)
5. Haga clic en "Iniciar Conversión"

## Opciones

- **Buscar en subcarpetas**: Busca videos en todas las subcarpetas del directorio seleccionado
- **Sobrescribir archivos existentes**: Reemplaza archivos WAV que ya existen 