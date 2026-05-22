#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SysPurge - Herramienta de limpieza para Windows, Linux y macOS
Author: Falconmx1
License: MIT
Version: 2.0
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
from pathlib import Path
from datetime import datetime
import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
import threading

# ==================== CONFIGURACIÓN GLOBAL ====================

SISTEMA = platform.system()
ES_WINDOWS = SISTEMA == "Windows"
ES_LINUX = SISTEMA == "Linux"
ES_MAC = SISTEMA == "Darwin"

total_liberado = 0
reporte_detalle = []

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

# ==================== UTILIDADES ====================

def get_size(path):
    try:
        if os.path.isfile(path):
            return os.path.getsize(path)
        elif os.path.isdir(path):
            total = 0
            for dirpath, dirnames, filenames in os.walk(path):
                for f in filenames:
                    fp = os.path.join(dirpath, f)
                    if os.path.exists(fp):
                        total += os.path.getsize(fp)
            return total
    except:
        return 0
    return 0

def format_size(bytes):
    for unit in ['B', 'KB', 'MB', 'GB']:
        if bytes < 1024.0:
            return f"{bytes:.2f} {unit}"
        bytes /= 1024.0
    return f"{bytes:.2f} TB"

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
    if status == "ok":
        print(f"{Colors.GREEN}✅ {message}{Colors.RESET}")
    elif status == "error":
        print(f"{Colors.RED}❌ {message}{Colors.RESET}")
    elif status == "warning":
        print(f"{Colors.YELLOW}⚠️  {message}{Colors.RESET}")
    elif status == "info":
        print(f"{Colors.BLUE}➡️  {message}{Colors.RESET}")
    else:
        print(f"   {message}")

def run_command(cmd, shell=False):
    try:
        if shell:
            return subprocess.run(cmd, shell=True, capture_output=True, text=True)
        else:
            return subprocess.run(cmd, capture_output=True, text=True)
    except:
        return None

# ==================== MÓDULOS DE LIMPIEZA ====================

# ----- TEMPORALES -----
def clean_temp():
    print_progress("Limpiando archivos temporales...")
    liberated = 0
    
    if ES_LINUX:
        temp_dirs = ['/tmp', '/var/tmp']
    elif ES_MAC:
        temp_dirs = ['/tmp', '/var/tmp', os.path.expanduser('~/Library/Caches')]
    else:  # Windows
        temp_paths = [os.environ.get('TEMP', ''), os.environ.get('TMP', ''), r'C:\Windows\Temp']
        temp_dirs = [p for p in temp_paths if p and os.path.exists(p)]
    
    for temp_dir in temp_dirs:
        if os.path.exists(temp_dir):
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
                liberated += (size_before - size_after)
            except:
                pass
    
    if liberated > 0:
        add_liberated(liberated, "Archivos temporales")
    else:
        print_progress("No se encontraron temporales", "warning")

# ----- CACHÉ DEL SISTEMA -----
def clean_system_cache():
    print_progress("Limpiando cachés del sistema...")
    liberated = 0
    
    if ES_LINUX:
        if os.path.exists('/var/cache/apt/archives'):
            size_before = get_size('/var/cache/apt/archives')
            run_command(['sudo', 'apt-get', 'clean'])
            size_after = get_size('/var/cache/apt/archives')
            liberated += (size_before - size_after)
            print_progress("  APT cache limpiada", "ok")
        
        pip_cache = os.path.expanduser('~/.cache/pip')
        if os.path.exists(pip_cache):
            size_before = get_size(pip_cache)
            shutil.rmtree(pip_cache, ignore_errors=True)
            liberated += (size_before - get_size(pip_cache))
            print_progress("  PIP cache limpiada", "ok")
            
    elif ES_MAC:
        # Homebrew cache
        run_command('brew cleanup --prune=all', shell=True)
        # Librerías de sistema
        caches = ['~/Library/Caches', '~/Library/Logs', '~/Library/Application Support/Apple/Installer Cache']
        for cache in caches:
            cache_path = os.path.expanduser(cache)
            if os.path.exists(cache_path):
                size_before = get_size(cache_path)
                shutil.rmtree(cache_path, ignore_errors=True)
                os.makedirs(cache_path, exist_ok=True)
                liberated += (size_before - get_size(cache_path))
        
        # Xcode cache
        xcode_cache = os.path.expanduser('~/Library/Developer/Xcode/DerivedData')
        if os.path.exists(xcode_cache):
            size_before = get_size(xcode_cache)
            shutil.rmtree(xcode_cache, ignore_errors=True)
            liberated += (size_before - get_size(xcode_cache))
            print_progress("  Xcode cache limpiada", "ok")
    
    if liberated > 0:
        add_liberated(liberated, "Caché del sistema")

# ----- CACHÉ DE NAVEGADORES -----
def clean_browser_cache(browser=None):
    print_progress("Limpiando caché de navegadores...")
    liberated = 0
    
    browsers_to_clean = []
    if not browser or browser == "chrome":
        browsers_to_clean.append(("Chrome", get_chrome_cache_path()))
    if not browser or browser == "firefox":
        browsers_to_clean.append(("Firefox", get_firefox_cache_path()))
    if not browser or browser == "edge":
        browsers_to_clean.append(("Edge", get_edge_cache_path()))
    
    for name, cache_path in browsers_to_clean:
        if cache_path and os.path.exists(cache_path):
            size_before = get_size(cache_path)
            try:
                shutil.rmtree(cache_path, ignore_errors=True)
                os.makedirs(cache_path, exist_ok=True)
                size_after = get_size(cache_path)
                liberated += (size_before - size_after)
                print_progress(f"  {name} cache limpiada", "ok")
            except:
                print_progress(f"  No se pudo limpiar {name}", "error")
    
    if liberated > 0:
        add_liberated(liberated, "Caché de navegadores")

def get_chrome_cache_path():
    if ES_WINDOWS:
        return os.path.expanduser('~\\AppData\\Local\\Google\\Chrome\\User Data\\Default\\Cache')
    elif ES_MAC:
        return os.path.expanduser('~/Library/Caches/Google/Chrome')
    else:
        return os.path.expanduser('~/.cache/google-chrome')

def get_firefox_cache_path():
    if ES_WINDOWS:
        return os.path.expanduser('~\\AppData\\Local\\Mozilla\\Firefox\\Profiles')
    elif ES_MAC:
        return os.path.expanduser('~/Library/Caches/Firefox')
    else:
        return os.path.expanduser('~/.cache/mozilla/firefox')

def get_edge_cache_path():
    if ES_WINDOWS:
        return os.path.expanduser('~\\AppData\\Local\\Microsoft\\Edge\\User Data\\Default\\Cache')
    elif ES_MAC:
        return os.path.expanduser('~/Library/Caches/Microsoft Edge')
    else:
        return os.path.expanduser('~/.cache/microsoft-edge')

# ----- SWAP -----
def clean_swap():
    if ES_LINUX:
        print_progress("Liberando memoria swap...")
        try:
            result = run_command(['swapon', '--show'])
            if result and result.stdout:
                run_command(['sudo', 'swapoff', '-a'])
                time.sleep(1)
                run_command(['sudo', 'swapon', '-a'])
                print_progress("Swap reiniciada", "ok")
                add_liberated(50 * 1024 * 1024, "Swap liberada")
            else:
                print_progress("No hay swap activo", "warning")
        except:
            print_progress("Error al liberar swap", "error")
    elif ES_MAC:
        print_progress("macOS: liberando memoria...")
        run_command('sudo purge', shell=True)
        print_progress("Memoria purgada", "ok")
        add_liberated(100 * 1024 * 1024, "Memoria purgada")

# ----- PAPELERA -----
def clean_trash():
    print_progress("Vaciando papelera...")
    liberated = 0
    
    if ES_LINUX:
        trash_paths = ['~/.local/share/Trash', '~/.Trash']
    elif ES_MAC:
        trash_paths = ['~/.Trash']
    else:
        run_command(['cmd', '/c', 'rd', '/s', '/q', 'C:\\$Recycle.bin'])
        print_progress("Papelera vaciada", "ok")
        add_liberated(100 * 1024 * 1024, "Papelera de reciclaje")
        return
    
    for trash in trash_paths:
        trash_path = os.path.expanduser(trash)
        if os.path.exists(trash_path):
            size_before = get_size(trash_path)
            shutil.rmtree(trash_path, ignore_errors=True)
            os.makedirs(trash_path, exist_ok=True)
            liberated += (size_before - get_size(trash_path))
    
    if liberated > 0:
        add_liberated(liberated, "Papelera de reciclaje")
    else:
        print_progress("Papelera vacía", "warning")

# ----- LIMPIEZA DE LOGS -----
def clean_logs():
    print_progress("Limpiando logs antiguos...")
    
    if ES_LINUX:
        run_command(['sudo', 'journalctl', '--vacuum-time=7d'])
        log_dir = '/var/log'
        if os.path.exists(log_dir):
            size_before = get_size(log_dir)
            run_command(['sudo', 'find', log_dir, '-name', '*.log', '-type', 'f', '-mtime', '+30', '-delete'])
            size_after = get_size(log_dir)
            liberated = size_before - size_after
            if liberated > 0:
                add_liberated(liberated, "Logs antiguos")
    elif ES_MAC:
        run_command('sudo log rotate --all', shell=True)
        add_liberated(50 * 1024 * 1024, "Logs rotados")

# ----- PAQUETES HUÉRFANOS (Linux) -----
def clean_orphans():
    if ES_LINUX:
        print_progress("Limpiando paquetes huérfanos...")
        if shutil.which('apt-get'):
            run_command(['sudo', 'apt-get', 'autoremove', '-y'])
            add_liberated(200 * 1024 * 1024, "Paquetes huérfanos")
        elif shutil.which('pacman'):
            run_command(['sudo', 'pacman', '-Rns', '$(pacman -Qtdq)', '--noconfirm'], shell=True)
            add_liberated(200 * 1024 * 1024, "Paquetes huérfanos")

# ==================== REPORTES ====================

def export_report_json(filename=None):
    if not filename:
        filename = f"syspurge_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    
    data = {
        "timestamp": datetime.now().isoformat(),
        "sistema": SISTEMA,
        "total_liberado_bytes": total_liberado,
        "total_liberado_formateado": format_size(total_liberado),
        "detalle": reporte_detalle
    }
    
    with open(filename, 'w') as f:
        json.dump(data, f, indent=2)
    
    print_progress(f"Reporte JSON guardado: {filename}", "ok")
    return filename

def export_report_csv(filename=None):
    if not filename:
        filename = f"syspurge_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    
    with open(filename, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['Descripción', 'Tamaño (bytes)', 'Tamaño formateado', 'Timestamp'])
        for item in reporte_detalle:
            writer.writerow([item['descripcion'], item['tamaño_bytes'], item['tamaño_formateado'], item['timestamp']])
        
        writer.writerow([])
        writer.writerow(['TOTAL', total_liberado, format_size(total_liberado), datetime.now().isoformat()])
    
    print_progress(f"Reporte CSV guardado: {filename}", "ok")
    return filename

# ==================== PROGRAMACIÓN AUTOMÁTICA ====================

def setup_auto_clean(periodo="semanal"):
    """
    Configura limpieza automática
    periodo: diario, semanal, mensual
    """
    print_progress(f"Configurando limpieza automática ({periodo})...", "info")
    
    if ES_WINDOWS:
        import win32com.client
        scheduler = win32com.client.Dispatch('Schedule.Service')
        scheduler.Connect()
        root_folder = scheduler.GetFolder('\\')
        
        task_def = scheduler.NewTask(0)
        trigger = None
        
        if periodo == "diario":
            trigger = task_def.Triggers.Create(1)  # TASK_TRIGGER_DAILY
            trigger.DaysInterval = 1
        elif periodo == "semanal":
            trigger = task_def.Triggers.Create(2)  # TASK_TRIGGER_WEEKLY
            trigger.WeeksInterval = 1
        elif periodo == "mensual":
            trigger = task_def.Triggers.Create(3)  # TASK_TRIGGER_MONTHLY
        
        trigger.StartBoundary = datetime.now().isoformat()
        
        action = task_def.Actions.Create(0)
        action.Path = sys.executable
        action.Arguments = f'"{os.path.abspath(__file__)}" --full --auto'
        
        task_def.RegistrationInfo.Description = "SysPurge - Limpieza automática del sistema"
        task_def.Settings.Enabled = True
        task_def.Settings.Hidden = False
        
        root_folder.RegisterTaskDefinition(
            'SysPurge_AutoClean',
            task_def,
            6,  # TASK_CREATE_OR_UPDATE
            None,
            None,
            3  # TASK_LOGON_INTERACTIVE_TOKEN
        )
        print_progress("Tarea programada en Windows creada", "ok")
        
    elif ES_LINUX or ES_MAC:
        cron_cmd = {
            "diario": "0 3 * * *",
            "semanal": "0 3 * * 0",
            "mensual": "0 3 1 * *"
        }
        
        cmd = f'(crontab -l 2>/dev/null; echo "{cron_cmd[periodo]} {sys.executable} {os.path.abspath(__file__)} --full --auto >> /var/log/syspurge.log 2>&1") | crontab -'
        
        # Para macOS, usar launchd
        if ES_MAC:
            plist_path = os.path.expanduser('~/Library/LaunchAgents/com.syspurge.clean.plist')
            plist_content = f'''<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.syspurge.clean</string>
    <key>ProgramArguments</key>
    <array>
        <string>{sys.executable}</string>
        <string>{os.path.abspath(__file__)}</string>
        <string>--full</string>
        <string>--auto</string>
    </array>
    <key>StartCalendarInterval</key>
    <dict>
        <key>Hour</key><integer>3</integer>
        <key>Minute</key><integer>0</integer>
    </dict>
    <key>StandardOutPath</key><string>/tmp/syspurge.log</string>
    <key>StandardErrorPath</key><string>/tmp/syspurge.log</string>
</dict>
</plist>'''
            with open(plist_path, 'w') as f:
                f.write(plist_content)
            run_command(f'launchctl load {plist_path}', shell=True)
            print_progress("Tarea programada en macOS creada", "ok")
        else:
            run_command(cmd, shell=True)
            print_progress("Cron job configurado en Linux", "ok")
    else:
        print_progress("No se pudo configurar programación automática", "error")

# ==================== INTERFAZ GRÁFICA (Tkinter) ====================

class SysPurgeGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("SysPurge - Limpieza de Sistema")
        self.root.geometry("700x600")
        self.root.resizable(True, True)
        
        # Configurar estilo
        style = ttk.Style()
        style.theme_use('clam')
        
        # Frame principal
        main_frame = ttk.Frame(root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Título
        title_label = ttk.Label(main_frame, text="💀 SysPurge", font=('Arial', 20, 'bold'))
        title_label.grid(row=0, column=0, columnspan=2, pady=10)
        
        # Info del sistema
        sys_info = f"Sistema: {SISTEMA} | {platform.machine()}"
        info_label = ttk.Label(main_frame, text=sys_info, font=('Arial', 10))
        info_label.grid(row=1, column=0, columnspan=2, pady=5)
        
        # Frame de opciones
        options_frame = ttk.LabelFrame(main_frame, text="Opciones de limpieza", padding="10")
        options_frame.grid(row=2, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=10)
        
        self.var_temp = tk.BooleanVar(value=True)
        self.var_cache = tk.BooleanVar(value=True)
        self.var_browser = tk.BooleanVar(value=True)
        self.var_swap = tk.BooleanVar(value=True)
        self.var_trash = tk.BooleanVar(value=True)
        self.var_logs = tk.BooleanVar(value=False)
        
        ttk.Checkbutton(options_frame, text="Archivos temporales", variable=self.var_temp).grid(row=0, column=0, sticky=tk.W, pady=2)
        ttk.Checkbutton(options_frame, text="Caché del sistema", variable=self.var_cache).grid(row=1, column=0, sticky=tk.W, pady=2)
        ttk.Checkbutton(options_frame, text="Caché de navegadores", variable=self.var_browser).grid(row=2, column=0, sticky=tk.W, pady=2)
        ttk.Checkbutton(options_frame, text="Swap/Memoria", variable=self.var_swap).grid(row=0, column=1, sticky=tk.W, pady=2)
        ttk.Checkbutton(options_frame, text="Papelera de reciclaje", variable=self.var_trash).grid(row=1, column=1, sticky=tk.W, pady=2)
        ttk.Checkbutton(options_frame, text="Logs antiguos", variable=self.var_logs).grid(row=2, column=1, sticky=tk.W, pady=2)
        
        # Botones
        buttons_frame = ttk.Frame(main_frame)
        buttons_frame.grid(row=3, column=0, columnspan=2, pady=10)
        
        self.btn_clean = ttk.Button(buttons_frame, text="🧹 INICIAR LIMPIEZA", command=self.start_clean)
        self.btn_clean.grid(row=0, column=0, padx=5)
        
        ttk.Button(buttons_frame, text="📊 Exportar Reporte", command=self.export_report).grid(row=0, column=1, padx=5)
        ttk.Button(buttons_frame, text="⏰ Programar Auto", command=self.setup_auto).grid(row=0, column=2, padx=5)
        
        # Progreso
        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(main_frame, variable=self.progress_var, maximum=100)
        self.progress_bar.grid(row=4, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=10)
        
        # Log de salida
        log_frame = ttk.LabelFrame(main_frame, text="Registro de limpieza", padding="5")
        log_frame.grid(row=5, column=0, columnspan=2, sticky=(tk.W, tk.E, tk.N, tk.S), pady=10)
        
        self.log_text = scrolledtext.ScrolledText(log_frame, height=15, width=80, font=('Consolas', 9))
        self.log_text.pack(fill=tk.BOTH, expand=True)
        
        # Estadísticas
        self.stats_label = ttk.Label(main_frame, text="Total liberado: 0 B", font=('Arial', 10, 'bold'))
        self.stats_label.grid(row=6, column=0, columnspan=2, pady=5)
        
        # Configurar grid weights
        root.columnconfigure(0, weight=1)
        root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(0, weight=1)
        main_frame.rowconfigure(5, weight=1)
    
    def log(self, message, status="info"):
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_text.insert(tk.END, f"[{timestamp}] {message}\n")
        self.log_text.see(tk.END)
        self.root.update()
    
    def start_clean(self):
        self.btn_clean.config(state=tk.DISABLED)
        self.log_text.delete(1.0, tk.END)
        self.progress_var.set(0)
        
        def clean_thread():
            global total_liberado, reporte_detalle
            total_liberado = 0
            reporte_detalle = []
            
            steps = []
            if self.var_temp.get(): steps.append(clean_temp)
            if self.var_cache.get(): steps.append(clean_system_cache)
            if self.var_browser.get(): steps.append(clean_browser_cache)
            if self.var_swap.get(): steps.append(clean_swap)
            if self.var_trash.get(): steps.append(clean_trash)
            if self.var_logs.get(): steps.append(clean_logs)
            if ES_LINUX: steps.append(clean_orphans)
            
            total_steps = len(steps)
            for i, step in enumerate(steps):
                try:
                    self.log(f"Iniciando: {step.__name__.replace('_', ' ').title()}", "info")
                    
                    # Redirigir print a GUI
                    import io
                    old_stdout = sys.stdout
                    sys.stdout = captured = io.StringIO()
                    
                    step()
                    
                    sys.stdout = old_stdout
                    output = captured.getvalue()
                    for line in output.split('\n'):
                        if line.strip():
                            self.log(line, "ok" if "✅" in line else "info")
                    
                except Exception as e:
                    self.log(f"Error: {e}", "error")
                
                self.progress_var.set((i + 1) / total_steps * 100)
            
            self.log(f"\n🎉 LIMPIEZA COMPLETADA")
            self.log(f"📊 Total liberado: {format_size(total_liberado)}", "ok")
            self.stats_label.config(text=f"Total liberado: {format_size(total_liberado)}")
            self.btn_clean.config(state=tk.NORMAL)
        
        threading.Thread(target=clean_thread, daemon=True).start()
    
    def export_report(self):
        if total_liberado > 0:
            filename_json = export_report_json()
            filename_csv = export_report_csv()
            self.log(f"Reportes guardados: {filename_json} y {filename_csv}", "ok")
            messagebox.showinfo("Éxito", f"Reportes guardados:\n{filename_json}\n{filename_csv}")
        else:
            messagebox.showwarning("Sin datos", "Ejecuta una limpieza primero")
    
    def setup_auto(self):
        def set_schedule():
            periodo = combo.get()
            setup_auto_clean(periodo)
            messagebox.showinfo("Programado", f"Limpieza automática configurada: {periodo}")
            auto_win.destroy()
        
        auto_win = tk.Toplevel(self.root)
        auto_win.title("Programar limpieza automática")
        auto_win.geometry("300x150")
        auto_win.resizable(False, False)
        
        ttk.Label(auto_win, text="Selecciona frecuencia:").pack(pady=10)
        combo = ttk.Combobox(auto_win, values=["diario", "semanal", "mensual"], state="readonly")
        combo.set("semanal")
        combo.pack(pady=10)
        
        ttk.Button(auto_win, text="Configurar", command=set_schedule).pack(pady=10)

# ==================== MAIN CLI Y GUI ====================

def print_banner():
    print(Colors.CYAN + r"""
    ╔═══════════════════════════════════════╗
    ║  ███████╗██╗   ██╗███████╗██████╗ ██╗   ║
    ║  ██╔════╝╚██╗ ██╔╝██╔════╝██╔══██╗██║   ║
    ║  ███████╗ ╚████╔╝ █████╗  ██████╔╝██║   ║
    ║  ╚════██║  ╚██╔╝  ██╔══╝  ██╔══██╗██║   ║
    ║  ███████║   ██║   ███████╗██║  ██║█████╗║
    ║  ╚══════╝   ╚═╝   ╚══════╝╚═╝  ╚═╝╚════╝║
    ║            SysPurge v2.0               ║
    ║     Windows | Linux | macOS            ║
    ╚═══════════════════════════════════════╝
    """ + Colors.RESET)

def run_full_clean():
    print_banner()
    print_progress(f"Sistema detectado: {SISTEMA}", "info")
    
    clean_temp()
    clean_system_cache()
    clean_browser_cache()
    clean_swap()
    clean_trash()
    clean_logs()
    if ES_LINUX:
        clean_orphans()
    
    print("\n" + "="*50)
    print(Colors.GREEN + Colors.BOLD + f"🎉 LIMPIEZA COMPLETADA" + Colors.RESET)
    print(Colors.CYAN + f"📊 Total liberado: {format_size(total_liberado)}" + Colors.RESET)
    
    if total_liberado > 0:
        export_report_json()
        export_report_csv()
    
    print("="*50)

def dry_run():
    print_banner()
    print_progress("MODO SIMULACIÓN (nada se eliminará realmente)", "warning")
    print_progress("Esto es lo que se limpiaría:\n", "info")
    
    print("  • Archivos temporales")
    print("  • Caché del sistema")
    print("  • Caché de navegadores (Chrome, Firefox, Edge)")
    print("  • Swap / Memoria")
    print("  • Papelera de reciclaje")
    print("  • Logs antiguos")
    if ES_LINUX:
        print("  • Paquetes huérfanos")

def main():
    parser = argparse.ArgumentParser(description="SysPurge - Limpieza de sistema multi-plataforma")
    parser.add_argument("--full", action="store_true", help="Limpieza completa")
    parser.add_argument("--gui", action="store_true", help="Abrir interfaz gráfica")
    parser.add_argument("--auto", action="store_true", help="Ejecutar en modo automático (sin interacción)")
    parser.add_argument("--dry-run", action="store_true", help="Modo simulación")
    parser.add_argument("--setup-auto", choices=["diario", "semanal", "mensual"], help="Configurar limpieza automática")
    parser.add_argument("--browser", choices=["chrome", "firefox", "edge"], help="Limpiar caché de navegador específico")
    
    args = parser.parse_args()
    
    if args.gui:
        root = tk.Tk()
        app = SysPurgeGUI(root)
        root.mainloop()
    elif args.setup_auto:
        setup_auto_clean(args.setup_auto)
    elif args.dry_run:
        dry_run()
    elif args.browser:
        print_banner()
        clean_browser_cache(args.browser)
    elif args.auto:
        run_full_clean()
    elif args.full:
        run_full_clean()
    else:
        run_full_clean()

if __name__ == "__main__":
    if not args or (hasattr(args, 'gui') and not args.gui):
        if (ES_LINUX or ES_MAC) and os.geteuid() != 0:
            print(Colors.RED + "⚠️  Recomiendo ejecutar con sudo para máxima efectividad" + Colors.RESET)
    main()
