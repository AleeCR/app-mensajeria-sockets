# 🖥️ Cliente - Servidor en Python

Este proyecto implementa una comunicación **cliente-servidor** simple utilizando **sockets en Python**. En este modelo tradicional, el servidor escucha conexiones entrantes y puede manejar múltiples clientes simultáneamente, mientras que los clientes se conectan al servidor para enviar y recibir mensajes.

## 🚀 Cómo ejecutar

### 🔹 Servidor
1. Abre una terminal (PowerShell, CMD o consola de Linux).
2. Ejecuta el servidor indicando el puerto en el que escuchará:
```bash
python servidor.py <puerto>
```
**Ejemplo:**
```bash
python servidor.py 12345
```

### 🔹 Cliente
1. Abre otra terminal.
2. Ejecuta el cliente indicando la **IP del servidor** y el **puerto**:
```bash
python cliente.py <ip_servidor> <puerto>
```
**Ejemplo:**
```bash
python cliente.py 192.168.72.1 12345
```

## 🛠️ Notas importantes

- Reemplaza `<ip_servidor>` por la dirección IP donde se está ejecutando `servidor.py`.
- Para obtener tu IP en Windows:
  ```powershell
  ipconfig
  ```
- Para Linux/macOS:
  ```bash
  ifconfig
  ```
- Asegúrate de que el puerto no esté ocupado ni bloqueado por el firewall.
- Si corres servidor y cliente en la **misma máquina**, puedes usar:
  ```bash
  python cliente.py 127.0.0.1 <puerto>
  ```

## 📂 Requisitos

- Python 3 instalado
- Scripts `servidor.py` y `cliente.py` en la misma carpeta
- No se requieren librerías externas (solo `socket`)

## 📌 Ejemplo de uso

```bash
# Terminal 1 - Servidor
python servidor.py 12345

# Terminal 2 - Cliente
python cliente.py 127.0.0.1 12345
```