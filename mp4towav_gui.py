import os
import subprocess
import time
import sys
import threading
import queue
from pathlib import Path
import tkinter as tk
from tkinter import ttk, filedialog, scrolledtext
from tkinter import messagebox

class MP4ToWAVConverter:
    def __init__(self, root):
        self.root = root
        self.root.title("Convertidor de Video a WAV")
        self.root.geometry("800x600")
        self.root.minsize(750, 500)
        
        self.input_folder = tk.StringVar()
        self.output_folder = tk.StringVar()
        self.recursive_search = tk.BooleanVar(value=True)
        self.overwrite_existing = tk.BooleanVar(value=False)
        
        self.conversion_running = False
        self.conversion_thread = None
        self.stop_conversion = False
        self.log_queue = queue.Queue()
        
        # Configuración de la interfaz
        self.setup_ui()
        
        # Verificar ffmpeg al inicio
        self.root.after(100, self.check_ffmpeg_startup)
        
        # Configurar la actualización de logs
        self.root.after(100, self.update_logs_from_queue)

    def setup_ui(self):
        # Marco principal
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Marco para selección de carpetas
        folder_frame = ttk.LabelFrame(main_frame, text="Selección de Carpetas", padding="10")
        folder_frame.pack(fill=tk.X, padx=5, pady=5)
        
        # Carpeta de entrada
        ttk.Label(folder_frame, text="Carpeta de Entrada:").grid(row=0, column=0, sticky=tk.W, pady=5)
        ttk.Entry(folder_frame, textvariable=self.input_folder, width=50).grid(row=0, column=1, padx=5, pady=5)
        ttk.Button(folder_frame, text="Explorar...", command=self.browse_input_folder).grid(row=0, column=2, padx=5, pady=5)
        
        # Carpeta de salida
        ttk.Label(folder_frame, text="Carpeta de Salida:").grid(row=1, column=0, sticky=tk.W, pady=5)
        ttk.Entry(folder_frame, textvariable=self.output_folder, width=50).grid(row=1, column=1, padx=5, pady=5)
        ttk.Button(folder_frame, text="Explorar...", command=self.browse_output_folder).grid(row=1, column=2, padx=5, pady=5)
        
        # Marco para opciones
        options_frame = ttk.LabelFrame(main_frame, text="Opciones", padding="10")
        options_frame.pack(fill=tk.X, padx=5, pady=5)
        
        # Opciones
        ttk.Checkbutton(options_frame, text="Buscar en subcarpetas", variable=self.recursive_search).pack(anchor=tk.W, pady=2)
        ttk.Checkbutton(options_frame, text="Sobrescribir archivos existentes", variable=self.overwrite_existing).pack(anchor=tk.W, pady=2)
        
        # Marco para botones de acción
        actions_frame = ttk.Frame(main_frame, padding="10")
        actions_frame.pack(fill=tk.X, padx=5, pady=5)
        
        # Botones de acción
        self.start_button = ttk.Button(actions_frame, text="Iniciar Conversión", command=self.start_conversion)
        self.start_button.pack(side=tk.LEFT, padx=5)
        
        self.stop_button = ttk.Button(actions_frame, text="Detener Conversión", command=self.stop_conversion_process, state=tk.DISABLED)
        self.stop_button.pack(side=tk.LEFT, padx=5)
        
        # Barra de progreso
        progress_frame = ttk.Frame(main_frame, padding="10")
        progress_frame.pack(fill=tk.X, padx=5, pady=5)
        
        ttk.Label(progress_frame, text="Progreso:").pack(anchor=tk.W, pady=2)
        self.progress_bar = ttk.Progressbar(progress_frame, orient=tk.HORIZONTAL, length=100, mode='determinate')
        self.progress_bar.pack(fill=tk.X, pady=2)
        
        # Área de registro
        log_frame = ttk.LabelFrame(main_frame, text="Registro", padding="10")
        log_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        self.log_text = scrolledtext.ScrolledText(log_frame, wrap=tk.WORD, width=80, height=15)
        self.log_text.pack(fill=tk.BOTH, expand=True)
        self.log_text.config(state=tk.DISABLED)

    def browse_input_folder(self):
        folder = filedialog.askdirectory()
        if folder:
            self.input_folder.set(folder)

    def browse_output_folder(self):
        folder = filedialog.askdirectory()
        if folder:
            self.output_folder.set(folder)

    def log_message(self, message):
        self.log_queue.put(message)

    def update_logs_from_queue(self):
        try:
            while True:
                message = self.log_queue.get_nowait()
                self.log_text.config(state=tk.NORMAL)
                self.log_text.insert(tk.END, message + "\n")
                self.log_text.see(tk.END)
                self.log_text.config(state=tk.DISABLED)
                self.log_queue.task_done()
        except queue.Empty:
            pass
        finally:
            self.root.after(100, self.update_logs_from_queue)

    def check_ffmpeg_startup(self):
        if not self.check_ffmpeg():
            messagebox.showerror("Error", "ffmpeg no está instalado o no está en el PATH.\n"
                               "Por favor, instala ffmpeg y asegúrate de que esté en el PATH.")

    def check_ffmpeg(self):
        """Verifica si ffmpeg está instalado en el sistema."""
        try:
            subprocess.run(['ffmpeg', '-version'], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            self.log_message("✅ ffmpeg detectado correctamente.")
            return True
        except FileNotFoundError:
            self.log_message("❌ Error: ffmpeg no está instalado o no está en el PATH.")
            return False

    def convert_to_wav(self, input_file, output_file):
        """Convierte un archivo de video a WAV optimizado para Whisper."""
        try:
            result = subprocess.run(
                ['ffmpeg', '-i', input_file, '-vn', '-acodec', 'pcm_s16le', 
                 '-ar', '16000', '-ac', '1', output_file, 
                 '-y' if self.overwrite_existing.get() else '-n',
                 '-hide_banner', '-loglevel', 'warning'],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                universal_newlines=True
            )
            
            if result.returncode != 0:
                self.log_message(f"❌ Error al convertir {input_file}: {result.stderr}")
                return False
            
            return True
        except Exception as e:
            self.log_message(f"❌ Error al convertir {input_file}: {str(e)}")
            return False

    def find_video_files(self, base_path, recursive=True):
        """Encuentra todos los archivos de video en la ruta especificada."""
        base_path = Path(base_path)
        video_files = []
        
        # Extensiones de video comunes
        video_extensions = ['.mp4', '.mov', '.avi', '.mkv', '.m4v', '.wmv', '.flv', '.ts']
        
        if recursive:
            # Búsqueda recursiva en todas las subcarpetas
            for ext in video_extensions:
                video_files.extend(list(base_path.glob(f'**/*{ext}')))
                video_files.extend(list(base_path.glob(f'**/*{ext.upper()}')))
        else:
            # Búsqueda solo en la carpeta actual
            for ext in video_extensions:
                video_files.extend(list(base_path.glob(f'*{ext}')))
                video_files.extend(list(base_path.glob(f'*{ext.upper()}')))
        
        return video_files

    def update_progress(self, current, total):
        progress = int((current / total) * 100)
        self.progress_bar['value'] = progress
        self.root.update_idletasks()

    def conversion_worker(self):
        input_path = self.input_folder.get()
        output_path = self.output_folder.get()
        recursive = self.recursive_search.get()
        
        if not input_path or not output_path:
            self.log_message("❌ Debes seleccionar las carpetas de entrada y salida.")
            self.reset_ui_after_conversion()
            return
        
        if not os.path.exists(input_path):
            self.log_message(f"❌ La carpeta de entrada no existe: {input_path}")
            self.reset_ui_after_conversion()
            return
        
        if not os.path.exists(output_path):
            try:
                os.makedirs(output_path)
                self.log_message(f"✅ Creada carpeta de salida: {output_path}")
            except Exception as e:
                self.log_message(f"❌ Error al crear carpeta de salida: {str(e)}")
                self.reset_ui_after_conversion()
                return
        
        # Buscar archivos de video
        self.log_message(f"🔍 Buscando archivos de video en: {input_path}")
        video_files = self.find_video_files(input_path, recursive)
        
        if not video_files:
            self.log_message(f"ℹ️ No se encontraron archivos de video en la carpeta seleccionada.")
            self.reset_ui_after_conversion()
            return
        
        self.log_message(f"✅ Se encontraron {len(video_files)} archivos de video.")
        
        # Contadores
        successful = 0
        failed = 0
        skipped = 0
        total_files = len(video_files)
        
        # Convertir archivos
        self.log_message("🚀 Iniciando conversión...")
        for i, video_file in enumerate(video_files):
            if self.stop_conversion:
                self.log_message("⚠️ Proceso de conversión detenido por el usuario.")
                break
                
            # Calcular ruta de salida preservando la estructura de carpetas
            rel_path = video_file.relative_to(input_path) if video_file.is_relative_to(input_path) else Path(video_file.name)
            output_file = Path(output_path) / rel_path.with_suffix('.wav')
            
            # Crear directorio de salida si no existe
            os.makedirs(output_file.parent, exist_ok=True)
            
            # Verificar si el archivo WAV ya existe
            if output_file.exists() and not self.overwrite_existing.get():
                self.log_message(f"⏭️ Omitido: {video_file.name} (Ya existe)")
                skipped += 1
            else:
                self.log_message(f"🔄 Convirtiendo: {video_file.name}")
                success = self.convert_to_wav(str(video_file), str(output_file))
                
                if success:
                    self.log_message(f"✅ Convertido: {video_file.name}")
                    successful += 1
                else:
                    failed += 1
            
            # Actualizar progreso
            self.update_progress(i + 1, total_files)
        
        # Mostrar resultados
        self.log_message("\n=== Resumen de Conversión ===")
        self.log_message(f"📊 Total de archivos encontrados: {total_files}")
        self.log_message(f"✅ Conversiones exitosas: {successful}")
        self.log_message(f"❌ Conversiones fallidas: {failed}")
        self.log_message(f"⏭️ Archivos omitidos: {skipped}")
        self.log_message("=== Proceso Finalizado ===\n")
        
        self.reset_ui_after_conversion()

    def start_conversion(self):
        if not self.check_ffmpeg():
            messagebox.showerror("Error", "ffmpeg no está instalado o no está en el PATH.\n"
                               "Por favor, instala ffmpeg y asegúrate de que esté en el PATH.")
            return
            
        if self.conversion_running:
            return
            
        self.conversion_running = True
        self.stop_conversion = False
        
        # Deshabilitar botones durante la conversión
        self.start_button.config(state=tk.DISABLED)
        self.stop_button.config(state=tk.NORMAL)
        
        # Resetear barra de progreso
        self.progress_bar['value'] = 0
        
        # Iniciar hilo de conversión
        self.conversion_thread = threading.Thread(target=self.conversion_worker)
        self.conversion_thread.daemon = True
        self.conversion_thread.start()

    def stop_conversion_process(self):
        if self.conversion_running:
            self.stop_conversion = True
            self.log_message("⚠️ Solicitando detener la conversión...")
            self.stop_button.config(state=tk.DISABLED)

    def reset_ui_after_conversion(self):
        self.conversion_running = False
        self.start_button.config(state=tk.NORMAL)
        self.stop_button.config(state=tk.DISABLED)

def main():
    root = tk.Tk()
    app = MP4ToWAVConverter(root)
    root.mainloop()

if __name__ == "__main__":
    main() 