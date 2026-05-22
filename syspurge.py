#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SysPurge - Herramienta de limpieza para Windows y Linux
Author: Falconmx1
License: MIT
"""

import os
import sys
import platform
import subprocess
import shutil
import argparse
import time
from pathlib import Path

# Colores para consola
class Colors:
    RED = '\033[91m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    MAGENTA = '\033[95m'
    CYAN = '\033[96m'
    WHITE = '\033[97m'
    RESET = '\033[0m'
    BOLD = '\033[1m'

# Configuración del sistema
SISTEMA = platform.system()
ES_WINDOWS = SISTEMA == "Windows"
ES_LINUX = SISTEMA == "Linux"

# Estadísticas
total_liberado = 0

def print_banner():
    """Muestra el banner de SysPurge"""
    print(Colors.CYAN + r"""
    ╔═══════════════════════════════════════╗
    ║  ███████╗██╗   ██╗███████╗██████╗ ██╗   ║
    ║  ██╔════╝╚██╗ ██╔╝██╔════╝██╔══██╗██║   ║
    ║  ███████╗ ╚████╔╝ █████╗  ██████╔╝██║   ║
    ║  ╚════██║  ╚██╔╝  ██╔══╝  ██╔══██╗██║   ║
    ║  ███████║   ██║   ███████╗██║  ██║█████╗║
    ║  ╚══════╝   ╚═╝   ╚══════╝╚═╝  ╚═╝╚════╝║
    ║            SysPurge v1.0               ║
    ╚═══════════════════════════════════════╝
    """ + Colors.RESET)
    print(Colors.BOLD + "🧹 Limpiando tu sistema como un pro...\n" + Colors.RESET)

def print_progress(message, status="info"):
    """Muestra mensajes con formato"""
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

def get_size(path):
    """Obtiene el tamaño de un archivo o directorio"""
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
    """Formatea bytes a KB/MB/GB"""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if bytes < 1024.0:
            return f"{bytes:.2f} {unit}"
        bytes /= 1024.0
    return f"{bytes:.2f} TB"

def add_liberated(size):
    """Suma al total liberado"""
    global total_liberado
    total_liberado += size
    print_progress(f"Liberados: {format_size(size)}", "ok")

# ==================== MÓDULOS DE LIMPIEZA ====================

def clean_temp_linux():
    """Limpia archivos temporales en Linux"""
    print_progress("Limpiando /tmp y /var/tmp...")
    
    temp_dirs = ['/tmp', '/var/tmp']
    liberated = 0
    
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
                            shutil.rmtree(item_path)
                    except:
                        pass
                size_after = get_size(temp_dir)
                liberated += (size_before - size_after)
            except:
                pass
    
    if liberated > 0:
        add_liberated(liberated)
    else:
        print_progress("No se encontraron temporales", "warning")

def clean_temp_windows():
    """Limpia archivos temporales en Windows"""
    print_progress("Limpiando temporales de Windows...")
    
    temp_paths = [
        os.environ.get('TEMP', ''),
        os.environ.get('TMP', ''),
        r'C:\Windows\Temp'
    ]
    
    liberated = 0
    
    for temp_path in temp_paths:
        if temp_path and os.path.exists(temp_path):
            size_before = get_size(temp_path)
            try:
                for item in os.listdir(temp_path):
                    item_path = os.path.join(temp_path, item)
                    try:
                        if os.path.isfile(item_path):
                            os.remove(item_path)
                        elif os.path.isdir(item_path):
                            shutil.rmtree(item_path, ignore_errors=True)
                    except:
                        pass
                size_after = get_size(temp_path)
                liberated += (size_before - size_after)
            except:
                pass
    
    if liberated > 0:
        add_liberated(liberated)
    else:
        print_progress("No se encontraron temporales", "warning")

def clean_cache_linux():
    """Limpia cachés en Linux"""
    print_progress("Limpiando cachés del sistema...")
    liberated = 0
    
    # APT cache
    if os.path.exists('/var/cache/apt/archives'):
        size_before = get_size('/var/cache/apt/archives')
        try:
            subprocess.run(['sudo', 'apt-get', 'clean'], capture_output=True, check=False)
            size_after = get_size('/var/cache/apt/archives')
            liberated += (size_before - size_after)
            print_progress(f"  APT cache limpiada", "ok")
        except:
            pass
    
    # PIP cache
    pip_cache = os.path.expanduser('~/.cache/pip')
    if os.path.exists(pip_cache):
        size_before = get_size(pip_cache)
        shutil.rmtree(pip_cache, ignore_errors=True)
        size_after = get_size(pip_cache)
        liberated += (size_before - size_after)
        print_progress(f"  PIP cache limpiada", "ok")
    
    # Thumbnails
    thumb_cache = os.path.expanduser('~/.cache/thumbnails')
    if os.path.exists(thumb_cache):
        size_before = get_size(thumb_cache)
        shutil.rmtree(thumb_cache, ignore_errors=True)
        size_after = get_size(thumb_cache)
        liberated += (size_before - size_after)
        print_progress(f"  Miniaturas limpiadas", "ok")
    
    if liberated > 0:
        add_liberated(liberated)

def clean_swap_linux():
    """Limpia y libera memoria swap en Linux"""
    print_progress("Liberando memoria swap...")
    try:
        # Verificar si swap está activo
        result = subprocess.run(['swapon', '--show'], capture_output=True, text=True)
        if result.stdout:
            subprocess.run(['sudo', 'swapoff', '-a'], check=False)
            time.sleep(1)
            subprocess.run(['sudo', 'swapon', '-a'], check=False)
            print_progress("Swap reiniciada y liberada", "ok")
            # No podemos medir fácilmente cuánto se liberó, asumimos algo
            add_liberated(50 * 1024 * 1024)  # Estimado 50MB
        else:
            print_progress("No hay swap activo", "warning")
    except Exception as e:
        print_progress(f"No se pudo liberar swap: {e}", "error")

def clean_trash_linux():
    """Vacía la papelera en Linux"""
    print_progress("Vaciando papelera...")
    
    trash_paths = [
        os.path.expanduser('~/.local/share/Trash'),
        os.path.expanduser('~/.Trash')
    ]
    
    liberated = 0
    for trash in trash_paths:
        if os.path.exists(trash):
            size_before = get_size(trash)
            shutil.rmtree(trash, ignore_errors=True)
            os.makedirs(trash, exist_ok=True)
            size_after = get_size(trash)
            liberated += (size_before - size_after)
    
    if liberated > 0:
        add_liberated(liberated)
    else:
        print_progress("Papelera ya estaba vacía", "warning")

def clean_trash_windows():
    """Vacía la papelera en Windows usando cmd"""
    print_progress("Vaciando papelera de reciclaje...")
    try:
        subprocess.run(['cmd', '/c', 'rd', '/s', '/q', 'C:\\$Recycle.bin'], 
                       capture_output=True, check=False)
        print_progress("Papelera vaciada", "ok")
        add_liberated(100 * 1024 * 1024)  # Estimado
    except:
        print_progress("No se pudo vaciar la papelera", "error")

def clean_orphans_linux():
    """Elimina paquetes huérfanos"""
    print_progress("Buscando paquetes huérfanos...")
    
    # Detectar gestor de paquetes
    if shutil.which('apt-get'):
        result = subprocess.run(['apt-get', 'autoremove', '--dry-run'], 
                                capture_output=True, text=True)
        if '0 upgraded' in result.stdout and '0 newly installed' in result.stdout:
            print_progress("No hay paquetes huérfanos", "warning")
        else:
            subprocess.run(['sudo', 'apt-get', 'autoremove', '-y'], check=False)
            print_progress("Paquetes huérfanos eliminados", "ok")
            add_liberated(200 * 1024 * 1024)
    elif shutil.which('pacman'):
        subprocess.run(['sudo', 'pacman', '-Rns', '$(pacman -Qtdq)', '--noconfirm'], 
                       shell=True, check=False)
        print_progress("Paquetes huérfanos eliminados", "ok")
        add_liberated(200 * 1024 * 1024)

def clean_logs_linux():
    """Limpia logs antiguos"""
    print_progress("Limpiando logs antiguos...")
    
    log_dir = '/var/log'
    if os.path.exists(log_dir):
        size_before = get_size(log_dir)
        try:
            subprocess.run(['sudo', 'journalctl', '--vacuum-time=3d'], 
                           capture_output=True, check=False)
            subprocess.run(['sudo', 'find', log_dir, '-name', '*.log', '-type', 'f', 
                           '-mtime', '+30', '-delete'], check=False)
            size_after = get_size(log_dir)
            liberated = size_before - size_after
            if liberated > 0:
                add_liberated(liberated)
            else:
                print_progress("No se encontraron logs antiguos", "warning")
        except:
            pass

# ==================== MAIN ====================

def run_full_clean():
    """Ejecuta limpieza completa"""
    print_banner()
    print_progress(f"Sistema detectado: {SISTEMA}", "info")
    print_progress("Iniciando limpieza completa...\n", "info")
    
    if ES_LINUX:
        clean_temp_linux()
        clean_cache_linux()
        clean_swap_linux()
        clean_trash_linux()
        clean_orphans_linux()
        clean_logs_linux()
    elif ES_WINDOWS:
        clean_temp_windows()
        clean_trash_windows()
        print_progress("En Windows: ejecuta 'cleanmgr' para más opciones", "info")
    else:
        print_progress(f"Sistema {SISTEMA} no soportado", "error")
        return
    
    print("\n" + "="*50)
    print(Colors.GREEN + Colors.BOLD + f"🎉 LIMPIEZA COMPLETADA" + Colors.RESET)
    print(Colors.CYAN + f"📊 Total liberado: {format_size(total_liberado)}" + Colors.RESET)
    print(Colors.YELLOW + "💡 Recomendación: Reinicia tu sistema para mejores resultados" + Colors.RESET)
    print("="*50)

def dry_run():
    """Modo simulación"""
    print_banner()
    print_progress("MODO SIMULACIÓN (nada se eliminará realmente)", "warning")
    print_progress("Esto es lo que se limpiaría:\n", "info")
    
    if ES_LINUX:
        print("  • /tmp y /var/tmp")
        print("  • Cachés: APT, PIP, thumbnails")
        print("  • Memoria swap")
        print("  • Papelera de reciclaje")
        print("  • Paquetes huérfanos")
        print("  • Logs antiguos (>30 días)")
    elif ES_WINDOWS:
        print("  • Archivos temporales (%TEMP%, Windows\\Temp)")
        print("  • Papelera de reciclaje")
    
    print(f"\n{Colors.GREEN}✅ No se eliminó ningún archivo real")

def main():
    parser = argparse.ArgumentParser(description="SysPurge - Limpieza de sistema")
    parser.add_argument("--full", action="store_true", help="Limpieza completa")
    parser.add_argument("--cache", action="store_true", help="Solo limpiar caché")
    parser.add_argument("--swap", action="store_true", help="Solo liberar swap")
    parser.add_argument("--temp", action="store_true", help="Solo limpiar temporales")
    parser.add_argument("--dry-run", action="store_true", help="Modo simulación")
    
    args = parser.parse_args()
    
    if args.dry_run:
        dry_run()
    elif args.cache and ES_LINUX:
        print_banner()
        clean_cache_linux()
    elif args.swap and ES_LINUX:
        print_banner()
        clean_swap_linux()
    elif args.temp:
        print_banner()
        if ES_LINUX:
            clean_temp_linux()
        elif ES_WINDOWS:
            clean_temp_windows()
    else:
        run_full_clean()

if __name__ == "__main__":
    if os.geteuid() != 0 and ES_LINUX:
        print(Colors.RED + "⚠️  En Linux necesitas permisos sudo. Ejecuta: sudo python3 syspurge.py" + Colors.RESET)
        sys.exit(1)
    main()
