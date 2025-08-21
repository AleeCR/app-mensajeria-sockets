import socket
import sys
import os
import select
import tkinter as tk
from tkinter import scrolledtext, filedialog, simpledialog, messagebox
import subprocess
import platform
import json
import errno
import time
import requests # type: ignore

API_URL = "https://api-inference.huggingface.co/models/mistralai/Mistral-7B-Instruct-v0.1"
HF_TOKEN = "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"

headers = {
    "Authorization": f"Bearer {HF_TOKEN}"
}

def consulta_ia(prompt):
    payload = {
        "inputs": prompt,
        "parameters": {"max_new_tokens": 100},
    }
    response = requests.post(API_URL, headers=headers, json=payload)
    if response.status_code == 200:
        respuesta = response.json()
        return respuesta[0]["generated_text"]
    else:
        return f"Error {response.status_code}: {response.text}"

# Constantes
RECV_DIR = "archivos_recibidos"
BUFFER_SIZE = 4096

if not os.path.exists(RECV_DIR):
    os.makedirs(RECV_DIR)

class EstadoRecepcion:
    def __init__(self):
        self.buffer = b""
        self.recibiendo_archivo = False
        self.archivo = None
        self.nombre_archivo = ""
        self.bytes_restantes = 0
        self.remitente = ""
        self.last_file = None

class IAChatWindow:

    def __init__(self, master):
        self.window = tk.Toplevel(master)
        self.window.title("Chat con Hugging Face")
        self.window.geometry("500x400")

        # Área de mensajes
        self.chat_area = scrolledtext.ScrolledText(self.window, state='disabled', wrap='word')
        self.chat_area.pack(padx=10, pady=10, expand=True, fill=tk.BOTH)

        # Frame para entrada y botón enviar
        entry_frame = tk.Frame(self.window)
        entry_frame.pack(padx=10, pady=(0,10), fill=tk.X)

        self.entry = tk.Entry(entry_frame)
        self.entry.pack(side=tk.LEFT, expand=True, fill=tk.X)
        self.entry.focus_set()  # IMPORTANTE: activa el foco en la caja de texto
        self.entry.bind("<Return>", self.enviar_mensaje)

        self.send_button = tk.Button(entry_frame, text="Enviar", command=self.enviar_mensaje)
        self.send_button.pack(side=tk.RIGHT)

    def enviar_mensaje(self, event=None):
        mensaje = self.entry.get().strip()
        if not mensaje:
            return
        self.agregar_mensaje("Tú", mensaje)
        self.entry.delete(0, tk.END)

        respuesta = self.llamar_ia(mensaje)
        self.agregar_mensaje("IA", respuesta)

    def agregar_mensaje(self, remitente, texto):
        self.chat_area.configure(state='normal')
        self.chat_area.insert(tk.END, f"{remitente}: {texto}\n")
        self.chat_area.configure(state='disabled')
        self.chat_area.see(tk.END)

    def llamar_ia(self, prompt):
        payload = {
            "inputs": prompt,
            "parameters": {"max_new_tokens": 150},
        }
        try:
            response = requests.post(API_URL, headers=headers, json=payload)
            if response.status_code == 200:
                text = response.json()[0]["generated_text"]
                # Filtra la parte útil de la respuesta (quita lo que ya escribiste)
                if prompt in text:
                    parts = text.split(prompt)
                    respuesta = parts[-1].strip()
                else:
                    respuesta = text.strip()
                return respuesta

            else:
                return f"[Error {response.status_code}]: {response.text}"
        except Exception as e:
            return f"[ERROR] {e}"

class PeerChat:
    def __init__(self, master, server_host, server_port):
        self.master = master
        self.master.title("P2P Chat App")
        self.server_host = server_host
        self.server_port = server_port
        
        # Configuración de interfaz
        self.colors = ["#FF0000", "#008000", "#0000FF", "#800080", "#FF8C00", "#4B0082"]
        self.name_color_map = {}
        
        self.chat_area = scrolledtext.ScrolledText(master, state='normal', width=60, height=20)
        self.chat_area.pack(padx=10, pady=10)
        self.chat_area.tag_configure("Tú", foreground="#0000FF")
        self.chat_area.tag_configure("private", foreground="#008000")
        self.chat_area.tag_configure("notification", foreground="#FF8C00")
        
        self.entry_frame = tk.Frame(master)
        self.entry_frame.pack(padx=10, pady=(0,10), fill=tk.X)
        self.msg_entry = tk.Entry(self.entry_frame)
        self.msg_entry.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(0,10))
        self.msg_entry.bind("<Return>", self.send_message)
        
        self.send_button = tk.Button(self.entry_frame, text="Enviar", command=self.send_message)
        self.send_button.pack(side=tk.LEFT)
        
        self.file_button = tk.Button(master, text="Enviar Archivo", command=self.send_file)
        self.file_button.pack(pady=(0,10))
        
        self.priv_button = tk.Button(master, text="Mensaje Privado", command=self.send_private_message)
        self.priv_button.pack(pady=(0,10))
        
        self.open_file_button = tk.Button(master, text="Abrir Último Archivo", command=self.open_last_file, state="disabled")
        self.open_file_button.pack(pady=(0,10))
        self.ia_button = tk.Button(master, text="IA", command=self.abrir_chat_ia)
        self.ia_button.pack(pady=(0,10))

        self.estado = EstadoRecepcion()
        self.username = None
        self.server_socket = None
        self.listen_port = None
        self.directory_socket = None
        self.peers = {}
        self.socketlist = []
        self.message_cache = {}  # Para almacenar mensajes y evitar duplicados
        
        # Solicitar nombre de usuario
        self.username = simpledialog.askstring("Nombre", "Ingresa tu nombre:", parent=self.master)
        if not self.username:
            self.username = "Desconocido"
            
        self.initialize_p2p()
        self.master.after(100, self.check_messages)
        self.master.after(10000, self.ping_directory)  # Ping al servidor cada 10 segundos
        
        # Configurar cierre apropiado
        self.master.protocol("WM_DELETE_WINDOW", self.on_closing)

    def abrir_chat_ia(self):
        IAChatWindow(self.master)

    def on_closing(self):
        # Cerrar todas las conexiones
        try:
            if self.directory_socket:
                self.directory_socket.close()
                
            if self.server_socket:
                self.server_socket.close()
                
            for name, info in list(self.peers.items()):
                if info["socket"]:
                    info["socket"].close()
        except:
            pass
            
        self.master.destroy()

    def initialize_p2p(self):
        # Configurar socket servidor
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        
        # Enlazar a puerto disponible
        port = 8000
        for _ in range(100):
            try:
                self.server_socket.bind(('0.0.0.0', port))
                self.listen_port = port
                break
            except:
                port += 1
        
        if not self.listen_port:
            messagebox.showerror("Error", "No se pudo enlazar a ningún puerto")
            sys.exit(1)
            
        self.server_socket.listen(10)
        self.server_socket.setblocking(False)
        self.socketlist.append(self.server_socket)
        
        # Conectar al servidor de usuarios
        try:
            self.directory_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.directory_socket.connect((self.server_host, self.server_port))
            self.directory_socket.setblocking(False)
            self.socketlist.append(self.directory_socket)
            
            registro = json.dumps({
                "name": self.username, 
                "server_port": self.listen_port
            }).encode()
            self.directory_socket.send(registro)
            
            self.append_chat(f"Escuchando en puerto {self.listen_port}", "notification")
            
        except Exception as e:
            messagebox.showerror("Error", f"Error de conexión: {e}")
            sys.exit(1)

    def ping_directory(self):
        # Enviar ping al servidor de directorio para mantener la conexión
        # y obtener lista actualizada de peers
        if self.directory_socket:
            try:
                self.directory_socket.send(b"PING")
                # Programar siguiente ping
                self.master.after(10000, self.ping_directory)
            except:
                self.append_chat("Error enviando ping al servidor de directorio", "notification")
                # Intentar reconectar
                self.reconnect_directory()

    def reconnect_directory(self):
        # Intentar reconectar al servidor de directorio
        try:
            if self.directory_socket in self.socketlist:
                self.socketlist.remove(self.directory_socket)
            self.directory_socket.close()
            
            self.directory_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.directory_socket.connect((self.server_host, self.server_port))
            self.directory_socket.setblocking(False)
            self.socketlist.append(self.directory_socket)
            
            registro = json.dumps({
                "name": self.username, 
                "server_port": self.listen_port
            }).encode()
            self.directory_socket.send(registro)
            
            self.append_chat("Reconectado al servidor de directorio", "notification")
            self.master.after(10000, self.ping_directory)
        except Exception as e:
            self.append_chat(f"Error reconectando al servidor: {e}", "notification")
            # Intentar de nuevo después de un tiempo
            self.master.after(5000, self.reconnect_directory)

    def display_message(self, sender_name, message):
        if sender_name not in self.name_color_map:
            color_index = len(self.name_color_map) % len(self.colors)
            self.name_color_map[sender_name] = self.colors[color_index]
            self.chat_area.tag_configure(sender_name, foreground=self.name_color_map[sender_name])
        
        self.chat_area.insert(tk.END, f"{sender_name}: ", sender_name)
        self.chat_area.insert(tk.END, message + "\n")
        self.chat_area.see(tk.END)

    def check_messages(self):
        try:
            if not self.socketlist:
                self.master.after(100, self.check_messages)
                return
                
            read_sockets, _, _ = select.select(self.socketlist, [], [], 0)
            
            for sock in read_sockets:
                if sock == self.server_socket:
                    # Nueva conexión entrante
                    client_sock, addr = self.server_socket.accept()
                    client_sock.setblocking(False)
                    self.socketlist.append(client_sock)
                    self.append_chat(f"Nueva conexión de {addr}", "notification")
                
                elif sock == self.directory_socket:
                    # Datos del servidor de usuarios
                    data = sock.recv(BUFFER_SIZE)
                    if data:
                        self.process_directory_data(data)
                    else:
                        self.socketlist.remove(sock)
                        sock.close()
                        self.directory_socket = None
                        # Intentar reconectar
                        self.master.after(5000, self.reconnect_directory)
                
                else:
                    # Datos de un peer
                    try:
                        data = sock.recv(BUFFER_SIZE)
                        if data:
                            self.process_peer_data(sock, data)
                        else:
                            self.handle_peer_disconnect(sock)
                    except socket.error as e:
                        if e.errno != errno.EWOULDBLOCK and e.errno != 10035:
                            self.handle_peer_disconnect(sock)
                        
        except Exception as e:
            self.append_chat(f"Error: {e}", "notification")
        
        self.master.after(100, self.check_messages)

    def process_directory_data(self, data):
        try:
            # Corregir el problema de JSON extra data
            try:
                decoded_data = data.decode('utf-8')
                valid_json = decoded_data.strip()
                try:
                    peers_list = json.loads(valid_json)
                except json.JSONDecodeError as e:
                    pos = int(str(e).split('(char ')[1].split(')')[0])
                    valid_json = valid_json[:pos]
                    peers_list = json.loads(valid_json)
                
                # Conectar a todos los peers que no estén ya conectados
                for peer in peers_list:
                    if peer["name"] != self.username and peer["name"] not in self.peers:
                        self.connect_to_peer(peer)
                        
                # Verificar conexiones completas - todos los peers deben estar conectados entre sí
                self.verify_complete_mesh()
                
            except Exception as e:
                self.append_chat(f"Error procesando lista de peers: {e}", "notification")
        except Exception as e:
            self.append_chat(f"Error general: {e}", "notification")

    def verify_complete_mesh(self):
        # Asegurarse de que tengamos conexión con todos los peers
        # Este método se llama después de recibir una lista actualizada de peers
        for peer_name, peer_info in list(self.peers.items()):
            # Si el socket está cerrado o hay error, intentar reconectar
            try:
                # Probar envío de datos para verificar conexión
                peer_info["socket"].send(b"")
            except:
                # Socket inválido o cerrado, eliminar y reconectar
                if peer_info["socket"] in self.socketlist:
                    self.socketlist.remove(peer_info["socket"])
                
                # Intentar reconectar
                try:
                    new_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    new_socket.connect((peer_info["ip"], peer_info["port"]))
                    new_socket.setblocking(False)
                    
                    # Reenviar identificación
                    handshake = json.dumps({
                        "type": "connect", 
                        "name": self.username
                    }).encode()
                    new_socket.send(handshake)
                    
                    # Actualizar socket
                    self.peers[peer_name]["socket"] = new_socket
                    self.socketlist.append(new_socket)
                    self.append_chat(f"Reconectado a {peer_name}", "notification")
                except:
                    # No se pudo reconectar, mantener el status quo
                    pass

    def connect_to_peer(self, peer_info):
        try:
            peer_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            peer_socket.connect((peer_info["ip"], peer_info["port"]))
            peer_socket.setblocking(False)
            
            # Identificarse con el peer
            handshake = json.dumps({
                "type": "connect", 
                "name": self.username
            }).encode()
            peer_socket.send(handshake)
            
            self.peers[peer_info["name"]] = {
                "socket": peer_socket,
                "ip": peer_info["ip"],
                "port": peer_info["port"]
            }
            self.socketlist.append(peer_socket)
            
            self.append_chat(f"Conectado a {peer_info['name']}", "notification")
            
        except Exception as e:
            self.append_chat(f"Error conectando a {peer_info['name']}: {e}", "notification")

    def process_peer_data(self, sock, data):
        try:
            # Intentar decodificar como JSON (para mensajes de control y chat)
            try:
                message = data.decode('utf-8')
                # Si el mensaje es JSON, procesarlo según su tipo
                if message.startswith("{"):
                    info = json.loads(message)
                    if info.get("type") == "connect":
                        peer_name = info["name"]
                        peer_addr = sock.getpeername()
                        
                        self.peers[peer_name] = {
                            "socket": sock,
                            "ip": peer_addr[0],
                            "port": peer_addr[1]
                        }
                        
                        if peer_name not in self.name_color_map:
                            color_index = len(self.name_color_map) % len(self.colors)
                            self.name_color_map[peer_name] = self.colors[color_index]
                            self.chat_area.tag_configure(peer_name, foreground=self.name_color_map[peer_name])
                        
                        self.append_chat(f"{peer_name} se ha conectado", "notification")
                        return
                    elif info.get("type") == "message":
                        sender_name = info.get("name", "Desconocido")
                        text = info.get("message", "")
                        message_id = info.get("id", "")
                        
                        # Verificar si el mensaje ya se ha recibido para evitar duplicados
                        if message_id not in self.message_cache:
                            self.message_cache[message_id] = time.time()
                            self.display_message(sender_name, text)
                            
                            # Reenviar el mensaje a todos los demás peers para asegurar distribución completa
                            self.relay_message(info, sock)
                        return
                    elif info.get("type") == "relay":
                        # Mensaje reenviado desde otro peer
                        original_message = info.get("original_message", {})
                        if original_message:
                            sender_name = original_message.get("name", "Desconocido")
                            text = original_message.get("message", "")
                            message_id = original_message.get("id", "")
                            
                            # Verificar si el mensaje ya se ha recibido
                            if message_id not in self.message_cache:
                                self.message_cache[message_id] = time.time()
                                self.display_message(sender_name, text)
                                
                                # Seguir reenviando
                                self.relay_message(original_message, sock)
                        return
                # Procesar mensajes privados
                if message.startswith("[PRIVADO]"):
                    self.append_chat(message, "private")
                    return
                    
                # Si no es JSON, se asume que es un mensaje plano y se busca identificar el remitente por el socket
                sender_name = None
                for name, info in self.peers.items():
                    if info["socket"] == sock:
                        sender_name = name
                        break
                
                if sender_name:
                    self.display_message(sender_name, message)
                
            except UnicodeDecodeError:
                # Es un archivo o datos binarios
                self.process_file_data(sock, data)
                
        except Exception as e:
            self.append_chat(f"Error procesando datos: {e}", "notification")

    def relay_message(self, message, source_socket):
        # Reenviar el mensaje a todos los peers excepto el remitente original
        for name, peer in self.peers.items():
            if peer["socket"] != source_socket:
                try:
                    # Si es un mensaje original, reenviarlo como relay
                    if message.get("type") == "message":
                        relay_msg = json.dumps({
                            "type": "relay",
                            "original_message": message
                        }).encode()
                        peer["socket"].sendall(relay_msg)
                    # Si ya es un relay, pasar el mensaje original
                    elif message.get("type") == "relay":
                        peer["socket"].sendall(json.dumps(message).encode())
                    else:
                        # Caso para mensajes directos, reenviar tal cual
                        peer["socket"].sendall(json.dumps(message).encode())
                except Exception as e:
                    self.append_chat(f"Error reenviando a {name}: {e}", "notification")

    def process_file_data(self, sock, data):
        try:
            # Si no estamos recibiendo un archivo, comprobar si es el inicio de uno
            if not self.estado.recibiendo_archivo:
                try:
                    header_end = data.find(b"\n")
                    if header_end != -1:
                        header = data[:header_end].decode()
                        if "envía archivo:" in header:
                            parts = header.split(" envía archivo: ")
                            sender = parts[0]
                            filename, filesize = parts[1].split("|")
                            
                            self.estado.recibiendo_archivo = True
                            self.estado.bytes_restantes = int(filesize)
                            self.estado.remitente = sender
                            self.estado.nombre_archivo = filename
                            self.estado.last_file = os.path.join(RECV_DIR, filename)
                            self.estado.archivo = open(self.estado.last_file, "wb")
                            
                            data = data[header_end+1:]
                            self.append_chat(f"Recibiendo archivo {filename} de {sender}", "notification")
                except:
                    pass
            
            if self.estado.recibiendo_archivo and self.estado.archivo:
                self.estado.archivo.write(data)
                self.estado.bytes_restantes -= len(data)
                
                if self.estado.bytes_restantes <= 0:
                    self.estado.archivo.close()
                    self.append_chat(f"Archivo recibido: {self.estado.nombre_archivo} de {self.estado.remitente}", "notification")
                    self.open_file_button.config(state="normal")
                    
                    self.estado.recibiendo_archivo = False
                    self.estado.archivo = None
                    
        except Exception as e:
            self.append_chat(f"Error procesando archivo: {e}", "notification")
            if self.estado.archivo:
                self.estado.archivo.close()
            self.estado.recibiendo_archivo = False

    def send_message(self, event=None):
        message = self.msg_entry.get().strip()
        if message:
            # Generar un ID único para el mensaje (evita duplicados)
            message_id = f"{self.username}_{time.time()}"
            
            # Estructurar el mensaje en JSON incluyendo ID y remitente
            msg_data = json.dumps({
                "type": "message",
                "id": message_id,
                "name": self.username,
                "message": message
            }).encode()
            
            # Añadir a la caché para evitar procesarlo al recibirlo de vuelta
            self.message_cache[message_id] = time.time()
            
            # Enviar mensaje a todos los peers
            sent_to_anyone = False
            for name, peer in self.peers.items():
                try:
                    peer["socket"].sendall(msg_data)
                    sent_to_anyone = True
                except Exception as e:
                    self.append_chat(f"Error enviando a {name}: {e}", "notification")
            
            # Mostrar en el chat local
            self.chat_area.insert(tk.END, "Tú: ", "Tú")
            self.chat_area.insert(tk.END, message + "\n")
            self.chat_area.see(tk.END)
            
            self.msg_entry.delete(0, tk.END)
            
            # Si no se pudo enviar a nadie, mostrar advertencia
            if not sent_to_anyone and self.peers:
                self.append_chat("Advertencia: No se pudo enviar el mensaje a ningún peer", "notification")
                # Intentar refrescar conexiones
                self.verify_complete_mesh()

    def send_file(self):
        filepath = filedialog.askopenfilename(title="Selecciona un archivo")
        if not filepath: 
            return
        
        try:
            filename = os.path.basename(filepath)
            filesize = os.path.getsize(filepath)
            
            header = f"{self.username} envía archivo: {filename}|{filesize}\n".encode()
            
            for name, peer in self.peers.items():
                try:
                    peer["socket"].sendall(header)
                    with open(filepath, "rb") as f:
                        while True:
                            chunk = f.read(BUFFER_SIZE)
                            if not chunk: 
                                break
                            peer["socket"].sendall(chunk)
                except Exception as e:
                    self.append_chat(f"Error enviando archivo a {name}: {e}", "notification")
            
            self.append_chat(f"Archivo enviado: {filename}", "notification")
            
        except Exception as e:
            self.append_chat(f"Error preparando archivo: {e}", "notification")

    def send_private_message(self):
        target = simpledialog.askstring("Mensaje Privado", "Destinatario:")
        if not target:
            return
            
        if target not in self.peers:
            messagebox.showerror("Error", f"Usuario {target} no encontrado")
            return
        
        message = simpledialog.askstring("Mensaje Privado", "Mensaje:")
        if not message:
            return
        
        try:
            full_msg = f"[PRIVADO] {self.username}: {message}".encode()
            self.peers[target]["socket"].sendall(full_msg)
            
            self.chat_area.insert(tk.END, f"[Privado a {target}]: ", "private")
            self.chat_area.insert(tk.END, message + "\n")
            self.chat_area.see(tk.END)
            
        except Exception as e:
            self.append_chat(f"Error enviando mensaje privado: {e}", "notification")
    
    def append_chat(self, text, tag=None):
        self.chat_area.insert(tk.END, text + "\n", tag)
        self.chat_area.see(tk.END)

    def open_last_file(self):
        if self.estado.last_file and os.path.exists(self.estado.last_file):
            try:
                if platform.system() == "Windows":
                    os.startfile(self.estado.last_file)
                else:
                    opener = "open" if platform.system() == "Darwin" else "xdg-open"
                    subprocess.call([opener, self.estado.last_file])
            except Exception as e:
                messagebox.showerror("Error", f"No se pudo abrir el archivo: {e}")
        else:
            messagebox.showinfo("Info", "No hay archivos recibidos aún")

    def handle_peer_disconnect(self, sock):
        for name, info in list(self.peers.items()):
            if info["socket"] == sock:
                self.append_chat(f"{name} se ha desconectado", "notification")
                del self.peers[name]
                break
                
        if sock in self.socketlist:
            self.socketlist.remove(sock)
        sock.close()

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Uso: python peer.py <servidor_usuarios> <puerto_usuarios>")
        sys.exit(1)
    
    root = tk.Tk()
    app = PeerChat(root, sys.argv[1], int(sys.argv[2]))
    root.mainloop()
