# 💀 SysPurge

**SysPurge** es una herramienta CLI ligera y poderosa para limpiar archivos innecesarios, liberar memoria swap, purgar cachés y optimizar el rendimiento de tu sistema operativo. Funciona tanto en **Windows** como en **Linux**.

> ¿Te quedaste sin espacio? ¿La PC va lenta? SysPurge es tu solución.

---

## ✨ Características

- ✅ Limpieza de caché del sistema (apt, pip, npm, pacman, etc.)
- ✅ Liberación de memoria swap
- ✅ Eliminación de archivos temporales (`/tmp`, `%TEMP%`)
- ✅ Vaciar papelera de reciclaje
- ✅ Limpiar logs antiguos (opcional)
- ✅ Eliminar paquetes huérfanos/obsoletos (Linux)
- ✅ Limpiar caché de navegadores (opcional)
- ✅ Modo seco (`--dry-run`) para ver qué se eliminará
- ✅ Colores en consola y barra de progreso
- ✅ Script único para ambos SOs

---

## 📦 Instalación

```bash
git clone https://github.com/Falconmx1/SysPurge.git
cd SysPurge
chmod +x syspurge.py  # Linux/Mac


🚀 Comandos Ultimate

# Interfaz gráfica completa (recomendado)
python syspurge.py --gui

# Dashboard web con estadísticas
python syspurge.py --dashboard 8080

# Buscar y eliminar duplicados
python syspurge.py --duplicates

# Limpieza completa con todos los módulos
python syspurge.py --full

# Configurar automático
python syspurge.py --setup-auto semanal

# Modo simulación (ver qué se eliminaría)
python syspurge.py --dry-run
