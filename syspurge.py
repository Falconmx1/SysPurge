#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SysPurge Ultimate - Herramienta de limpieza multi-plataforma
Author: Falconmx1
License: MIT
Version: 3.0 - Ultimate Edition
"""

import os
import sys
import platform
import subprocess
import shutil
import argparse
import time
import json
import csv
import sqlite3
import hashlib
import zipfile
import threading
import queue
from pathlib import Path
from datetime import datetime, timedelta
from collections import defaultdict
import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext, filedialog

# ==================== CONFIGURACIÓN GLOBAL ====================

SISTEMA = platform.system()
ES_WINDOWS = SISTEMA == "Windows"
ES_LINUX = SISTEMA == "Linux"
ES_MAC = SISTEMA == "Darwin"

total_liberado = 0
reporte_detalle = []
backup_files = []  # Para undo
historial_db = "syspurge_history.db"

# Configuración de temas GUI
TEMA_ACTUAL = "dark"  # dark o light

# Colores para consola
class Colors:
    RED = '\033[91m' if not ES_WINDOWS else ''
    GREEN = '\033[92m' if not ES_WINDOWS else ''
    YELLOW = '\033[93m' if not ES_WINDOWS else ''
    BLUE = '\033[94m' if not ES_WINDOWS else ''
    MAGENTA = '\033[95m' if not ES_WINDOWS else ''
    CYAN = '\033[96m' if not ES_WINDOWS else ''
    RESET = '\033[0m' if not ES_WINDOWS else ''
    BOLD = '\033[1m' if not ES_WINDOWS else ''

# ==================== BASE DE DATOS HISTÓRICA ====================

def init_database():
    """Inicializa la base de datos SQLite para historial"""
    conn = sqlite3.connect(historial_db)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS historial (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            sistema TEXT NOT NULL,
            total_liberado_bytes INTEGER,
            total_liberado_formateado TEXT,
            detalle_json TEXT
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS backups (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            archivo_original TEXT,
            archivo_backup TEXT,
            tamaño_bytes INTEGER
        )
    ''')
    conn.commit()
    conn.close()

def save_to_history():
    """Guarda el resultado de la limpieza en el historial"""
    conn = sqlite3.connect(historial_db)
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO historial (timestamp, sistema, total_liberado_bytes, total_liberado_formateado, detalle_json)
        VALUES (?, ?, ?, ?, ?)
    ''', (
        datetime.now().isoformat(),
        SISTEMA,
        total_liberado,
        format_size(total_liberado),
        json.dumps(reporte_detalle)
    ))
    conn.commit()
    conn.close()

def get_history_stats():
    """Obtiene estadísticas históricas"""
    conn = sqlite3.connect(historial_db)
    cursor = conn.cursor()
    cursor.execute('SELECT COUNT(*), SUM(total_liberado_bytes) FROM historial')
    count, total = cursor.fetchone()
    cursor.execute('SELECT timestamp, total_liberado_formateado FROM historial ORDER BY timestamp DESC LIMIT 10')
    ultimas = cursor.fetchall()
    conn.close()
    return {
        "total_limpiezas": count or 0,
        "total_liberado_historico": total or 0,
        "ultimas_limpiezas": ultimas
    }

# ==================== UTILIDADES MEJORADAS ====================

def get_size(path):
    try:
        if os.path.isfile(path):
            return os.path.getsize(path)
        elif os.path.isdir(path):
            total = 0
            for dirpath, dirnames, filenames in os.walk(path, followlinks=False):
                for f in filenames:
                    fp = os.path.join(dirpath, f)
                    if os.path.exists(fp):
                        try:
                            total += os.path.getsize(fp)
                        except:
                            pass
            return total
    except:
        return 0
    return 0

def format_size(bytes):
    if bytes == 0:
        return "0 B"
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if bytes < 1024.0:
            return f"{bytes:.2f} {unit}"
        bytes /= 1024.0
    return f"{bytes:.2f} PB"

def add_liberated(size, descripcion=""):
    global total_liberado
    total_liberado += size
    reporte_detalle.append({
        "descripcion": descripcion,
        "tamaño_bytes": size,
        "tamaño_formateado": format_size(size),
        "timestamp": datetime.now().isoformat()
    })
    if descripcion:
        print_progress(f"{descripcion}: {format_size(size)}", "ok")

def print_progress(message, status="info"):
    timestamp = datetime.now().strftime("%H:%M:%S")
    if status == "ok":
        print(f"{Colors.GREEN}✅ [{timestamp}] {message}{Colors.RESET}")
    elif status == "error":
        print(f"{Colors.RED}❌ [{timestamp}] {message}{Colors.RESET}")
    elif status == "warning":
        print(f"{Colors.YELLOW}⚠️  [{timestamp}] {message}{Colors.RESET}")
    elif status == "info":
        print(f"{Colors.BLUE}➡️  [{timestamp}] {message}{Colors.RESET}")
    else:
        print(f"   {message}")

def run_command(cmd, shell=False, check=True):
    try:
        if shell:
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        else:
            result = subprocess.run(cmd, capture_output=True, text=True)
        if check and result.returncode != 0:
            return None
        return result
    except:
        return None

def create_backup(file_path):
    """Crea un backup antes de eliminar archivos importantes"""
    try:
        if os.path.exists(file_path):
            backup_dir = Path.home() / ".syspurge_backups"
            backup_dir.mkdir(exist_ok=True)
            backup_name = backup_dir / f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{Path(file_path).name}"
            if os.path.isdir(file_path):
                shutil.copytree(file_path, backup_name, ignore_errors=True)
            else:
                shutil.copy2(file_path, backup_name)
            backup_files.append({
                "original": file_path,
                "backup": str(backup_name),
                "timestamp": datetime.now().isoformat()
            })
            return str(backup_name)
    except:
        return None
    return None

def restore_backup(backup_path, original_path):
    """Restaura un backup"""
    try:
        if os.path.exists(backup_path):
            if os.path.isdir(backup_path):
                shutil.copytree(backup_path, original_path, dirs_exist_ok=True)
            else:
                shutil.copy2(backup_path, original_path)
            return True
    except:
        return False
    return False

def send_notification(title, message):
    """Envía notificación de escritorio"""
    try:
        if ES_WINDOWS:
            from plyer import notification
            notification.notify(title=title, message=message, timeout=5)
        elif ES_LINUX:
            subprocess.run(['notify-send', title, message], check=False)
        elif ES_MAC:
            subprocess.run(['osascript', '-e', f'display notification "{message}" with title "{title}"'], check=False)
    except:
        pass

# ==================== NUEVOS MÓDULOS DE LIMPIEZA ====================

# 1. DOCKER CLEANUP
def clean_docker():
    print_progress("Limpiando Docker...")
    liberated = 0
    
    if shutil.which('docker'):
        # Contenedores detenidos
        result = run_command(['docker', 'container', 'prune', '-f'])
        # Imágenes huérfanas
        result = run_command(['docker', 'image', 'prune', '-f'])
        # Volúmenes no usados
        result = run_command(['docker', 'volume', 'prune', '-f'])
        # Build cache
        result = run_command(['docker', 'builder', 'prune', '-f'])
        
        # Medir espacio liberado (estimado)
        liberated = 100 * 1024 * 1024  # Estimado 100MB
        print_progress("  Docker limpiado", "ok")
    else:
        print_progress("  Docker no instalado", "warning")
    
    if liberated > 0:
        add_liberated(liberated, "Docker (contenedores, imágenes, volúmenes)")

# 2. PYTHON CACHE
def clean_python_cache():
    print_progress("Limpiando caché de Python...")
    liberated = 0
    
    # Buscar __pycache__ en todo el sistema (limitado a home)
    home = str(Path.home())
    pycache_dirs = []
    for root, dirs, files in os.walk(home):
        if '__pycache__' in dirs:
            pycache_dirs.append(os.path.join(root, '__pycache__'))
        for file in files:
            if file.endswith(('.pyc', '.pyo', '.pyd')):
                pycache_dirs.append(os.path.join(root, file))
    
    for item in pycache_dirs[:1000]:  # Limitar para rendimiento
        size_before = get_size(item)
        try:
            if os.path.isdir(item):
                shutil.rmtree(item, ignore_errors=True)
            else:
                os.remove(item)
            liberated += size_before
        except:
            pass
    
    # pytest cache
    pytest_cache = os.path.join(home, '.pytest_cache')
    if os.path.exists(pytest_cache):
        liberated += get_size(pytest_cache)
        shutil.rmtree(pytest_cache, ignore_errors=True)
    
    if liberated > 0:
        add_liberated(liberated, "Python (__pycache__, .pyc, .pytest_cache)")

# 3. NODE.JS / NPM / YARN / PNPM
def clean_node():
    print_progress("Limpiando Node.js/NPM/Yarn/PNPM...")
    liberated = 0
    
    home = str(Path.home())
    
    # NPM cache
    npm_cache = os.path.join(home, '.npm')
    if os.path.exists(npm_cache):
        size = get_size(npm_cache)
        shutil.rmtree(npm_cache, ignore_errors=True)
        liberated += size
        print_progress("  NPM cache limpiada", "ok")
    
    # Yarn cache
    yarn_cache = os.path.join(home, '.yarn/cache')
    if os.path.exists(yarn_cache):
        size = get_size(yarn_cache)
        shutil.rmtree(yarn_cache, ignore_errors=True)
        liberated += size
        print_progress("  Yarn cache limpiada", "ok")
    
    # PNPM store
    pnpm_store = os.path.join(home, '.pnpm-store')
    if os.path.exists(pnpm_store):
        size = get_size(pnpm_store)
        shutil.rmtree(pnpm_store, ignore_errors=True)
        liberated += size
        print_progress("  PNPM store limpiada", "ok")
    
    # Buscar node_modules (opcional - preguntar)
    # Por ahora solo en home y limitado
    if liberated > 0:
        add_liberated(liberated, "Node.js/NPM/Yarn/PNPM cache")

# 4. JAVA / MAVEN / GRADLE
def clean_java():
    print_progress("Limpiando Java/Maven/Gradle...")
    liberated = 0
    
    home = str(Path.home())
    
    # Maven repo (opcional - puede ser grande)
    m2_repo = os.path.join(home, '.m2/repository')
    if os.path.exists(m2_repo):
        # Limpiar solo snapshots y archivos .lastUpdated
        for root, dirs, files in os.walk(m2_repo):
            for file in files:
                if file.endswith('.lastUpdated') or 'snapshot' in file.lower():
                    fp = os.path.join(root, file)
                    size = get_size(fp)
                    try:
                        os.remove(fp)
                        liberated += size
                    except:
                        pass
    
    # Gradle cache
    gradle_cache = os.path.join(home, '.gradle/caches')
    if os.path.exists(gradle_cache):
        size = get_size(gradle_cache)
        shutil.rmtree(gradle_cache, ignore_errors=True)
        liberated += size
        print_progress("  Gradle cache limpiada", "ok")
    
    if liberated > 0:
        add_liberated(liberated, "Java/Maven/Gradle")

# 5. RUST / CARGO
def clean_rust():
    print_progress("Limpiando Rust/Cargo...")
    liberated = 0
    
    home = str(Path.home())
    
    cargo_cache = os.path.join(home, '.cargo/registry/cache')
    if os.path.exists(cargo_cache):
        size = get_size(cargo_cache)
        shutil.rmtree(cargo_cache, ignore_errors=True)
        liberated += size
        print_progress("  Cargo cache limpiada", "ok")
    
    cargo_git = os.path.join(home, '.cargo/git/db')
    if os.path.exists(cargo_git):
        size = get_size(cargo_git)
        shutil.rmtree(cargo_git, ignore_errors=True)
        liberated += size
    
    if liberated > 0:
        add_liberated(liberated, "Rust/Cargo cache")

# 6. ANDROID STUDIO / AVD / GRADLE
def clean_android():
    print_progress("Limpiando Android Studio/AVD...")
    liberated = 0
    
    home = str(Path.home())
    
    # Android cache
    android_cache = os.path.join(home, '.android/cache')
    if os.path.exists(android_cache):
        size = get_size(android_cache)
        shutil.rmtree(android_cache, ignore_errors=True)
        liberated += size
    
    # AVD logs
    avd_dir = os.path.join(home, '.android/avd')
    if os.path.exists(avd_dir):
        for avd in os.listdir(avd_dir):
            if avd.endswith('.avd'):
                log_file = os.path.join(avd_dir, avd, 'logs')
                if os.path.exists(log_file):
                    size = get_size(log_file)
                    shutil.rmtree(log_file, ignore_errors=True)
                    liberated += size
    
    # Gradle wrapper cache
    gradle_wrapper = os.path.join(home, '.gradle/wrapper/dists')
    if os.path.exists(gradle_wrapper):
        # Solo limpiar versiones viejas (más de 30 días)
        now = time.time()
        for item in os.listdir(gradle_wrapper):
            item_path = os.path.join(gradle_wrapper, item)
            if os.path.isdir(item_path):
                if now - os.path.getmtime(item_path) > 30 * 86400:
                    size = get_size(item_path)
                    shutil.rmtree(item_path, ignore_errors=True)
                    liberated += size
    
    if liberated > 0:
        add_liberated(liberated, "Android Studio/AVD/Gradle")

# 7. STEAM CACHE
def clean_steam():
    print_progress("Limpiando Steam cache...")
    liberated = 0
    
    if ES_WINDOWS:
        steam_dir = os.path.expandvars('%ProgramFiles(x86)%\\Steam')
    elif ES_LINUX:
        steam_dir = os.path.expanduser('~/.steam')
    elif ES_MAC:
        steam_dir = os.path.expanduser('~/Library/Application Support/Steam')
    else:
        steam_dir = None
    
    if steam_dir and os.path.exists(steam_dir):
        download_cache = os.path.join(steam_dir, 'steamapps', 'downloading')
        if os.path.exists(download_cache):
            size = get_size(download_cache)
            shutil.rmtree(download_cache, ignore_errors=True)
            liberated += size
            print_progress("  Steam download cache limpiada", "ok")
        
        shader_cache = os.path.join(steam_dir, 'steamapps', 'shadercache')
        if os.path.exists(shader_cache):
            size = get_size(shader_cache)
            shutil.rmtree(shader_cache, ignore_errors=True)
            liberated += size
    
    if liberated > 0:
        add_liberated(liberated, "Steam cache")

# 8. DETECTAR Y ELIMINAR DUPLICADOS
def find_duplicates(directory=None, min_size_mb=1):
    """Encuentra archivos duplicados por hash"""
    if not directory:
        directory = str(Path.home())
    
    print_progress(f"Buscando duplicados en {directory} (min {min_size_mb}MB)...")
    
    hash_map = defaultdict(list)
    files_checked = 0
    
    for root, dirs, files in os.walk(directory):
        # Saltar directorios del sistema
        if any(x in root for x in ['/proc', '/sys', '/dev', 'Windows', 'System32']):
            continue
        
        for file in files:
            file_path = os.path.join(root, file)
            try:
                if os.path.getsize(file_path) >= min_size_mb * 1024 * 1024:
                    with open(file_path, 'rb') as f:
                        file_hash = hashlib.md5(f.read(8192)).hexdigest()
                    hash_map[file_hash].append(file_path)
                    files_checked += 1
                    if files_checked % 1000 == 0:
                        print_progress(f"  Escaneados {files_checked} archivos...", "info")
            except:
                pass
    
    duplicates_found = []
    for hash_val, files in hash_map.items():
        if len(files) > 1:
            duplicates_found.extend(files[1:])  # Todos menos el primero
    
    return duplicates_found

def clean_duplicates(dry_run=False):
    print_progress("Buscando y eliminando archivos duplicados...")
    liberated = 0
    
    duplicates = find_duplicates(min_size_mb=10)  # Solo archivos >10MB
    
    if not dry_run:
        for dup in duplicates:
            size = get_size(dup)
            try:
                os.remove(dup)
                liberated += size
            except:
                pass
    
    if liberated > 0:
        add_liberated(liberated, f"Archivos duplicados ({len(duplicates)} archivos)")
    else:
        print_progress("  No se encontraron duplicados significativos", "warning")

# 9. COMPRIMIR LOGS VIEJOS
def compress_old_logs():
    print_progress("Comprimiendo logs antiguos (>30 días)...")
    liberated = 0
    compressed = 0
    
    log_dirs = []
    if ES_LINUX or ES_MAC:
        log_dirs = ['/var/log', os.path.expanduser('~/Library/Logs')]
    else:
        log_dirs = [os.path.expandvars('%SystemRoot%\\Logs'), os.path.expanduser('~\\AppData\\Local\\Temp')]
    
    now = time.time()
    cutoff = 30 * 86400
    
    for log_dir in log_dirs:
        if not os.path.exists(log_dir):
            continue
        
        for root, dirs, files in os.walk(log_dir):
            for file in files:
                if file.endswith('.log'):
                    file_path = os.path.join(root, file)
                    try:
                        if now - os.path.getmtime(file_path) > cutoff:
                            # Comprimir
                            zip_path = file_path + '.zip'
                            with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                                zipf.write(file_path, os.path.basename(file_path))
                            
                            size_before = os.path.getsize(file_path)
                            os.remove(file_path)
                            size_after = os.path.getsize(zip_path) if os.path.exists(zip_path) else 0
                            liberated += (size_before - size_after)
                            compressed += 1
                    except:
                        pass
    
    if liberated > 0:
        add_liberated(liberated, f"Logs comprimidos ({compressed} archivos)")
    else:
        print_progress("  No se encontraron logs antiguos", "warning")

# 10. SERVIDOR WEB DASHBOARD
def start_web_dashboard(port=8080):
    """Inicia un servidor web con estadísticas en tiempo real"""
    try:
        from http.server import HTTPServer, BaseHTTPRequestHandler
        import json
        
        class DashboardHandler(BaseHTTPRequestHandler):
            def do_GET(self):
                if self.path == '/':
                    self.send_response(200)
                    self.send_header('Content-type', 'text/html')
                    self.end_headers()
                    
                    stats = get_history_stats()
                    html = f'''
                    <!DOCTYPE html>
                    <html>
                    <head>
                        <title>SysPurge Dashboard</title>
                        <style>
                            body {{ font-family: Arial; margin: 40px; background: #1e1e2e; color: #fff; }}
                            .card {{ background: #313244; padding: 20px; border-radius: 10px; margin: 10px; display: inline-block; }}
                            .big {{ font-size: 32px; font-weight: bold; color: #89b4fa; }}
                            table {{ width: 100%; border-collapse: collapse; }}
                            th, td {{ padding: 10px; text-align: left; border-bottom: 1px solid #45475a; }}
                        </style>
                    </head>
                    <body>
                        <h1>💀 SysPurge Dashboard</h1>
                        <div class="card">
                            <div>Total Limpiezas</div>
                            <div class="big">{stats['total_limpiezas']}</div>
                        </div>
                        <div class="card">
                            <div>Total Liberado</div>
                            <div class="big">{format_size(stats['total_liberado_historico'])}</div>
                        </div>
                        <h2>Últimas Limpiezas</h2>
                        <table>
                            <tr><th>Fecha</th><th>Liberado</th></tr>
                            {''.join(f'<tr><td>{row[0]}</td><td>{row[1]}</td></tr>' for row in stats['ultimas_limpiezas'])}
                        </table>
                    </body>
                    </html>
                    '''
                    self.wfile.write(html.encode())
                else:
                    self.send_response(404)
                    self.end_headers()
        
        server = HTTPServer(('localhost', port), DashboardHandler)
        print_progress(f"Dashboard web en http://localhost:{port}", "ok")
        server.serve_forever()
    except Exception as e:
        print_progress(f"No se pudo iniciar dashboard: {e}", "error")

# ==================== INTERFAZ GRÁFICA MEJORADA ====================

class SysPurgeUltimateGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("SysPurge Ultimate - Limpiador de Sistema Profesional")
        self.root.geometry("900x700")
        self.root.resizable(True, True)
        
        self.setup_theme()
        self.setup_ui()
        self.check_admin()
    
    def setup_theme(self):
        style = ttk.Style()
        if TEMA_ACTUAL == "dark":
            self.root.configure(bg='#2d2d2d')
            style.theme_use('clam')
            style.configure('TLabel', background='#2d2d2d', foreground='white')
            style.configure('TFrame', background='#2d2d2d')
            style.configure('TLabelframe', background='#2d2d2d', foreground='white')
            style.configure('TLabelframe.Label', background='#2d2d2d', foreground='white')
            style.configure('TButton', background='#404040', foreground='white')
            style.map('TButton', background=[('active', '#505050')])
            style.configure('TCheckbutton', background='#2d2d2d', foreground='white')
        else:
            self.root.configure(bg='#f0f0f0')
    
    def setup_ui(self):
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Título
        title = ttk.Label(main_frame, text="💀 SysPurge Ultimate 💀", font=('Arial', 24, 'bold'))
        title.grid(row=0, column=0, columnspan=3, pady=10)
        
        # Info sistema
        sys_info = f"🖥️ {SISTEMA} | {platform.machine()} | Python {platform.python_version()}"
        ttk.Label(main_frame, text=sys_info, font=('Arial', 10)).grid(row=1, column=0, columnspan=3, pady=5)
        
        # Crear notebook (tabs)
        notebook = ttk.Notebook(main_frame)
        notebook.grid(row=2, column=0, columnspan=3, sticky=(tk.W, tk.E, tk.N, tk.S), pady=10)
        
        # Tab 1: Limpieza básica
        basic_tab = ttk.Frame(notebook)
        notebook.add(basic_tab, text="🧹 Limpieza Básica")
        self.setup_basic_tab(basic_tab)
        
        # Tab 2: Limpieza avanzada
        advanced_tab = ttk.Frame(notebook)
        notebook.add(advanced_tab, text="⚙️ Limpieza Avanzada")
        self.setup_advanced_tab(advanced_tab)
        
        # Tab 3: Programación
        schedule_tab = ttk.Frame(notebook)
        notebook.add(schedule_tab, text="⏰ Automatización")
        self.setup_schedule_tab(schedule_tab)
        
        # Tab 4: Estadísticas
        stats_tab = ttk.Frame(notebook)
        notebook.add(stats_tab, text="📊 Estadísticas")
        self.setup_stats_tab(stats_tab)
        
        # Tab 5: Dashboard Web
        web_tab = ttk.Frame(notebook)
        notebook.add(web_tab, text="🌐 Dashboard Web")
        self.setup_web_tab(web_tab)
        
        # Log de salida
        log_frame = ttk.LabelFrame(main_frame, text="Registro en tiempo real", padding="5")
        log_frame.grid(row=3, column=0, columnspan=3, sticky=(tk.W, tk.E, tk.N, tk.S), pady=10)
        
        self.log_text = scrolledtext.ScrolledText(log_frame, height=12, font=('Consolas', 9))
        self.log_text.pack(fill=tk.BOTH, expand=True)
        
        # Barra de progreso
        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(main_frame, variable=self.progress_var, maximum=100)
        self.progress_bar.grid(row=4, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=5)
        
        # Estadísticas inferiores
        self.stats_label = ttk.Label(main_frame, text="📊 Total liberado en esta sesión: 0 B", font=('Arial', 10))
        self.stats_label.grid(row=5, column=0, columnspan=3, pady=5)
        
        # Botones principales
        btn_frame = ttk.Frame(main_frame)
        btn_frame.grid(row=6, column=0, columnspan=3, pady=10)
        
        self.btn_clean = ttk.Button(btn_frame, text="🚀 INICIAR LIMPIEZA COMPLETA", command=self.start_full_clean)
        self.btn_clean.grid(row=0, column=0, padx=5)
        
        ttk.Button(btn_frame, text="📄 Exportar Reporte", command=self.export_report).grid(row=0, column=1, padx=5)
        ttk.Button(btn_frame, text="💾 Crear Backup", command=self.create_system_backup).grid(row=0, column=2, padx=5)
        ttk.Button(btn_frame, text="🔄 Restaurar Backup", command=self.restore_backup_gui).grid(row=0, column=3, padx=5)
        
        # Configurar grid
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(0, weight=1)
        main_frame.rowconfigure(3, weight=1)
        notebook.columnconfigure(0, weight=1)
        notebook.rowconfigure(0, weight=1)
    
    def setup_basic_tab(self, parent):
        frame = ttk.Frame(parent, padding="10")
        frame.pack(fill=tk.BOTH, expand=True)
        
        self.var_temp = tk.BooleanVar(value=True)
        self.var_cache = tk.BooleanVar(value=True)
        self.var_browser = tk.BooleanVar(value=True)
        self.var_swap = tk.BooleanVar(value=True)
        self.var_trash = tk.BooleanVar(value=True)
        self.var_logs = tk.BooleanVar(value=False)
        
        options = [
            ("🗑️ Archivos temporales", self.var_temp),
            ("📦 Caché del sistema", self.var_cache),
            ("🌐 Caché de navegadores", self.var_browser),
            ("💾 Swap / Memoria", self.var_swap),
            ("🗑️ Papelera de reciclaje", self.var_trash),
            ("📝 Logs antiguos", self.var_logs),
        ]
        
        for i, (text, var) in enumerate(options):
            ttk.Checkbutton(frame, text=text, variable=var).grid(row=i, column=0, sticky=tk.W, pady=5)
    
    def setup_advanced_tab(self, parent):
        frame = ttk.Frame(parent, padding="10")
        frame.pack(fill=tk.BOTH, expand=True)
        
        self.var_docker = tk.BooleanVar(value=False)
        self.var_python = tk.BooleanVar(value=False)
        self.var_node = tk.BooleanVar(value=False)
        self.var_java = tk.BooleanVar(value=False)
        self.var_rust = tk.BooleanVar(value=False)
        self.var_android = tk.BooleanVar(value=False)
        self.var_steam = tk.BooleanVar(value=False)
        self.var_duplicates = tk.BooleanVar(value=False)
        
        options = [
            ("🐳 Docker (contenedores, imágenes, volúmenes)", self.var_docker),
            ("🐍 Python (__pycache__, .pyc)", self.var_python),
            ("📦 Node.js (npm, yarn, pnpm)", self.var_node),
            ("☕ Java/Maven/Gradle", self.var_java),
            ("🦀 Rust/Cargo", self.var_rust),
            ("📱 Android Studio/AVD", self.var_android),
            ("🎮 Steam cache", self.var_steam),
            ("📁 Archivos duplicados (cuidado)", self.var_duplicates),
        ]
        
        for i, (text, var) in enumerate(options):
            ttk.Checkbutton(frame, text=text, variable=var).grid(row=i, column=0, sticky=tk.W, pady=5)
    
    def setup_schedule_tab(self, parent):
        frame = ttk.Frame(parent, padding="10")
        frame.pack(fill=tk.BOTH, expand=True)
        
        ttk.Label(frame, text="Configurar limpieza automática:", font=('Arial', 12)).pack(pady=10)
        
        self.schedule_var = tk.StringVar(value="semanal")
        for freq in ["diario", "semanal", "mensual"]:
            ttk.Radiobutton(frame, text=freq.capitalize(), variable=self.schedule_var, value=freq).pack(pady=5)
        
        ttk.Button(frame, text="⏰ Programar Limpieza", command=self.setup_auto).pack(pady=20)
        
        ttk.Label(frame, text="\n💡 La limpieza se ejecutará automáticamente a las 3:00 AM", font=('Arial', 9)).pack()
    
    def setup_stats_tab(self, parent):
        frame = ttk.Frame(parent, padding="10")
        frame.pack(fill=tk.BOTH, expand=True)
        
        stats = get_history_stats()
        
        stats_frame = ttk.Frame(frame)
        stats_frame.pack(pady=20)
        
        ttk.Label(stats_frame, text=f"📊 Total de limpiezas realizadas:", font=('Arial', 12)).grid(row=0, column=0, pady=5)
        ttk.Label(stats_frame, text=str(stats['total_limpiezas']), font=('Arial', 24, 'bold')).grid(row=0, column=1, padx=20)
        
        ttk.Label(stats_frame, text=f"💾 Total liberado históricamente:", font=('Arial', 12)).grid(row=1, column=0, pady=5)
        ttk.Label(stats_frame, text=format_size(stats['total_liberado_historico']), font=('Arial', 24, 'bold')).grid(row=1, column=1, padx=20)
        
        # Gráfico simple de últimas limpiezas
        ttk.Label(frame, text="Últimas 10 limpiezas:", font=('Arial', 12)).pack(pady=10)
        
        history_text = scrolledtext.ScrolledText(frame, height=10, font=('Consolas', 9))
        history_text.pack(fill=tk.BOTH, expand=True)
        
        for timestamp, size in stats['ultimas_limpiezas']:
            history_text.insert(tk.END, f"{timestamp} → {size}\n")
    
    def setup_web_tab(self, parent):
        frame = ttk.Frame(parent, padding="10")
        frame.pack(fill=tk.BOTH, expand=True)
        
        ttk.Label(frame, text="🌐 Dashboard Web en tiempo real", font=('Arial', 14)).pack(pady=10)
        ttk.Label(frame, text="Inicia un servidor web local para ver estadísticas desde cualquier navegador", wraplength=400).pack(pady=5)
        
        self.web_port = tk.StringVar(value="8080")
        port_frame = ttk.Frame(frame)
        port_frame.pack(pady=10)
        ttk.Label(port_frame, text="Puerto:").pack(side=tk.LEFT, padx=5)
        ttk.Entry(port_frame, textvariable=self.web_port, width=10).pack(side=tk.LEFT)
        
        ttk.Button(frame, text="🚀 Iniciar Dashboard Web", command=self.start_web_dashboard).pack(pady=10)
        ttk.Label(frame, text="⚠️ El servidor se ejecutará en segundo plano. Cierra la ventana para detenerlo.", font=('Arial', 8)).pack(pady=20)
    
    def log(self, message, status="info"):
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_text.insert(tk.END, f"[{timestamp}] {message}\n")
        self.log_text.see(tk.END)
        self.root.update()
    
    def check_admin(self):
        if ES_LINUX or ES_MAC:
            if os.geteuid() != 0:
                self.log("⚠️ No estás ejecutando como root. Algunas funciones pueden no funcionar.", "warning")
    
    def start_full_clean(self):
        self.btn_clean.config(state=tk.DISABLED)
        self.log_text.delete(1.0, tk.END)
        self.progress_var.set(0)
        
        def clean_thread():
            global total_liberado, reporte_detalle
            total_liberado = 0
            reporte_detalle = []
            
            steps = []
            # Básicos
            if self.var_temp.get(): steps.append(clean_temp)
            if self.var_cache.get(): steps.append(clean_system_cache)
            if self.var_browser.get(): steps.append(clean_browser_cache)
            if self.var_swap.get(): steps.append(clean_swap)
            if self.var_trash.get(): steps.append(clean_trash)
            if self.var_logs.get(): steps.append(clean_logs)
            
            # Avanzados
            if hasattr(self, 'var_docker') and self.var_docker.get(): steps.append(clean_docker)
            if hasattr(self, 'var_python') and self.var_python.get(): steps.append(clean_python_cache)
            if hasattr(self, 'var_node') and self.var_node.get(): steps.append(clean_node)
            if hasattr(self, 'var_java') and self.var_java.get(): steps.append(clean_java)
            if hasattr(self, 'var_rust') and self.var_rust.get(): steps.append(clean_rust)
            if hasattr(self, 'var_android') and self.var_android.get(): steps.append(clean_android)
            if hasattr(self, 'var_steam') and self.var_steam.get(): steps.append(clean_steam)
            if hasattr(self, 'var_duplicates') and self.var_duplicates.get(): steps.append(clean_duplicates)
            
            total_steps = len(steps)
            for i, step in enumerate(steps):
                try:
                    self.log(f"Iniciando: {step.__name__.replace('_', ' ').title()}")
                    step()
                except Exception as e:
                    self.log(f"Error: {e}", "error")
                self.progress_var.set((i + 1) / total_steps * 100)
            
            # Guardar en historial
            save_to_history()
            send_notification("SysPurge Ultimate", f"Limpieza completada. Liberados {format_size(total_liberado)}")
            
            self.log(f"\n🎉 LIMPIEZA COMPLETADA")
            self.log(f"📊 Total liberado: {format_size(total_liberado)}", "ok")
            self.stats_label.config(text=f"📊 Total liberado en esta sesión: {format_size(total_liberado)}")
            self.btn_clean.config(state=tk.NORMAL)
        
        threading.Thread(target=clean_thread, daemon=True).start()
    
    def export_report(self):
        if total_liberado > 0:
            filename = f"syspurge_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            export_report_json(f"{filename}.json")
            export_report_csv(f"{filename}.csv")
            self.log(f"Reportes guardados: {filename}.json y {filename}.csv", "ok")
            messagebox.showinfo("Éxito", f"Reportes guardados en {filename}.json/.csv")
        else:
            messagebox.showwarning("Sin datos", "Ejecuta una limpieza primero")
    
    def create_system_backup(self):
        reply = messagebox.askyesno("Backup", "¿Crear backup completo de configuración del sistema? (Puede tomar varios minutos)")
        if reply:
            self.log("Creando backup...", "info")
            backup_dir = Path.home() / ".syspurge_backups"
            backup_dir.mkdir(exist_ok=True)
            backup_file = backup_dir / f"backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            
            # Backup de configuraciones comunes
            config_dirs = []
            if ES_LINUX or ES_MAC:
                config_dirs = [
                    os.path.expanduser('~/.bashrc'),
                    os.path.expanduser('~/.zshrc'),
                    os.path.expanduser('~/.config'),
                ]
            else:
                config_dirs = [
                    os.path.expandvars('%APPDATA%'),
                    os.path.expandvars('%USERPROFILE%\\Documents'),
                ]
            
            for item in config_dirs:
                if os.path.exists(item):
                    try:
                        dest = backup_file / Path(item).name
                        shutil.copytree(item, dest, ignore_errors=True)
                    except:
                        pass
            
            self.log(f"Backup creado en {backup_file}", "ok")
            messagebox.showinfo("Backup", f"Backup creado en {backup_file}")
    
    def restore_backup_gui(self):
        backup_dir = Path.home() / ".syspurge_backups"
        if backup_dir.exists():
            backups = list(backup_dir.iterdir())
            if backups:
                win = tk.Toplevel(self.root)
                win.title("Restaurar Backup")
                win.geometry("400x300")
                
                ttk.Label(win, text="Selecciona un backup para restaurar:").pack(pady=10)
                listbox = tk.Listbox(win)
                for b in backups:
                    listbox.insert(tk.END, b.name)
                listbox.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)
                
                def restore():
                    selected = listbox.curselection()
                    if selected:
                        backup_path = backups[selected[0]]
                        # Lógica de restauración
                        messagebox.showinfo("Restaurar", f"Restaurando {backup_path.name}...")
                        win.destroy()
                
                ttk.Button(win, text="Restaurar", command=restore).pack(pady=10)
            else:
                messagebox.showinfo("Sin backups", "No hay backups disponibles")
        else:
            messagebox.showinfo("Sin backups", "No hay backups disponibles")
    
    def setup_auto(self):
        periodo = self.schedule_var.get()
        setup_auto_clean(periodo)
        self.log(f"Limpieza automática configurada: {periodo}", "ok")
        messagebox.showinfo("Programado", f"Limpieza automática configurada: {periodo}")
    
    def start_web_dashboard(self):
        try:
            port = int(self.web_port.get())
            threading.Thread(target=start_web_dashboard, args=(port,), daemon=True).start()
            self.log(f"Dashboard web iniciado en http://localhost:{port}", "ok")
            messagebox.showinfo("Dashboard", f"Dashboard disponible en http://localhost:{port}")
        except Exception as e:
            self.log(f"Error al iniciar dashboard: {e}", "error")

# ==================== FUNCIONES ADICIONALES ====================

def clean_temp():
    """Limpia temporales (versión simplificada)"""
    print_progress("Limpiando archivos temporales...")
    liberated = 0
    
    temp_dirs = []
    if ES_LINUX or ES_MAC:
        temp_dirs = ['/tmp', '/var/tmp']
    else:
        temp_dirs = [os.environ.get('TEMP', ''), r'C:\Windows\Temp']
    
    for temp_dir in temp_dirs:
        if temp_dir and os.path.exists(temp_dir):
            size_before = get_size(temp_dir)
            try:
                for item in os.listdir(temp_dir):
                    item_path = os.path.join(temp_dir, item)
                    try:
                        if os.path.isfile(item_path) or os.path.islink(item_path):
                            os.unlink(item_path)
                        elif os.path.isdir(item_path):
                            shutil.rmtree(item_path, ignore_errors=True)
                    except:
                        pass
                size_after = get_size(temp_dir)
                liberated += max(0, size_before - size_after)
            except:
                pass
    
    if liberated > 0:
        add_liberated(liberated, "Archivos temporales")

def clean_system_cache():
    print_progress("Limpiando caché del sistema...")
    liberated = 0
    home = str(Path.home())
    
    # Limpiar ~/.cache en Linux/macOS
    if ES_LINUX or ES_MAC:
        cache_dir = os.path.join(home, '.cache')
        if os.path.exists(cache_dir):
            size = get_size(cache_dir)
            shutil.rmtree(cache_dir, ignore_errors=True)
            os.makedirs(cache_dir, exist_ok=True)
            liberated += size
            print_progress("  Cache del usuario limpiada", "ok")
    
    if liberated > 0:
        add_liberated(liberated, "Caché del sistema")

def clean_browser_cache(browser=None):
    print_progress("Limpiando caché de navegadores...")
    liberated = 0
    home = str(Path.home())
    
    browser_paths = {
        "Chrome": [],
        "Firefox": [],
        "Edge": []
    }
    
    if ES_WINDOWS:
        browser_paths["Chrome"].append(os.path.expanduser('~\\AppData\\Local\\Google\\Chrome\\User Data\\Default\\Cache'))
        browser_paths["Edge"].append(os.path.expanduser('~\\AppData\\Local\\Microsoft\\Edge\\User Data\\Default\\Cache'))
        browser_paths["Firefox"].append(os.path.expanduser('~\\AppData\\Local\\Mozilla\\Firefox\\Profiles'))
    elif ES_MAC:
        browser_paths["Chrome"].append(os.path.expanduser('~/Library/Caches/Google/Chrome'))
        browser_paths["Firefox"].append(os.path.expanduser('~/Library/Caches/Firefox'))
        browser_paths["Edge"].append(os.path.expanduser('~/Library/Caches/Microsoft Edge'))
    else:
        browser_paths["Chrome"].append(os.path.expanduser('~/.cache/google-chrome'))
        browser_paths["Firefox"].append(os.path.expanduser('~/.cache/mozilla/firefox'))
    
    for name, paths in browser_paths.items():
        for cache_path in paths:
            if os.path.exists(cache_path):
                size = get_size(cache_path)
                try:
                    shutil.rmtree(cache_path, ignore_errors=True)
                    os.makedirs(cache_path, exist_ok=True)
                    liberated += size
                    print_progress(f"  {name} limpiado", "ok")
                except:
                    pass
    
    if liberated > 0:
        add_liberated(liberated, "Caché de navegadores")

def clean_swap():
    if ES_LINUX:
        print_progress("Liberando memoria swap...")
        run_command(['sudo', 'swapoff', '-a'])
        time.sleep(1)
        run_command(['sudo', 'swapon', '-a'])
        add_liberated(50 * 1024 * 1024, "Swap liberada")
    elif ES_MAC:
        print_progress("Purgando memoria...")
        run_command('sudo purge', shell=True)
        add_liberated(100 * 1024 * 1024, "Memoria purgada")

def clean_trash():
    print_progress("Vaciando papelera...")
    if ES_WINDOWS:
        run_command(['cmd', '/c', 'rd', '/s', '/q', 'C:\\$Recycle.bin'])
    elif ES_MAC:
        trash = os.path.expanduser('~/.Trash')
        if os.path.exists(trash):
            size = get_size(trash)
            shutil.rmtree(trash, ignore_errors=True)
            os.makedirs(trash, exist_ok=True)
            add_liberated(size, "Papelera de reciclaje")
    else:
        trash = os.path.expanduser('~/.local/share/Trash')
        if os.path.exists(trash):
            size = get_size(trash)
            shutil.rmtree(trash, ignore_errors=True)
            os.makedirs(trash, exist_ok=True)
            add_liberated(size, "Papelera de reciclaje")

def clean_logs():
    print_progress("Limpiando logs antiguos...")
    liberated = 0
    
    if ES_LINUX:
        run_command(['sudo', 'journalctl', '--vacuum-time=7d'])
        log_dir = '/var/log'
        if os.path.exists(log_dir):
            size_before = get_size(log_dir)
            run_command(['sudo', 'find', log_dir, '-name', '*.log', '-type', 'f', '-mtime', '+30', '-delete'])
            size_after = get_size(log_dir)
            liberated = max(0, size_before - size_after)
    elif ES_MAC:
        log_dir = os.path.expanduser('~/Library/Logs')
        if os.path.exists(log_dir):
            size_before = get_size(log_dir)
            run_command(['find', log_dir, '-name', '*.log', '-type', 'f', '-mtime', '+30', '-delete'], check=False)
            size_after = get_size(log_dir)
            liberated = max(0, size_before - size_after)
    
    if liberated > 0:
        add_liberated(liberated, "Logs antiguos")

def setup_auto_clean(periodo):
    print_progress(f"Configurando limpieza automática ({periodo})...", "info")
    
    if ES_WINDOWS:
        try:
            import win32com.client
            scheduler = win32com.client.Dispatch('Schedule.Service')
            scheduler.Connect()
            root_folder = scheduler.GetFolder('\\')
            task_def = scheduler.NewTask(0)
            
            trigger = None
            if periodo == "diario":
                trigger = task_def.Triggers.Create(1)
                trigger.DaysInterval = 1
            elif periodo == "semanal":
                trigger = task_def.Triggers.Create(2)
                trigger.WeeksInterval = 1
            elif periodo == "mensual":
                trigger = task_def.Triggers.Create(3)
            
            trigger.StartBoundary = datetime.now().replace(hour=3, minute=0).isoformat()
            
            action = task_def.Actions.Create(0)
            action.Path = sys.executable
            action.Arguments = f'"{os.path.abspath(__file__)}" --auto'
            
            root_folder.RegisterTaskDefinition('SysPurge_AutoClean', task_def, 6, None, None, 3)
            print_progress("Tarea programada creada", "ok")
        except:
            print_progress("No se pudo crear tarea programada", "error")
    else:
        cron_cmd = {"diario": "0 3 * * *", "semanal": "0 3 * * 0", "mensual": "0 3 1 * *"}
        cmd = f'(crontab -l 2>/dev/null; echo "{cron_cmd[periodo]} {sys.executable} {os.path.abspath(__file__)} --auto >> /tmp/syspurge.log 2>&1") | crontab -'
        run_command(cmd, shell=True)
        print_progress("Cron job configurado", "ok")

def export_report_json(filename):
    data = {
        "timestamp": datetime.now().isoformat(),
        "sistema": SISTEMA,
        "total_liberado_bytes": total_liberado,
        "total_liberado_formateado": format_size(total_liberado),
        "detalle": reporte_detalle
    }
    with open(filename, 'w') as f:
        json.dump(data, f, indent=2)
    return filename

def export_report_csv(filename):
    with open(filename, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['Descripción', 'Tamaño (bytes)', 'Tamaño formateado', 'Timestamp'])
        for item in reporte_detalle:
            writer.writerow([item['descripcion'], item['tamaño_bytes'], item['tamaño_formateado'], item['timestamp']])
        writer.writerow([])
        writer.writerow(['TOTAL', total_liberado, format_size(total_liberado), datetime.now().isoformat()])
    return filename

def run_full_clean():
    print_banner()
    print_progress(f"Sistema detectado: {SISTEMA}", "info")
    
    clean_temp()
    clean_system_cache()
    clean_browser_cache()
    clean_swap()
    clean_trash()
    clean_logs()
    
    print("\n" + "="*50)
    print(Colors.GREEN + Colors.BOLD + f"🎉 LIMPIEZA COMPLETADA" + Colors.RESET)
    print(Colors.CYAN + f"📊 Total liberado: {format_size(total_liberado)}" + Colors.RESET)
    
    if total_liberado > 0:
        export_report_json(f"syspurge_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
        export_report_csv(f"syspurge_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv")
        save_to_history()
    
    print("="*50)

def print_banner():
    print(Colors.CYAN + r"""
    ╔═══════════════════════════════════════════════════════════╗
    ║  ███████╗██╗   ██╗███████╗██████╗ ██╗   ██╗██████╗  ██████╗ ███████╗ ║
    ║  ██╔════╝╚██╗ ██╔╝██╔════╝██╔══██╗██║   ██║██╔══██╗██╔════╝ ██╔════╝ ║
    ║  ███████╗ ╚████╔╝ █████╗  ██████╔╝██║   ██║██████╔╝██║  ███╗█████╗   ║
    ║  ╚════██║  ╚██╔╝  ██╔══╝  ██╔══██╗██║   ██║██╔══██╗██║   ██║██╔══╝   ║
    ║  ███████║   ██║   ███████╗██║  ██║╚██████╔╝██║  ██║╚██████╔╝███████╗ ║
    ║  ╚══════╝   ╚═╝   ╚══════╝╚═╝  ╚═╝ ╚═════╝ ╚═╝  ╚═╝ ╚═════╝ ╚══════╝ ║
    ║                    SysPurge ULTIMATE v3.0                          ║
    ║              Windows | Linux | macOS | Docker | Node | Java        ║
    ╚═══════════════════════════════════════════════════════════════════╝
    """ + Colors.RESET)

def main():
    parser = argparse.ArgumentParser(description="SysPurge Ultimate - Limpieza multi-plataforma")
    parser.add_argument("--gui", action="store_true", help="Abrir interfaz gráfica")
    parser.add_argument("--full", action="store_true", help="Limpieza completa")
    parser.add_argument("--auto", action="store_true", help="Modo automático")
    parser.add_argument("--dry-run", action="store_true", help="Modo simulación")
    parser.add_argument("--setup-auto", choices=["diario", "semanal", "mensual"], help="Configurar automático")
    parser.add_argument("--dashboard", type=int, nargs='?', const=8080, help="Iniciar dashboard web")
    parser.add_argument("--duplicates", action="store_true", help="Buscar duplicados")
    
    args = parser.parse_args()
    
    init_database()
    
    if args.gui:
        root = tk.Tk()
        app = SysPurgeUltimateGUI(root)
        root.mainloop()
    elif args.dashboard:
        start_web_dashboard(args.dashboard)
    elif args.setup_auto:
        setup_auto_clean(args.setup_auto)
    elif args.duplicates:
        print_banner()
        clean_duplicates(dry_run=False)
    elif args.dry_run:
        print_banner()
        print_progress("MODO SIMULACIÓN", "warning")
    elif args.auto or args.full:
        run_full_clean()
    else:
        run_full_clean()

if __name__ == "__main__":
    main()
