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
                            QGroupBox, QGridLayout, QSplitter)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QSize
from PyQt5.QtGui import QIcon, QTextCursor, QFont


class FFmpegWorker(QThread):
    """Hilo de trabajo para la conversión de archivos con ffmpeg"""
    # Señales
    progress_updated = pyqtSignal(int, int)  # Actualizar progreso (actual, total)
    conversion_finished = pyqtSignal()  # Conversión terminada
    log_message = pyqtSignal(str)  # Mensaje de registro
    
    def __init__(self, input_path, output_path, selected_folders, selected_formats, 
                 recursive, overwrite_existing):
        super().__init__()
        self.input_path = input_path
        self.output_path = output_path
        self.selected_folders = selected_folders
        self.selected_formats = selected_formats
        self.recursive = recursive
        self.overwrite_existing = overwrite_existing
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
            if not self.output_path:
                # Si no se especificó carpeta de salida, usar la misma que el archivo original
                output_file = video_file.with_suffix('.wav')
            else:
                # Calcular ruta de salida preservando la estructura de carpetas
                rel_path = video_file.relative_to(self.input_path) if video_file.is_relative_to(self.input_path) else Path(video_file.name)
                output_file = Path(self.output_path) / rel_path.with_suffix('.wav')
                
                # Crear directorio de salida si no existe
                os.makedirs(output_file.parent, exist_ok=True)
            
            # Verificar si el archivo WAV ya existe
            if output_file.exists() and not self.overwrite_existing:
                self.log_message.emit(f"⏭️ Omitido: {video_file.name} (Ya existe)")
                skipped += 1
            else:
                self.log_message.emit(f"🔄 Convirtiendo: {video_file.name}")
                success = self.convert_to_wav(str(video_file), str(output_file))
                
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
    
    def stop(self):
        """Detiene la ejecución del hilo"""
        self.stop_requested = True

    def find_video_files(self):
        """Encuentra archivos de video según los filtros seleccionados."""
        video_files = []
        
        # Si no hay carpetas seleccionadas, usar solo la carpeta base
        folders_to_search = self.selected_folders if self.selected_folders else [self.input_path]
        
        # Buscar en cada carpeta seleccionada
        for folder in folders_to_search:
            # Verificar si la carpeta existe
            if not os.path.exists(folder):
                continue
                
            # Si la búsqueda es recursiva
            if self.recursive:
                for root, _, files in os.walk(folder):
                    for file in files:
                        ext = os.path.splitext(file)[1].lower()
                        if ext in self.selected_formats:
                            video_files.append(os.path.join(root, file))
            # Si la búsqueda no es recursiva, solo buscar en la carpeta actual
            else:
                for file in os.listdir(folder):
                    file_path = os.path.join(folder, file)
                    if os.path.isfile(file_path):
                        ext = os.path.splitext(file)[1].lower()
                        if ext in self.selected_formats:
                            video_files.append(file_path)
        
        return [Path(file) for file in video_files]
    
    def convert_to_wav(self, input_file, output_file):
        """Convierte un archivo de video a WAV optimizado para Whisper."""
        try:
            result = subprocess.run(
                ['ffmpeg', '-i', input_file, '-vn', '-acodec', 'pcm_s16le', 
                 '-ar', '16000', '-ac', '1', output_file, 
                 '-y' if self.overwrite_existing else '-n',
                 '-hide_banner', '-loglevel', 'warning'],
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


class MP4ToWAVConverterApp(QMainWindow):
    """Aplicación principal para convertir archivos de video a WAV"""
    def __init__(self):
        super().__init__()
        
        # Configuración de la ventana principal
        self.setWindowTitle("Convertidor de Video a WAV")
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
        
        # Variables para los checkboxes de formatos
        self.format_checkboxes = {}
        
        # Variables para el árbol de carpetas
        self.folder_items = {}  # Para acceder rápidamente a los elementos del árbol
        
        # Configuración de la interfaz
        self.setup_ui()
        
        # Verificar ffmpeg al inicio
        QApplication.processEvents()
        self.check_ffmpeg()
    
    def setup_ui(self):
        """Configura la interfaz gráfica de usuario"""
        # Widget central
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # Layout principal
        main_layout = QVBoxLayout(central_widget)
        
        # Crear pestañas
        self.tab_widget = QTabWidget()
        main_layout.addWidget(self.tab_widget)
        
        # Pestaña principal
        main_tab = QWidget()
        self.tab_widget.addTab(main_tab, "Principal")
        
        # Pestaña de filtros
        filters_tab = QWidget()
        self.tab_widget.addTab(filters_tab, "Filtros de Formato")
        
        # Pestaña de carpetas
        folders_tab = QWidget()
        self.tab_widget.addTab(folders_tab, "Selección de Carpetas")
        
        # Configurar cada pestaña
        self.setup_main_tab(main_tab)
        self.setup_filters_tab(filters_tab)
        self.setup_folders_tab(folders_tab)
    
    def setup_main_tab(self, tab):
        """Configura la pestaña principal"""
        layout = QVBoxLayout(tab)
        
        # Grupo de selección de carpetas
        folder_group = QGroupBox("Selección de Carpetas")
        layout.addWidget(folder_group)
        
        folder_layout = QGridLayout(folder_group)
        
        # Carpeta de entrada
        folder_layout.addWidget(QLabel("Carpeta de Entrada:"), 0, 0)
        self.input_folder_label = QLabel("")
        self.input_folder_label.setStyleSheet("background-color: white; padding: 5px; border: 1px solid #ccc;")
        folder_layout.addWidget(self.input_folder_label, 0, 1)
        
        input_browse_btn = QPushButton("Explorar...")
        input_browse_btn.clicked.connect(self.browse_input_folder)
        folder_layout.addWidget(input_browse_btn, 0, 2)
        
        # Carpeta de salida
        folder_layout.addWidget(QLabel("Carpeta de Salida:"), 1, 0)
        self.output_folder_label = QLabel("")
        self.output_folder_label.setStyleSheet("background-color: white; padding: 5px; border: 1px solid #ccc;")
        folder_layout.addWidget(self.output_folder_label, 1, 1)
        
        output_browse_btn = QPushButton("Explorar...")
        output_browse_btn.clicked.connect(self.browse_output_folder)
        folder_layout.addWidget(output_browse_btn, 1, 2)
        
        # Grupo de opciones
        options_group = QGroupBox("Opciones")
        layout.addWidget(options_group)
        
        options_layout = QVBoxLayout(options_group)
        
        # Opciones con checkboxes
        self.recursive_checkbox = QCheckBox("Buscar en subcarpetas")
        self.recursive_checkbox.setChecked(True)
        self.recursive_checkbox.stateChanged.connect(self.on_recursive_changed)
        options_layout.addWidget(self.recursive_checkbox)
        
        self.overwrite_checkbox = QCheckBox("Sobrescribir archivos existentes")
        options_layout.addWidget(self.overwrite_checkbox)
        
        # Botón de escaneo
        scan_btn = QPushButton("Escanear Archivos")
        scan_btn.clicked.connect(self.scan_files)
        options_layout.addWidget(scan_btn)
        
        # Grupo de botones de acción
        actions_layout = QHBoxLayout()
        layout.addLayout(actions_layout)
        
        self.start_button = QPushButton("Iniciar Conversión")
        self.start_button.clicked.connect(self.start_conversion)
        actions_layout.addWidget(self.start_button)
        
        self.stop_button = QPushButton("Detener Conversión")
        self.stop_button.clicked.connect(self.stop_conversion)
        self.stop_button.setEnabled(False)
        actions_layout.addWidget(self.stop_button)
        
        # Barra de progreso
        progress_group = QGroupBox("Progreso")
        layout.addWidget(progress_group)
        
        progress_layout = QVBoxLayout(progress_group)
        
        self.progress_bar = QProgressBar()
        progress_layout.addWidget(self.progress_bar)
        
        # Área de registro
        log_group = QGroupBox("Registro")
        layout.addWidget(log_group, 1)  # 1 para que se expanda
        
        log_layout = QVBoxLayout(log_group)
        
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        log_layout.addWidget(self.log_text)
    
    def setup_filters_tab(self, tab):
        """Configura la pestaña de filtros de formato"""
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
    
    def setup_folders_tab(self, tab):
        """Configura la pestaña de selección de carpetas"""
        layout = QVBoxLayout(tab)
        
        # Grupo de árbol de carpetas
        tree_group = QGroupBox("Carpetas y subcarpetas con videos")
        layout.addWidget(tree_group)
        
        tree_layout = QVBoxLayout(tree_group)
        
        # Árbol de carpetas
        self.folder_tree = QTreeWidget()
        self.folder_tree.setHeaderLabels(["Carpeta", "Ruta"])
        self.folder_tree.setColumnWidth(0, 300)  # Ancho de la primera columna
        self.folder_tree.itemChanged.connect(self.on_folder_item_changed)
        tree_layout.addWidget(self.folder_tree)
        
        # Botones para seleccionar/deseleccionar carpetas
        buttons_layout = QHBoxLayout()
        layout.addLayout(buttons_layout)
        
        select_all_btn = QPushButton("Seleccionar Todas")
        select_all_btn.clicked.connect(self.select_all_folders)
        buttons_layout.addWidget(select_all_btn)
        
        deselect_all_btn = QPushButton("Deseleccionar Todas")
        deselect_all_btn.clicked.connect(self.deselect_all_folders)
        buttons_layout.addWidget(deselect_all_btn)
    
    def browse_input_folder(self):
        """Abre un diálogo para seleccionar la carpeta de entrada"""
        folder = QFileDialog.getExistingDirectory(self, "Seleccionar Carpeta de Entrada")
        if folder:
            self.input_folder = folder
            self.input_folder_label.setText(folder)
            self.log_message(f"Carpeta de entrada seleccionada: {folder}")
    
    def browse_output_folder(self):
        """Abre un diálogo para seleccionar la carpeta de salida"""
        folder = QFileDialog.getExistingDirectory(self, "Seleccionar Carpeta de Salida")
        if folder:
            self.output_folder = folder
            self.output_folder_label.setText(folder)
            self.log_message(f"Carpeta de salida seleccionada: {folder}")
    
    def log_message(self, message):
        """Agrega un mensaje al área de registro"""
        self.log_text.append(message)
        # Desplazar al final
        cursor = self.log_text.textCursor()
        cursor.movePosition(QTextCursor.End)
        self.log_text.setTextCursor(cursor)
    
    def on_recursive_changed(self):
        """Maneja el cambio en la opción de búsqueda recursiva"""
        if self.recursive_checkbox.isChecked():
            self.log_message("Búsqueda recursiva activada. Use la pestaña 'Selección de Carpetas' para filtrar subcarpetas")
        else:
            self.log_message("Búsqueda recursiva desactivada. Solo se buscará en la carpeta principal")
    
    def select_all_formats(self, select):
        """Selecciona o deselecciona todos los formatos de video"""
        for checkbox in self.format_checkboxes.values():
            checkbox.setChecked(select)
        
        if select:
            self.log_message("Se han seleccionado todos los formatos de video")
        else:
            self.log_message("Se han deseleccionado todos los formatos de video")
    
    def get_selected_formats(self):
        """Obtiene la lista de formatos de video seleccionados"""
        return [fmt for fmt, checkbox in self.format_checkboxes.items() if checkbox.isChecked()]
    
    def on_folder_item_changed(self, item, column):
        """Maneja el cambio en un ítem del árbol de carpetas"""
        # Solo procesar cambios en la primera columna (checkbox)
        if column != 0:
            return
        
        # Obtener el nuevo estado de selección
        is_checked = item.checkState(0) == Qt.Checked
        
        # Propagar el cambio a todos los elementos hijos
        self.apply_check_state_to_children(item, is_checked)
    
    def apply_check_state_to_children(self, parent_item, checked):
        """Aplica el mismo estado a todos los hijos de un elemento"""
        # Configurar el estado de los hijos
        check_state = Qt.Checked if checked else Qt.Unchecked
        
        # Recorrer todos los hijos
        for i in range(parent_item.childCount()):
            child = parent_item.child(i)
            child.setCheckState(0, check_state)
            
            # Aplicar recursivamente a los hijos de este hijo
            self.apply_check_state_to_children(child, checked)
    
    def select_all_folders(self):
        """Selecciona todas las carpetas en el árbol"""
        root = self.folder_tree.invisibleRootItem()
        for i in range(root.childCount()):
            item = root.child(i)
            item.setCheckState(0, Qt.Checked)
        
        self.log_message("Se han seleccionado todas las carpetas")
    
    def deselect_all_folders(self):
        """Deselecciona todas las carpetas en el árbol"""
        root = self.folder_tree.invisibleRootItem()
        for i in range(root.childCount()):
            item = root.child(i)
            item.setCheckState(0, Qt.Unchecked)
        
        self.log_message("Se han deseleccionado todas las carpetas")
    
    def update_folder_tree(self, base_path):
        """Actualiza el árbol de carpetas con la estructura de directorios"""
        # Limpiar el árbol existente
        self.folder_tree.clear()
        self.folder_items = {}
        
        # Obtener el nombre de la carpeta base
        base_name = os.path.basename(base_path)
        
        # Crear elemento raíz
        root_item = QTreeWidgetItem(self.folder_tree)
        root_item.setText(0, base_name)
        root_item.setText(1, base_path)
        root_item.setCheckState(0, Qt.Checked)
        
        # Guardar referencia al ítem
        self.folder_items[base_path] = root_item
        
        # Si la búsqueda recursiva está activa, añadir subcarpetas
        if self.recursive_checkbox.isChecked():
            self.scan_subfolders(base_path, root_item)
        
        # Expandir el primer nivel
        root_item.setExpanded(True)
    
    def scan_subfolders(self, parent_path, parent_item):
        """Escanea subcarpetas y las añade al árbol"""
        try:
            # Obtener todas las subcarpetas
            for entry in os.scandir(parent_path):
                if entry.is_dir():
                    # Crear elemento para esta subcarpeta
                    folder_item = QTreeWidgetItem(parent_item)
                    folder_item.setText(0, entry.name)
                    folder_item.setText(1, entry.path)
                    folder_item.setCheckState(0, Qt.Checked)
                    
                    # Guardar referencia al ítem
                    self.folder_items[entry.path] = folder_item
                    
                    # Escanear recursivamente
                    self.scan_subfolders(entry.path, folder_item)
        except Exception as e:
            self.log_message(f"Error al escanear subcarpetas: {str(e)}")
    
    def get_selected_folders(self):
        """Obtiene la lista de carpetas seleccionadas en el árbol"""
        selected_folders = []
        
        # Si no hay elementos en el árbol, devolver lista vacía
        if not self.folder_items:
            return selected_folders
        
        # Recorrer todos los elementos del árbol
        for path, item in self.folder_items.items():
            if item.checkState(0) == Qt.Checked:
                selected_folders.append(path)
        
        return selected_folders
    
    def scan_files(self):
        """Escanea archivos de video en las carpetas seleccionadas"""
        if not self.input_folder:
            QMessageBox.warning(self, "Advertencia", "Por favor, seleccione una carpeta de entrada")
            return
        
        if not os.path.exists(self.input_folder):
            QMessageBox.critical(self, "Error", f"La carpeta {self.input_folder} no existe")
            return
        
        # Actualizar el árbol de carpetas
        self.update_folder_tree(self.input_folder)
        
        # Buscar archivos de video y contar por carpeta
        self.log_message(f"🔍 Escaneando {self.input_folder} en busca de archivos de video...")
        selected_formats = self.get_selected_formats()
        
        if not selected_formats:
            QMessageBox.warning(self, "Advertencia", "No hay formatos de video seleccionados para buscar")
            return
            
        self.log_message(f"Formatos seleccionados: {', '.join(selected_formats)}")
        
        # Verificar recursividad
        if self.recursive_checkbox.isChecked():
            self.log_message("Buscando en todas las subcarpetas...")
        else:
            self.log_message("Buscando solo en la carpeta principal...")
        
        # Iniciar escaneo en un hilo para no bloquear la interfaz
        self.scanner_thread = FolderScannerThread(self.input_folder, selected_formats, self.recursive_checkbox.isChecked())
        self.scanner_thread.scan_complete.connect(self.show_scan_results)
        self.scanner_thread.log_message.connect(self.log_message)
        self.scanner_thread.start()
    
    def show_scan_results(self, folder_counts, total_files, folders_with_videos):
        """Muestra los resultados del escaneo de archivos"""
        self.log_message("\n=== Resultados del Escaneo ===")
        self.log_message(f"Total de archivos de video encontrados: {total_files}")
        self.log_message(f"Carpetas con videos: {folders_with_videos}")
        
        if folder_counts:
            self.log_message("\nDistribución de archivos:")
            for folder, count in folder_counts.items():
                self.log_message(f"  • {folder}: {count} archivos")
        else:
            self.log_message("No se encontraron archivos de video en las carpetas seleccionadas")
        
        self.log_message("=== Fin del Escaneo ===\n")
    
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
        
        # Obtener carpetas seleccionadas
        selected_folders = self.get_selected_folders()
        
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
            selected_folders, 
            selected_formats, 
            self.recursive_checkbox.isChecked(), 
            self.overwrite_checkbox.isChecked()
        )
        
        # Conectar señales
        self.worker_thread.progress_updated.connect(self.update_progress)
        self.worker_thread.conversion_finished.connect(self.conversion_finished)
        self.worker_thread.log_message.connect(self.log_message)
        
        # Iniciar hilo
        self.worker_thread.start()
    
    def stop_conversion(self):
        """Detiene el proceso de conversión"""
        if self.conversion_running and self.worker_thread:
            self.worker_thread.stop()
            self.log_message("⚠️ Solicitando detener la conversión...")
            self.stop_button.setEnabled(False)
    
    def update_progress(self, current, total):
        """Actualiza la barra de progreso"""
        percent = int((current / total) * 100)
        self.progress_bar.setValue(percent)
    
    def conversion_finished(self):
        """Maneja el final del proceso de conversión"""
        self.conversion_running = False
        self.start_button.setEnabled(True)
        self.stop_button.setEnabled(False)


def main():
    app = QApplication(sys.argv)
    window = MP4ToWAVConverterApp()
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main() 