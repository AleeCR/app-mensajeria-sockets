# 🔗 Modelo Peer-to-Peer (P2P) en Python

Este proyecto implementa una comunicación **peer-to-peer (P2P)** utilizando **sockets en Python**. En este modelo no existe un servidor central: los nodos se conectan directamente entre sí para intercambiar mensajes en tiempo real. El manejo de múltiples conexiones se realiza con `select`, sin necesidad de usar hilos.

## 🚀 Cómo ejecutar

### 🔹 Nodo 1
1. Abre una terminal (PowerShell, CMD o consola de Linux).
2. Ejecuta el nodo indicando el puerto en el que escuchará:
```bash
python nodo1.py <puerto>
```
**Ejemplo:**
```bash
python nodo1.py 12345
```

### 🔹 Nodo 2
1. Abre otra terminal.
2. Ejecuta el nodo indicando la **IP de Nodo 1** y el **puerto** en el que está escuchando:
```bash
python nodo2.py <ip_nodo1> <puerto>
```
**Ejemplo:**
```bash
python nodo2.py 192.168.72.1 12345
```

## 🛠️ Notas importantes

- Reemplaza `<ip_nodo1>` por la dirección IP donde se está ejecutando `nodo1.py`.
- Para obtener tu IP en Windows:
  ```powershell
  ipconfig
  ```
- Para Linux/macOS:
  ```bash
  ifconfig
  ```
- Asegúrate de que el puerto no esté ocupado ni bloqueado por el firewall.
- Si corres ambos nodos en la **misma máquina**, puedes usar:
  ```bash
  python nodo2.py 127.0.0.1 <puerto>
  ```

## 📂 Requisitos

- Python 3 instalado
- Scripts `nodo1.py` y `nodo2.py` en la misma carpeta
- No se requieren librerías externas (solo `socket` y `select`)

## 📌 Ejemplo de uso

```bash
# Terminal 1 - Nodo 1
python nodo1.py 12345

# Terminal 2 - Nodo 2
python nodo2.py 127.0.0.1 12345
```