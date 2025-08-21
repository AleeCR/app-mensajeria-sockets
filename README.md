# 💬 App de Mensajería Local con Sockets

Proyecto en Python de una aplicación de mensajería local implementada con **dos modelos de comunicación**:  
- Cliente-Servidor  
- Peer-to-Peer (P2P)  

Ambos modelos usan **sockets TCP** y la función **select** para manejar múltiples conexiones sin necesidad de hilos.

---

## 🔹 Modelos implementados
### 1️⃣ Cliente-Servidor
- Un servidor central acepta múltiples clientes.  
- Los mensajes de un cliente se reenvían al resto.  
- Uso de `select` para manejar varios sockets de forma simultánea.  

### 2️⃣ Peer-to-Peer (P2P)
- Cada nodo puede enviar y recibir mensajes sin servidor central.  
- Conexión directa entre pares.  
- Uso de `select` para escuchar múltiples sockets a la vez.  

---

## 💻 Tecnologías
- Python  
- Sockets TCP  
- select (I/O multiplexing)

---
