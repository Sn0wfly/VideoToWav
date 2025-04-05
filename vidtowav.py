#!/usr/bin/env python
import os
import sys
import subprocess
import time
import threading
import queue
from pathlib import Path

from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
                            QLabel, QTreeWidget, QTreeWidgetItem, QProgressBar, QTextEdit, 
                            QPushButton, QCheckBox, QTabWidget, QFileDialog, QMessageBox,
                            QGroupBox, QGridLayout, QSplitter, QComboBox, QButtonGroup, QSlider,
                            QRadioButton, QStyle)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QSize
from PyQt5.QtGui import QIcon, QTextCursor, QFont


class FFmpegWorker(QThread):
    """Hilo de trabajo para la conversión de archivos con ffmpeg"""
    # Señales
    progress_updated = pyqtSignal(int, int)  # Actualizar progreso (actual, total)
    conversion_finished = pyqtSignal()  # Conversión terminada
    log_message = pyqtSignal(str)  # Mensaje de registro
    
    def __init__(self, input_path, output_path, selected_items, selected_formats, 
                 recursive, overwrite_existing, output_format, audio_quality):
        super().__init__()
        self.input_path = input_path
        self.output_path = output_path
        self.selected_items = selected_items
        self.selected_formats = selected_formats
        self.recursive = recursive
        self.overwrite_existing = overwrite_existing
        self.output_format = output_format
        self.audio_quality = audio_quality
        self.stop_requested = False
    
    def run(self):
        # Buscar archivos de video
        self.log_message.emit(f"🔍 Buscando archivos de video en: {self.input_path}")
        self.log_message.emit(f"Formatos seleccionados: {', '.join(self.selected_formats)}")
        
        video_files = self.find_video_files()
        
        if not video_files:
            self.log_message.emit("ℹ️ No se encontraron archivos de video en las carpetas seleccionadas.")
            self.conversion_finished.emit()
            return
        
        self.log_message.emit(f"✅ Se encontraron {len(video_files)} archivos de video.")
        self.log_message.emit(f"Formato de salida: {self.output_format}")
        
        # Contadores
        successful = 0
        failed = 0
        skipped = 0
        total_files = len(video_files)
        
        # Convertir archivos
        self.log_message.emit("🚀 Iniciando conversión...")
        for i, video_file in enumerate(video_files):
            if self.stop_requested:
                self.log_message.emit("⚠️ Proceso de conversión detenido por el usuario.")
                break
                
            # Determinar la ruta de salida
            output_extension = self.get_output_extension()
            
            if not self.output_path:
                # Si no se especificó carpeta de salida, usar la misma que el archivo original
                output_file = video_file.with_suffix(output_extension)
            else:
                # Calcular ruta de salida preservando la estructura de carpetas
                rel_path = video_file.relative_to(self.input_path) if video_file.is_relative_to(self.input_path) else Path(video_file.name)
                output_file = Path(self.output_path) / rel_path.with_suffix(output_extension)
                
                # Crear directorio de salida si no existe
                os.makedirs(output_file.parent, exist_ok=True)
            
            # Verificar si el archivo de salida ya existe
            if output_file.exists() and not self.overwrite_existing:
                self.log_message.emit(f"⏭️ Omitido: {video_file.name} (Ya existe)")
                skipped += 1
            else:
                self.log_message.emit(f"🔄 Convirtiendo: {video_file.name}")
                success = self.convert_audio(str(video_file), str(output_file))
                
                if success:
                    self.log_message.emit(f"✅ Convertido: {video_file.name}")
                    successful += 1
                else:
                    failed += 1
            
            # Actualizar progreso
            self.progress_updated.emit(i + 1, total_files)
            
            # Evitar que el hilo consuma demasiados recursos
            QThread.msleep(10)
        
        # Mostrar resultados
        self.log_message.emit("\n=== Resumen de Conversión ===")
        self.log_message.emit(f"📊 Total de archivos encontrados: {total_files}")
        self.log_message.emit(f"✅ Conversiones exitosas: {successful}")
        self.log_message.emit(f"❌ Conversiones fallidas: {failed}")
        self.log_message.emit(f"⏭️ Archivos omitidos: {skipped}")
        self.log_message.emit("=== Proceso Finalizado ===\n")
        
        # Emitir señal de finalización
        self.conversion_finished.emit()
    
    def get_output_extension(self):
        """Obtiene la extensión de archivo según el formato de salida seleccionado."""
        # Mapeo de formatos a extensiones
        format_extensions = {
            'wav': '.wav',
            'wav_voice': '.wav',
            'mp3': '.mp3',
            'ogg': '.ogg',
            'flac': '.flac',
            'aac': '.aac',
            'm4a': '.m4a',
            'opus': '.opus',
            'wma': '.wma'
        }
        return format_extensions.get(self.output_format, '.wav')
    
    def convert_audio(self, input_file, output_file):
        """Convierte un archivo de video a audio con el formato especificado."""
        try:
            # Configuración base
            command = ['ffmpeg', '-i', input_file, '-vn']
            
            # Configurar el codec y parámetros según el formato seleccionado
            if self.output_format == 'wav':
                # WAV - PCM 16 bit con calidad completa (siempre estéreo)
                command.extend(['-acodec', 'pcm_s16le', '-ar', '44100', '-ac', '2'])
            elif self.output_format == 'wav_voice':
                # WAV para transcripción de voz (siempre 16kHz mono)
                command.extend(['-acodec', 'pcm_s16le', '-ar', '16000', '-ac', '1'])
            elif self.output_format == 'mp3':
                # MP3 con calidad variable
                quality = self.get_mp3_quality()
                command.extend(['-codec:a', 'libmp3lame', '-qscale:a', quality])
            elif self.output_format == 'ogg':
                # OGG Vorbis con calidad variable
                quality = self.get_ogg_quality()
                command.extend(['-codec:a', 'libvorbis', '-qscale:a', quality])
            elif self.output_format == 'flac':
                # FLAC con compresión variable
                command.extend(['-codec:a', 'flac', '-compression_level', str(self.audio_quality)])
            elif self.output_format == 'aac':
                # AAC con bitrate variable
                bitrate = self.get_aac_bitrate()
                command.extend(['-codec:a', 'aac', '-b:a', bitrate])
            elif self.output_format == 'm4a':
                # M4A (AAC en contenedor MP4)
                bitrate = self.get_aac_bitrate()
                command.extend(['-codec:a', 'aac', '-b:a', bitrate])
            elif self.output_format == 'opus':
                # Opus con bitrate variable
                bitrate = self.get_opus_bitrate()
                command.extend(['-codec:a', 'libopus', '-b:a', bitrate])
            elif self.output_format == 'wma':
                # WMA con bitrate variable
                bitrate = self.get_wma_bitrate()
                command.extend(['-codec:a', 'wmav2', '-b:a', bitrate])
            else:
                # Formato desconocido, usar WAV como fallback
                command.extend(['-acodec', 'pcm_s16le', '-ar', '44100', '-ac', '2'])
            
            # Agregar el archivo de salida y parámetros adicionales
            command.extend([
                output_file,
                '-y' if self.overwrite_existing else '-n',
                '-hide_banner', '-loglevel', 'warning'
            ])
            
            # Ejecutar ffmpeg
            result = subprocess.run(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                universal_newlines=True
            )
            
            if result.returncode != 0:
                self.log_message.emit(f"❌ Error al convertir {input_file}: {result.stderr}")
                return False
            
            return True
        except Exception as e:
            self.log_message.emit(f"❌ Error al convertir {input_file}: {str(e)}")
            return False
    
    def get_mp3_quality(self):
        """Obtiene el valor de calidad para MP3 según el nivel seleccionado."""
        # MP3 quality: 0 (mejor) a 9 (peor)
        quality_map = {
            0: '0',  # Mejor calidad
            1: '2',
            2: '4',
            3: '6',
            4: '9'   # Calidad más baja
        }
        return quality_map.get(self.audio_quality, '2')
    
    def get_ogg_quality(self):
        """Obtiene el valor de calidad para OGG Vorbis según el nivel seleccionado."""
        # OGG quality: 0 (peor) a 10 (mejor)
        quality_map = {
            0: '10',  # Mejor calidad
            1: '8',
            2: '6',
            3: '3',
            4: '1'    # Calidad más baja
        }
        return quality_map.get(self.audio_quality, '6')
    
    def get_aac_bitrate(self):
        """Obtiene el bitrate para AAC según el nivel seleccionado."""
        # AAC bitrates
        bitrate_map = {
            0: '256k',  # Mejor calidad
            1: '192k',
            2: '128k',
            3: '96k',
            4: '64k'    # Calidad más baja
        }
        return bitrate_map.get(self.audio_quality, '128k')
    
    def get_opus_bitrate(self):
        """Obtiene el bitrate para Opus según el nivel seleccionado."""
        # Opus bitrates
        bitrate_map = {
            0: '192k',  # Mejor calidad
            1: '128k',
            2: '96k',
            3: '64k',
            4: '32k'    # Calidad más baja
        }
        return bitrate_map.get(self.audio_quality, '96k')
    
    def get_wma_bitrate(self):
        """Obtiene el bitrate para WMA según el nivel seleccionado."""
        # WMA bitrates
        bitrate_map = {
            0: '256k',  # Mejor calidad
            1: '192k',
            2: '128k',
            3: '96k',
            4: '64k'    # Calidad más baja
        }
        return bitrate_map.get(self.audio_quality, '128k')

    def stop(self):
        """Detiene la ejecución del hilo"""
        self.stop_requested = True

    def find_video_files(self):
        """Encuentra archivos de video según los filtros y selecciones"""
        video_files = []
        selected_folders = self.selected_items['folders']
        selected_files = self.selected_items['files']
        
        # Primero añadir los archivos individuales seleccionados
        for file_path in selected_files:
            video_files.append(Path(file_path))
        
        # Luego procesar las carpetas seleccionadas
        for folder in selected_folders:
            # Verificar si la carpeta existe
            if not os.path.exists(folder):
                continue
                
            # Si la búsqueda es recursiva
            if self.recursive:
                for root, _, files in os.walk(folder):
                    for file in files:
                        file_path = os.path.join(root, file)
                        # Verificar si el archivo ya fue añadido como selección individual
                        if file_path in selected_files:
                            continue
                            
                        ext = os.path.splitext(file)[1].lower()
                        if ext in self.selected_formats:
                            video_files.append(Path(file_path))
            # Si la búsqueda no es recursiva, solo buscar en la carpeta actual
            else:
                for file in os.listdir(folder):
                    file_path = os.path.join(folder, file)
                    # Verificar si el archivo ya fue añadido como selección individual
                    if file_path in selected_files:
                        continue
                        
                    if os.path.isfile(file_path):
                        ext = os.path.splitext(file)[1].lower()
                        if ext in self.selected_formats:
                            video_files.append(Path(file_path))
        
        return video_files


class FolderScannerThread(QThread):
    """Hilo para escanear carpetas y contar archivos de video"""
    # Señales
    scan_complete = pyqtSignal(dict, int, int)  # Resultados, total, carpetas
    log_message = pyqtSignal(str)  # Mensaje de registro
    
    def __init__(self, input_path, selected_formats, recursive):
        super().__init__()
        self.input_path = input_path
        self.selected_formats = selected_formats
        self.recursive = recursive
    
    def run(self):
        try:
            # Contadores
            total_files = 0
            folders_with_videos = 0
            folder_counts = {}
            
            # Escanear todas las carpetas o solo la principal
            if self.recursive:
                # Recorrer todas las carpetas
                for root, dirs, files in os.walk(self.input_path):
                    # Contar archivos de video en esta carpeta
                    count = 0
                    for file in files:
                        ext = os.path.splitext(file)[1].lower()
                        if ext in self.selected_formats:
                            count += 1
                    
                    # Si hay videos, registrar esta carpeta
                    if count > 0:
                        rel_path = os.path.relpath(root, self.input_path)
                        folder_counts[rel_path if rel_path != "." else "Carpeta principal"] = count
                        total_files += count
                        folders_with_videos += 1
            else:
                # Solo contar en la carpeta principal
                count = 0
                for file in os.listdir(self.input_path):
                    if os.path.isfile(os.path.join(self.input_path, file)):
                        ext = os.path.splitext(file)[1].lower()
                        if ext in self.selected_formats:
                            count += 1
                
                if count > 0:
                    folder_counts["Carpeta principal"] = count
                    total_files = count
                    folders_with_videos = 1
            
            # Emitir resultados
            self.scan_complete.emit(folder_counts, total_files, folders_with_videos)
            
        except Exception as e:
            self.log_message.emit(f"Error durante el escaneo: {str(e)}")


class VidToWav(QMainWindow):
    """Aplicación para convertir archivos de video a audio con PyQt5"""
    def __init__(self):
        super().__init__()
        
        # Configuración de la ventana principal
        self.setWindowTitle("Convertidor de Video a Audio")
        self.setMinimumSize(900, 700)
        
        # Variables de estado
        self.input_folder = ""
        self.output_folder = ""
        self.conversion_running = False
        self.worker_thread = None
        
        # Lista extendida de formatos de video soportados por ffmpeg
        self.video_formats = [
            '.mp4', '.mov', '.avi', '.mkv', '.m4v', '.wmv', '.flv', '.ts',
            '.webm', '.mpg', '.mpeg', '.m2v', '.mp2', '.m2p', '.mpe', 
            '.3gp', '.3g2', '.mxf', '.rm', '.rmvb', '.asf', '.vob', '.divx',
            '.y4m', '.ogv', '.ogg', '.drc', '.gifv', '.mts', '.m2ts', '.f4v'
        ]
        
        # Formatos de audio de salida disponibles
        self.audio_formats = [
            {'id': 'wav', 'name': 'WAV (PCM) - Sin compresión'},
            {'id': 'wav_voice', 'name': 'WAV para transcripción de voz (16kHz mono)'},
            {'id': 'mp3', 'name': 'MP3 - Compresión popular'},
            {'id': 'ogg', 'name': 'OGG Vorbis - Formato libre'},
            {'id': 'flac', 'name': 'FLAC - Sin pérdida'},
            {'id': 'aac', 'name': 'AAC - Alta calidad'},
            {'id': 'm4a', 'name': 'M4A - Formato Apple'},
            {'id': 'opus', 'name': 'Opus - Alta compresión'},
            {'id': 'wma', 'name': 'WMA - Windows Media Audio'}
        ]
        
        # Variables para los checkboxes de formatos
        self.format_checkboxes = {}
        
        # Variables para el árbol de carpetas
        self.folder_items = {}  # Para acceder rápidamente a los elementos del árbol
        self.file_items = {}  # Para almacenar referencias a los items de archivo
        
        # Configuración de la interfaz
        self.setup_ui()
        
        # Verificar ffmpeg al inicio
        QApplication.processEvents()
        self.check_ffmpeg()
    
    def setup_ui(self):
        """Configura la interfaz de usuario"""
        # Widget central
        central_widget = QWidget(self)
        self.setCentralWidget(central_widget)
        
        # Layout principal
        main_layout = QVBoxLayout(central_widget)
        
        # Tab Widget
        self.tab_widget = QTabWidget()
        main_layout.addWidget(self.tab_widget)
        
        # Pestaña de Conversión
        conversion_tab = QWidget()
        self.tab_widget.addTab(conversion_tab, "Conversión")
        
        # Pestaña de Formatos
        formats_tab = QWidget()
        self.tab_widget.addTab(formats_tab, "Formatos")
        
        # Pestaña de Configuración de Audio
        audio_tab = QWidget()
        self.tab_widget.addTab(audio_tab, "Configuración de Audio")
        
        # Configurar pestaña de conversión
        self.setup_conversion_tab(conversion_tab)
        
        # Configurar pestaña de formatos
        self.setup_formats_tab(formats_tab)
        
        # Configurar pestaña de audio
        self.setup_audio_tab(audio_tab)
        
        # Conectar el cambio del combobox para actualizar los radio buttons
        self.output_format_combo.currentIndexChanged.connect(self.on_output_format_changed)
        
        # Status bar
        self.statusBar().showMessage("Listo")
        
        # Comprobar si FFMPEG está disponible
        if not self.check_ffmpeg():
            self.log_message("⚠️ ADVERTENCIA: ffmpeg no encontrado en el PATH. La conversión no funcionará.")
    
    def setup_conversion_tab(self, tab):
        """Configura la pestaña de conversión"""
        layout = QVBoxLayout(tab)
        
        # Splitter para dividir la interfaz
        splitter = QSplitter(Qt.Horizontal)
        layout.addWidget(splitter)
        
        # Panel izquierdo: árbol de carpetas
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 0, 0, 0)
        
        # Grupo de árbol de carpetas
        tree_group = QGroupBox("Estructura de carpetas y archivos")
        left_layout.addWidget(tree_group)
        
        tree_layout = QVBoxLayout(tree_group)
        
        # Árbol de carpetas
        self.folder_tree = QTreeWidget()
        self.folder_tree.setHeaderLabels(["Nombre"])
        self.folder_tree.setColumnWidth(0, 300)
        self.folder_tree.itemChanged.connect(self.on_tree_item_changed)
        tree_layout.addWidget(self.folder_tree)
        
        # Botones para seleccionar/deseleccionar
        buttons_layout = QHBoxLayout()
        tree_layout.addLayout(buttons_layout)
        
        select_all_btn = QPushButton("Seleccionar Todo")
        select_all_btn.clicked.connect(self.select_all_items)
        buttons_layout.addWidget(select_all_btn)
        
        deselect_all_btn = QPushButton("Deseleccionar Todo")
        deselect_all_btn.clicked.connect(self.deselect_all_items)
        buttons_layout.addWidget(deselect_all_btn)
        
        # Panel derecho: opciones de conversión
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(0, 0, 0, 0)
        
        # Carpetas de entrada/salida
        folder_group = QGroupBox("Carpetas")
        right_layout.addWidget(folder_group)
        
        folder_layout = QGridLayout(folder_group)
        
        # Carpeta de entrada
        folder_layout.addWidget(QLabel("Carpeta de entrada:"), 0, 0)
        self.input_folder_label = QLabel("No seleccionada")
        folder_layout.addWidget(self.input_folder_label, 0, 1)
        
        input_browse_btn = QPushButton("Explorar...")
        input_browse_btn.clicked.connect(self.select_input_folder)
        folder_layout.addWidget(input_browse_btn, 0, 2)
        
        # Botón para abrir carpeta de entrada
        input_open_btn = QPushButton("Abrir")
        input_open_btn.setIcon(self.style().standardIcon(QStyle.SP_DirOpenIcon))
        input_open_btn.clicked.connect(self.open_input_folder)
        folder_layout.addWidget(input_open_btn, 0, 3)
        
        # Carpeta de salida
        folder_layout.addWidget(QLabel("Carpeta de salida:"), 1, 0)
        self.output_folder_label = QLabel("No seleccionada")
        folder_layout.addWidget(self.output_folder_label, 1, 1)
        
        output_browse_btn = QPushButton("Explorar...")
        output_browse_btn.clicked.connect(self.browse_output_folder)
        folder_layout.addWidget(output_browse_btn, 1, 2)
        
        # Botón para abrir carpeta de salida
        output_open_btn = QPushButton("Abrir")
        output_open_btn.setIcon(self.style().standardIcon(QStyle.SP_DirOpenIcon))
        output_open_btn.clicked.connect(self.open_output_folder)
        folder_layout.addWidget(output_open_btn, 1, 3)
        
        # Opciones de conversión
        options_group = QGroupBox("Opciones")
        right_layout.addWidget(options_group)
        
        options_layout = QVBoxLayout(options_group)
        
        # Búsqueda recursiva
        self.recursive_checkbox = QCheckBox("Incluir subcarpetas (búsqueda recursiva)")
        self.recursive_checkbox.setChecked(True)
        self.recursive_checkbox.stateChanged.connect(self.on_recursive_changed)
        options_layout.addWidget(self.recursive_checkbox)
        
        # Sobrescribir archivos existentes
        self.overwrite_checkbox = QCheckBox("Sobrescribir archivos existentes")
        self.overwrite_checkbox.setChecked(False)
        options_layout.addWidget(self.overwrite_checkbox)
        
        # Formato de salida seleccionado (vista rápida)
        format_layout = QHBoxLayout()
        format_layout.addWidget(QLabel("Formato de salida:"))
        self.output_format_combo = QComboBox()
        for fmt in self.audio_formats:
            self.output_format_combo.addItem(fmt['name'], fmt['id'])
        format_layout.addWidget(self.output_format_combo)
        options_layout.addLayout(format_layout)
        
        # Botones de acción
        actions_layout = QHBoxLayout()
        right_layout.addLayout(actions_layout)
        
        self.scan_button = QPushButton("Escanear Carpeta")
        self.scan_button.clicked.connect(self.scan_files)
        actions_layout.addWidget(self.scan_button)
        
        self.start_button = QPushButton("Iniciar Conversión")
        self.start_button.clicked.connect(self.start_conversion)
        self.start_button.setEnabled(False)
        actions_layout.addWidget(self.start_button)
        
        self.stop_button = QPushButton("Detener")
        self.stop_button.clicked.connect(self.stop_conversion)
        self.stop_button.setEnabled(False)
        actions_layout.addWidget(self.stop_button)
        
        # Barra de progreso
        self.progress_bar = QProgressBar()
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setValue(0)
        right_layout.addWidget(self.progress_bar)
        
        # Registro de actividad
        log_group = QGroupBox("Registro de actividad")
        right_layout.addWidget(log_group)
        
        log_layout = QVBoxLayout(log_group)
        
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setFont(QFont("Consolas", 9))
        log_layout.addWidget(self.log_text)
        
        # Añadir los paneles al splitter
        splitter.addWidget(left_panel)
        splitter.addWidget(right_panel)
        
        # Establecer tamaños iniciales del splitter
        splitter.setSizes([300, 700])
    
    def setup_formats_tab(self, tab):
        """Configura la pestaña de formatos"""
        layout = QVBoxLayout(tab)
        
        # Grupo de formatos
        formats_group = QGroupBox("Seleccione los formatos de video a buscar")
        layout.addWidget(formats_group)
        
        formats_layout = QGridLayout(formats_group)
        
        # Checkboxes para cada formato
        col_count = 4  # Número de columnas
        for i, fmt in enumerate(sorted(self.video_formats)):
            row = i // col_count
            col = i % col_count
            
            checkbox = QCheckBox(fmt)
            checkbox.setChecked(True)
            formats_layout.addWidget(checkbox, row, col)
            
            # Guardar referencia al checkbox
            self.format_checkboxes[fmt] = checkbox
        
        # Botones para seleccionar/deseleccionar todos
        buttons_layout = QHBoxLayout()
        layout.addLayout(buttons_layout)
        
        select_all_btn = QPushButton("Seleccionar Todos")
        select_all_btn.clicked.connect(lambda: self.select_all_formats(True))
        buttons_layout.addWidget(select_all_btn)
        
        deselect_all_btn = QPushButton("Deseleccionar Todos")
        deselect_all_btn.clicked.connect(lambda: self.select_all_formats(False))
        buttons_layout.addWidget(deselect_all_btn)
        
        # Espaciador para empujar todo hacia arriba
        layout.addStretch()
    
    def setup_audio_tab(self, tab):
        """Configura la pestaña de configuración de audio"""
        layout = QVBoxLayout(tab)
        
        # Grupo de formato de salida
        format_group = QGroupBox("Formato de Audio de Salida")
        layout.addWidget(format_group)
        
        format_layout = QVBoxLayout(format_group)
        
        # Descripción
        format_layout.addWidget(QLabel("Seleccione el formato de audio que desea generar:"))
        
        # Lista de formatos con RadioButtons
        self.format_radio_group = QButtonGroup(self)
        
        for i, fmt in enumerate(self.audio_formats):
            radio = QRadioButton(fmt['name'])
            if i == 0:  # Seleccionar WAV por defecto
                radio.setChecked(True)
            self.format_radio_group.addButton(radio, i)
            format_layout.addWidget(radio)
        
        # Conectar cambio de radio button a actualización del combobox en la pestaña principal
        self.format_radio_group.buttonClicked.connect(self.on_audio_format_changed)
        
        # Grupo de calidad de audio
        self.quality_group = QGroupBox("Calidad de Audio")
        layout.addWidget(self.quality_group)
        
        quality_layout = QVBoxLayout(self.quality_group)
        
        quality_layout.addWidget(QLabel("Seleccione el nivel de calidad:"))
        
        # Slider para calidad
        self.quality_slider = QSlider(Qt.Horizontal)
        self.quality_slider.setMinimum(0)
        self.quality_slider.setMaximum(4)
        self.quality_slider.setValue(2)  # Valor medio por defecto
        self.quality_slider.setTickPosition(QSlider.TicksBelow)
        self.quality_slider.setTickInterval(1)
        quality_layout.addWidget(self.quality_slider)
        
        # Etiquetas para el slider
        slider_labels_layout = QHBoxLayout()
        slider_labels_layout.addWidget(QLabel("Mejor calidad\n(archivo más grande)"), 1)
        slider_labels_layout.addStretch(3)
        slider_labels_layout.addWidget(QLabel("Menor calidad\n(archivo más pequeño)"), 1)
        quality_layout.addLayout(slider_labels_layout)
        
        # Información sobre formatos
        info_group = QGroupBox("Información sobre Formatos")
        layout.addWidget(info_group)
        
        info_layout = QVBoxLayout(info_group)
        
        info_text = QLabel(
            "<b>WAV:</b> Sin compresión, calidad de CD (44.1kHz, estéreo). No utiliza compresión, por lo que no aplica el control de calidad.<br>"
            "<b>WAV para transcripción de voz:</b> Optimizado para reconocimiento de voz (16kHz, mono). Ideal para servicios como Whisper, Google Speech, etc. Archivos más pequeños que WAV estándar.<br>"
            "<b>MP3:</b> Compresión con pérdida, compatible con prácticamente todo. El control de calidad afecta al bitrate.<br>"
            "<b>OGG:</b> Formato libre, mejor calidad que MP3 a mismo tamaño. El control de calidad afecta al nivel de compresión.<br>"
            "<b>FLAC:</b> Compresión sin pérdida, calidad perfecta, archivo más pequeño que WAV. El control de calidad afecta solo al nivel de compresión, no a la calidad de audio.<br>"
            "<b>AAC:</b> Mejor calidad que MP3 a mismo bitrate. Usado en iTunes. El control de calidad afecta al bitrate.<br>"
            "<b>M4A:</b> Contenedor para AAC, usado en ecosistema Apple. El control de calidad afecta al bitrate.<br>"
            "<b>Opus:</b> Formato más nuevo, excelente calidad a bitrates bajos. El control de calidad afecta al bitrate.<br>"
            "<b>WMA:</b> Formato de Microsoft, buena compatibilidad en Windows. El control de calidad afecta al bitrate."
        )
        info_text.setTextFormat(Qt.RichText)
        info_text.setWordWrap(True)
        info_layout.addWidget(info_text)
        
        # Verificar estado inicial del slider de calidad
        self.update_quality_slider_visibility()
        
        # Espaciador
        layout.addStretch()
    
    def on_audio_format_changed(self, button):
        """Actualiza el combobox cuando cambia el formato en la pestaña de audio"""
        index = self.format_radio_group.id(button)
        self.output_format_combo.setCurrentIndex(index)
        
        # Actualizar visibilidad del slider de calidad
        self.update_quality_slider_visibility()
    
    def select_input_folder(self):
        """Selecciona la carpeta de entrada"""
        folder = QFileDialog.getExistingDirectory(self, "Seleccionar Carpeta de Entrada")
        if folder:
            self.input_folder = folder
            self.input_folder_label.setText(folder)
            self.log_message(f"📁 Carpeta de entrada: {folder}")
            
            # Si no hay carpeta de salida, usar la misma
            if not self.output_folder:
                self.output_folder = folder
                self.output_folder_label.setText(folder)
                
            # Limpiar el registro si hay demasiadas entradas
            if self.log_text.document().lineCount() > 200:
                self.log_text.clear()
                self.log_message("🔄 Registro limpiado por rendimiento")
                self.log_message(f"📁 Carpeta de entrada: {folder}")
            
            # Actualizar el árbol de carpetas y buscar archivos
            self.scan_files()
    
    def browse_output_folder(self):
        """Abre un diálogo para seleccionar la carpeta de salida"""
        folder = QFileDialog.getExistingDirectory(self, "Seleccionar Carpeta de Salida")
        if folder:
            self.output_folder = folder
            self.output_folder_label.setText(folder)
            self.log_message(f"📁 Carpeta de salida: {folder}")
    
    def log_message(self, message):
        """Agrega un mensaje al área de registro"""
        self.log_text.append(message)
        # Desplazar al final
        cursor = self.log_text.textCursor()
        cursor.movePosition(QTextCursor.End)
        self.log_text.setTextCursor(cursor)
    
    def on_recursive_changed(self, state):
        """Maneja el cambio en la opción de búsqueda recursiva"""
        if self.input_folder:
            # Actualizar árbol según el nuevo estado
            self.update_folder_tree()
            self.scan_files()
    
    def select_all_formats(self, select):
        """Selecciona o deselecciona todos los formatos de video"""
        for checkbox in self.format_checkboxes.values():
            checkbox.setChecked(select)
        
        if select:
            self.log_message("Se han seleccionado todos los formatos de video")
        else:
            self.log_message("Se han deseleccionado todos los formatos de video")
    
    def get_selected_formats(self):
        """Obtiene los formatos de video seleccionados"""
        return [fmt for fmt, checkbox in self.format_checkboxes.items() if checkbox.isChecked()]
    
    def on_tree_item_changed(self, item, column):
        """Maneja el cambio de estado de selección de un elemento del árbol"""
        if column == 0:
            # Solo registrar cambios en elementos de archivo, no en carpetas
            if item.data(0, Qt.UserRole) in self.file_items:
                check_state = item.checkState(0)
                if check_state == Qt.Checked:
                    self.log_message(f"Seleccionado: {item.text(0)}")
                elif check_state == Qt.Unchecked:
                    self.log_message(f"Deseleccionado: {item.text(0)}")
    
    def select_all_items(self):
        """Selecciona todos los elementos del árbol"""
        root = self.folder_tree.invisibleRootItem()
        for i in range(root.childCount()):
            item = root.child(i)
            item.setCheckState(0, Qt.Checked)
        self.log_message("Se han seleccionado todos los elementos")
        
    def deselect_all_items(self):
        """Deselecciona todos los elementos del árbol"""
        root = self.folder_tree.invisibleRootItem()
        for i in range(root.childCount()):
            item = root.child(i)
            item.setCheckState(0, Qt.Unchecked)
        self.log_message("Se han deseleccionado todos los elementos")
    
    def update_folder_tree(self):
        """Actualiza el árbol de carpetas con la estructura de la carpeta seleccionada"""
        self.folder_tree.clear()
        self.folder_items = {}
        self.file_items = {}
        
        if not self.input_folder:
            return
            
        # Crear elemento raíz
        root_path = self.input_folder
        root_name = os.path.basename(root_path) or root_path
        root_item = QTreeWidgetItem(self.folder_tree)
        root_item.setText(0, root_name)
        root_item.setIcon(0, self.style().standardIcon(QStyle.SP_DirIcon))
        root_item.setData(0, Qt.UserRole, root_path)
        root_item.setFlags(root_item.flags() | Qt.ItemIsUserCheckable | Qt.ItemIsAutoTristate)
        root_item.setCheckState(0, Qt.Checked)
        
        self.folder_items[root_path] = root_item
        
        # Si la búsqueda es recursiva, usar scan_subfolders que ya escanea la carpeta actual
        if self.recursive_checkbox.isChecked():
            self.scan_subfolders(root_path, root_item)
        else:
            # Si no es recursiva, sólo escanear la carpeta raíz
            self.scan_files_in_folder(root_path, root_item)
            
        # Expandir elemento raíz
        root_item.setExpanded(True)
    
    def scan_subfolders(self, parent_path, parent_item):
        """Escanea las subcarpetas de forma recursiva"""
        try:
            # Primero agregar los archivos de la carpeta actual
            self.scan_files_in_folder(parent_path, parent_item)
            
            # Luego procesar subcarpetas
            for entry in os.scandir(parent_path):
                if entry.is_dir():
                    child_path = entry.path
                    child_name = os.path.basename(child_path)
                    
                    # Crear elemento hijo
                    child_item = QTreeWidgetItem(parent_item)
                    child_item.setText(0, child_name)
                    child_item.setIcon(0, self.style().standardIcon(QStyle.SP_DirIcon))
                    child_item.setData(0, Qt.UserRole, child_path)
                    child_item.setFlags(child_item.flags() | Qt.ItemIsUserCheckable | Qt.ItemIsAutoTristate)
                    child_item.setCheckState(0, Qt.Checked)
                    
                    self.folder_items[child_path] = child_item
                    
                    # Continuar escaneando de forma recursiva
                    self.scan_subfolders(child_path, child_item)
        except Exception as e:
            self.log_message(f"⚠️ Error al escanear subcarpetas: {str(e)}")
    
    def scan_files_in_folder(self, folder_path, parent_item):
        """Escanea y agrega archivos de video a la carpeta especificada en el árbol"""
        try:
            # Obtener formatos de video seleccionados
            selected_formats = self.get_selected_formats()
            
            # Escanear archivos en la carpeta
            for entry in os.scandir(folder_path):
                if entry.is_file():
                    file_path = entry.path
                    file_name = os.path.basename(file_path)
                    ext = os.path.splitext(file_name)[1].lower()
                    
                    # Verificar si es un formato de video seleccionado
                    if ext in selected_formats:
                        # Crear elemento de archivo
                        file_item = QTreeWidgetItem(parent_item)
                        file_item.setText(0, file_name)
                        file_item.setIcon(0, self.style().standardIcon(QStyle.SP_FileIcon))
                        file_item.setData(0, Qt.UserRole, file_path)
                        file_item.setFlags(file_item.flags() | Qt.ItemIsUserCheckable)
                        file_item.setCheckState(0, Qt.Checked)
                        
                        # Guardar referencia al elemento de archivo
                        self.file_items[file_path] = file_item
        except Exception as e:
            self.log_message(f"⚠️ Error al escanear archivos: {str(e)}")
    
    def get_selected_items(self):
        """Obtiene las carpetas y archivos seleccionados en el árbol"""
        result = {
            'folders': [],
            'files': []
        }
        
        # Recorrer elementos de carpeta
        for folder_path, item in self.folder_items.items():
            if item.checkState(0) == Qt.Checked:
                result['folders'].append(folder_path)
        
        # Recorrer elementos de archivo
        for file_path, item in self.file_items.items():
            if item.checkState(0) == Qt.Checked:
                result['files'].append(file_path)
        
        return result
    
    def scan_files(self):
        """Busca archivos de video en la carpeta de entrada"""
        if not self.input_folder:
            return
            
        # Obtener formatos seleccionados
        selected_formats = self.get_selected_formats()
        
        try:
            # Actualizar árbol de carpetas (esto ya escanea los archivos)
            self.update_folder_tree()
            
            # Contar archivos usando las selecciones actuales
            selected_items = self.get_selected_items()
            total_files = len(selected_items['files'])
            
            # Mostrar resultados
            if total_files > 0:
                plural = "s" if total_files > 1 else ""
                self.log_message(f"🔍 Se encontraron {total_files} archivo{plural} de video.")
                self.start_button.setEnabled(True)
            else:
                self.log_message("⚠️ No se encontraron archivos de video.")
                self.start_button.setEnabled(False)
                
        except Exception as e:
            self.log_message(f"❌ Error al buscar archivos: {str(e)}")
            self.start_button.setEnabled(False)
    
    def check_ffmpeg(self):
        """Verifica si ffmpeg está instalado en el sistema"""
        try:
            subprocess.run(['ffmpeg', '-version'], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            self.log_message("✅ ffmpeg detectado correctamente.")
            return True
        except FileNotFoundError:
            self.log_message("❌ Error: ffmpeg no está instalado o no está en el PATH.")
            QMessageBox.critical(self, "Error", "ffmpeg no está instalado o no está en el PATH.\n"
                               "Por favor, instala ffmpeg y asegúrate de que esté en el PATH.")
            return False
    
    def start_conversion(self):
        """Inicia el proceso de conversión de archivos"""
        if not self.check_ffmpeg():
            return
            
        if self.conversion_running:
            return
            
        if not self.input_folder:
            QMessageBox.warning(self, "Advertencia", "Por favor, seleccione una carpeta de entrada")
            return
            
        # Obtener formatos seleccionados
        selected_formats = self.get_selected_formats()
        if not selected_formats:
            QMessageBox.warning(self, "Advertencia", "No hay formatos de video seleccionados para convertir")
            return
        
        # Obtener elementos seleccionados
        selected_items = self.get_selected_items()
        
        # Verificar si hay archivos o carpetas seleccionadas
        if not selected_items['folders'] and not selected_items['files']:
            QMessageBox.warning(self, "Advertencia", "No hay carpetas ni archivos seleccionados para convertir")
            return
        
        # Obtener formato de audio seleccionado
        output_format = self.output_format_combo.currentData()
        if not output_format:
            # Si no hay formato seleccionado, usar WAV como predeterminado
            output_format = 'wav'
            self.log_message("⚠️ No se pudo obtener el formato de salida, usando WAV por defecto")
        
        # Obtener nivel de calidad
        audio_quality = self.quality_slider.value()
        
        # Cambiar estado de la interfaz
        self.conversion_running = True
        self.start_button.setEnabled(False)
        self.stop_button.setEnabled(True)
        
        # Resetear barra de progreso
        self.progress_bar.setValue(0)
        
        # Iniciar hilo de conversión
        self.worker_thread = FFmpegWorker(
            self.input_folder, 
            self.output_folder, 
            selected_items, 
            selected_formats, 
            self.recursive_checkbox.isChecked(), 
            self.overwrite_checkbox.isChecked(),
            output_format,
            audio_quality
        )
        
        # Conectar señales
        self.worker_thread.progress_updated.connect(self.update_progress)
        self.worker_thread.conversion_finished.connect(self.conversion_finished)
        self.worker_thread.log_message.connect(self.log_message)
        
        # Iniciar hilo
        self.worker_thread.start()
    
    def stop_conversion(self):
        """Detiene el proceso de conversión"""
        if self.worker_thread and self.worker_thread.isRunning():
            self.worker_thread.stop_requested = True
            self.log_message("⏹️ Deteniendo el proceso de conversión...")
            self.stop_button.setEnabled(False)
    
    def update_progress(self, current, total):
        """Actualiza la barra de progreso"""
        self.progress_bar.setMaximum(total)
        self.progress_bar.setValue(current)
        self.progress_bar.setFormat(f"{current}/{total} ({int(current/total*100)}%)")
    
    def conversion_finished(self):
        """Maneja el evento de finalización de la conversión"""
        self.conversion_running = False
        self.start_button.setEnabled(True)
        self.stop_button.setEnabled(False)
        self.progress_bar.setValue(self.progress_bar.maximum())
        
        # Reproducir sonido de notificación si está disponible
        try:
            QApplication.beep()
        except:
            pass
            
        self.log_message("✅ Proceso de conversión finalizado")
        
        # Preguntar si quiere abrir la carpeta de salida
        if self.output_folder and os.path.exists(self.output_folder):
            reply = QMessageBox.question(
                self, 
                "Conversión Completada", 
                "El proceso de conversión ha finalizado. ¿Desea abrir la carpeta de salida?",
                QMessageBox.Yes | QMessageBox.No, 
                QMessageBox.Yes
            )
            
            if reply == QMessageBox.Yes:
                self.open_output_folder()
        else:
            QMessageBox.information(self, "Conversión Completada", "El proceso de conversión ha finalizado.")

    def on_output_format_changed(self, index):
        """Actualiza los radio buttons cuando cambia el formato en el combobox"""
        if hasattr(self, 'format_radio_group'):
            button = self.format_radio_group.button(index)
            if button:
                button.setChecked(True)
                
        # Actualizar visibilidad del slider de calidad
        self.update_quality_slider_visibility()

    def update_quality_slider_visibility(self):
        """Actualiza la visibilidad del slider de calidad según el formato seleccionado"""
        if hasattr(self, 'quality_group') and hasattr(self, 'output_format_combo'):
            current_format = self.output_format_combo.currentData()
            
            # Ocultar slider para formatos donde no aplica
            if current_format in ['wav', 'wav_voice']:
                self.quality_group.setVisible(False)
            else:
                self.quality_group.setVisible(True)

    def open_input_folder(self):
        """Abre la carpeta de entrada en el explorador de archivos"""
        if self.input_folder and os.path.exists(self.input_folder):
            self.open_folder_in_explorer(self.input_folder)
        else:
            QMessageBox.warning(self, "Advertencia", "No hay carpeta de entrada seleccionada o no existe")

    def open_output_folder(self):
        """Abre la carpeta de salida en el explorador de archivos"""
        if self.output_folder and os.path.exists(self.output_folder):
            self.open_folder_in_explorer(self.output_folder)
        else:
            QMessageBox.warning(self, "Advertencia", "No hay carpeta de salida seleccionada o no existe")

    def open_folder_in_explorer(self, folder_path):
        """Abre una carpeta en el explorador de archivos del sistema"""
        try:
            if sys.platform == 'win32':
                os.startfile(folder_path)
            elif sys.platform == 'darwin':  # macOS
                subprocess.run(['open', folder_path])
            else:  # Linux y otros
                subprocess.run(['xdg-open', folder_path])
            self.log_message(f"📂 Abriendo carpeta: {folder_path}")
        except Exception as e:
            self.log_message(f"❌ Error al abrir la carpeta: {str(e)}")
            QMessageBox.warning(self, "Error", f"No se pudo abrir la carpeta: {str(e)}")


def main():
    app = QApplication(sys.argv)
    window = VidToWav()
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main() 