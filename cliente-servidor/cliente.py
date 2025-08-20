import socket
import sys
import os
import select
import tkinter as tk
from tkinter import scrolledtext, filedialog, simpledialog, messagebox
import subprocess
import platform

# Constantes
RECV_DIR = "archivos_recibidos"
BUFFER_SIZE = 4096
SEPARATOR = b"<SEP>"
FILE_PREFIX = b"FILE:"

if not os.path.exists(RECV_DIR):
    os.makedirs(RECV_DIR)

class EstadoRecepcion:
    def __init__(self):
        self.buffer = b""
        self.recibiendo_archivo = False
        self.archivo = None
        self.bytes_restantes = 0
        self.last_file = None  # Almacena la ruta del último archivo recibido

class ChatClient:
    def __init__(self, master, host, port):
        self.master = master
        self.master.title("Chat App")
        self.host = host
        self.port = port

        # Colores asignados a cada usuario
        self.colors = ["#FF0000", "#008000", "#0000FF", "#800080"]
        self.name_color_map = {}

        # Área de chat y configuración de tags
        self.chat_area = scrolledtext.ScrolledText(master, state='normal', width=60, height=20)
        self.chat_area.pack(padx=10, pady=10)
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

        # Botón para abrir el último archivo recibido (inicialmente deshabilitado)
        self.open_file_button = tk.Button(master, text="Abrir Último Archivo", command=self.open_last_file, state="disabled")
        self.open_file_button.pack(pady=(0,10))

        self.estado = EstadoRecepcion()

        try:
            self.s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.s.connect((self.host, self.port))
            self.s.setblocking(False)
        except Exception as e:
            messagebox.showerror("Error de conexión", f"No se pudo conectar a {self.host}:{self.port}\n{e}")
            sys.exit(1)

        self.username = simpledialog.askstring("Nombre", "Ingresa tu nombre:", parent=self.master)
        if not self.username:
            self.username = "Desconocido"

        try:
            self.s.sendall(self.username.encode())
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo enviar el nombre al servidor.\n{e}")
            sys.exit(1)

        self.master.after(100, self.check_messages)

    def get_color_for_name(self, name):
        if name not in self.name_color_map:
            color = self.colors[len(self.name_color_map) % len(self.colors)]
            self.name_color_map[name] = color
            self.chat_area.tag_configure(name, foreground=color)
        return self.name_color_map[name]

    def append_chat(self, text, tag=None):
        self.chat_area.insert(tk.END, text + "\n", tag)
        self.chat_area.see(tk.END)

    def display_line(self, line):
        if line.endswith("se ha unido al chat.") or line.endswith("ha dejado el chat."):
            self.append_chat(line, "notification")
            return

        if line.startswith("[PRIVADO"):
            self.append_chat(line, "private")
            return

        if ": " in line:
            try:
                nombre, mensaje = line.split(": ", 1)
                self.get_color_for_name(nombre)
                self.chat_area.insert(tk.END, f"{nombre}: ", nombre)
                self.chat_area.insert(tk.END, mensaje + "\n")
                self.chat_area.see(tk.END)
            except ValueError:
                self.append_chat(line)
        else:
            self.append_chat(line)

    def process_data(self, data):
        # Acumula los datos recibidos
        self.estado.buffer += data
        while True:
            # Si estamos recibiendo un archivo, procesamos en modo binario sin separar por líneas
            if self.estado.recibiendo_archivo:
                if len(self.estado.buffer) >= self.estado.bytes_restantes:
                    chunk = self.estado.buffer[:self.estado.bytes_restantes]
                    self.estado.archivo.write(chunk)
                    self.estado.archivo.close()
                    self.append_chat(f"Archivo recibido: {self.estado.last_file}", "notification")
                    self.open_file_button.config(state="normal")
                    self.estado.buffer = self.estado.buffer[self.estado.bytes_restantes:]
                    self.estado.recibiendo_archivo = False
                    self.estado.bytes_restantes = 0
                    # Luego se continúa para procesar lo que reste en el buffer
                    continue
                else:
                    self.estado.archivo.write(self.estado.buffer)
                    self.estado.bytes_restantes -= len(self.estado.buffer)
                    self.estado.buffer = b""
                    break

            # Si no estamos recibiendo archivo, procesamos datos como texto
            if b"\n" not in self.estado.buffer:
                break
            line, self.estado.buffer = self.estado.buffer.split(b"\n", 1)
            try:
                line_decoded = line.decode(errors="replace").strip()
            except Exception:
                line_decoded = ""
            # Si el mensaje es un encabezado de archivo
            if "envía archivo:" in line_decoded:
                try:
                    parts = line_decoded.split(" envía archivo: ")
                    sender = parts[0]
                    file_info = parts[1].split("<SEP>")
                    filename = file_info[0]
                    filesize = int(file_info[1])
                except Exception:
                    self.append_chat("Error al procesar encabezado de archivo.", "notification")
                    continue
                filepath = os.path.join(RECV_DIR, filename)
                try:
                    self.estado.archivo = open(filepath, "wb")
                except Exception as e:
                    self.append_chat(f"Error al abrir archivo: {e}", "notification")
                    continue
                self.append_chat(f"Recibiendo archivo '{filename}' de {sender} ({filesize} bytes)...", "notification")
                self.estado.bytes_restantes = filesize
                self.estado.recibiendo_archivo = True
                self.estado.last_file = filepath
            else:
                self.display_line(line_decoded)

    def check_messages(self):
        try:
            ready_to_read, _, _ = select.select([self.s], [], [], 0)
            if ready_to_read:
                data = self.s.recv(BUFFER_SIZE)
                if data:
                    self.process_data(data)
                else:
                    self.append_chat("Desconexión del servidor", "notification")
                    self.s.close()
                    return
        except Exception as e:
            self.append_chat(f"Error en recepción: {e}", "notification")
            self.s.close()
            return
        self.master.after(100, self.check_messages)

    def send_message(self, event=None):
        message = self.msg_entry.get().strip()
        if message:
            try:
                self.s.send(message.encode())
                if "Tú" not in self.chat_area.tag_names():
                    self.chat_area.tag_configure("Tú", foreground="#000000")
                self.chat_area.insert(tk.END, "Tú: ", "Tú")
                self.chat_area.insert(tk.END, message + "\n")
                self.chat_area.see(tk.END)
            except Exception as e:
                self.append_chat(f"Error al enviar mensaje: {e}", "notification")
        self.msg_entry.delete(0, tk.END)

    def send_file(self):
        filepath = filedialog.askopenfilename(title="Selecciona un archivo")
        if not filepath:
            return
        try:
            filesize = os.path.getsize(filepath)
            filename = os.path.basename(filepath)
            header = FILE_PREFIX + filename.encode() + SEPARATOR + str(filesize).encode() + b"\n"
            self.s.sendall(header)
            with open(filepath, "rb") as f:
                self.append_chat(f"Enviando archivo: {filename} ({filesize} bytes)", "notification")
                while True:
                    chunk = f.read(BUFFER_SIZE)
                    if not chunk:
                        break
                    self.s.sendall(chunk)
            self.append_chat("Archivo enviado", "notification")
        except Exception as e:
            self.append_chat(f"Error al enviar archivo: {e}", "notification")

    def send_private_message(self):
        target = simpledialog.askstring("Mensaje Privado", "Nombre del destinatario:", parent=self.master)
        if not target:
            return
        mensaje = simpledialog.askstring("Mensaje Privado", "Mensaje:", parent=self.master)
        if not mensaje:
            return
        cmd = f"/priv {target} {mensaje}"
        try:
            self.s.send(cmd.encode())
            self.chat_area.insert(tk.END, f"[PRIVADO a {target}]: ", "private")
            self.chat_area.insert(tk.END, mensaje + "\n", "private")
            self.chat_area.see(tk.END)
        except Exception as e:
            self.append_chat(f"Error al enviar mensaje privado: {e}", "notification")

    def open_last_file(self):
        if self.estado.last_file and os.path.exists(self.estado.last_file):
            try:
                if platform.system() == "Windows":
                    os.startfile(self.estado.last_file)
                elif platform.system() == "Darwin":
                    subprocess.call(["open", self.estado.last_file])
                else:
                    subprocess.call(["xdg-open", self.estado.last_file])
            except Exception as e:
                messagebox.showerror("Error", f"No se pudo abrir el archivo.\n{e}")
        else:
            messagebox.showinfo("Información", "No hay archivo disponible para abrir.")

    def on_close(self):
        try:
            self.s.close()
        except:
            pass
        self.master.destroy()

def main():
    if len(sys.argv) != 3:
        print("Uso: python cliente.py <host> <puerto>")
        sys.exit(1)

    host = sys.argv[1]
    port = int(sys.argv[2])
    
    root = tk.Tk()
    client_app = ChatClient(root, host, port)
    root.protocol("WM_DELETE_WINDOW", client_app.on_close)
    root.mainloop()

if __name__ == "__main__":
    main()