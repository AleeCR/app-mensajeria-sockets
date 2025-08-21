import socket
import sys
import select
import errno
import json
import signal

# Constantes
BUFFER_SIZE = 4096

def main():
    if len(sys.argv) != 2:
        print("Uso: python servidor.py <puerto>")
        sys.exit(1)

    host = '0.0.0.0'
    port = int(sys.argv[1])

    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_socket.bind((host, port))
    server_socket.listen(10)
    server_socket.setblocking(False)

    sockets_list = [server_socket]
    peers = {}  # {socket: {"name": nombre, "ip": ip, "port": puerto_servidor}}

    print(f"Servidor de usuarios iniciado en el puerto {port}")

    # Configurar manejador de señales para cierre controlado
    def signal_handler(sig, frame):
        print("\nIniciando cierre controlado del servidor...")
        # Notificar a todos los peers que el servidor se cerrará
        shutdown_msg = json.dumps({
            "type": "server_shutdown",
            "peers": [{"name": p["name"], "ip": p["ip"], "port": p["port"]} for p in peers.values()]
        }).encode()
        
        for peer_sock in peers:
            try:
                peer_sock.send(shutdown_msg)
            except:
                pass
        
        print("Notificación de cierre enviada a todos los peers.")
        server_socket.close()
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    while True:
        try:
            read_sockets, _, _ = select.select(sockets_list, [], [], 1)
            for s in read_sockets:
                if s == server_socket:
                    # Nueva conexión
                    client_sock, addr = server_socket.accept()
                    client_sock.setblocking(False)
                    sockets_list.append(client_sock)
                    print(f"Peer {addr} conectado. Esperando su registro.")
                else:
                    # Datos recibidos de un socket cliente
                    try:
                        data = s.recv(BUFFER_SIZE)
                        if data:
                            if s not in peers:
                                # Registro del peer
                                try:
                                    registro = json.loads(data.decode())
                                    if "name" in registro and "server_port" in registro:
                                        peer_ip = s.getpeername()[0]
                                        peers[s] = {
                                            "name": registro["name"],
                                            "ip": peer_ip,
                                            "port": registro["server_port"]
                                        }
                                        print(f"Peer {s.getpeername()} registrado como '{registro['name']}' en puerto {registro['server_port']}")
                                        
                                        # Enviar lista actualizada de peers a todos
                                        peers_list = [{"name": p["name"], "ip": p["ip"], "port": p["port"]}
                                                    for p in peers.values()]
                                        peers_data = json.dumps(peers_list).encode()
                                        for peer_sock in peers:
                                            try:
                                                peer_sock.send(peers_data)
                                            except:
                                                pass
                                    else:
                                        print(f"Formato de registro inválido de {s.getpeername()}")
                                except json.JSONDecodeError:
                                    print(f"Datos de registro no válidos de {s.getpeername()}")
                            else:
                                # Ping u otro tipo de mensaje
                                if data.decode() == "PING":
                                    # Actualizar y enviar lista de peers a todos
                                    peers_list = [{"name": p["name"], "ip": p["ip"], "port": p["port"]}
                                                for p in peers.values()]
                                    peers_data = json.dumps(peers_list).encode()
                                    for peer_sock in peers:
                                        try:
                                            peer_sock.send(peers_data)
                                        except:
                                            pass
                        else:
                            # Conexión cerrada
                            sockets_list.remove(s)
                            if s in peers:
                                print(f"Peer {peers[s]['name']} desconectado.")
                                del peers[s]
                                
                                # Enviar lista actualizada de peers a todos
                                peers_list = [{"name": p["name"], "ip": p["ip"], "port": p["port"]}
                                            for p in peers.values()]
                                peers_data = json.dumps(peers_list).encode()
                                for peer_sock in peers:
                                    try:
                                        peer_sock.send(peers_data)
                                    except:
                                        pass
                            s.close()
                    except socket.error as e:
                        if e.errno == errno.EWOULDBLOCK or e.errno == 10035:
                            continue
                        else:
                            # Otro error - cerrar socket
                            sockets_list.remove(s)
                            if s in peers:
                                print(f"Error con peer {peers[s]['name']}: {e}")
                                del peers[s]
                                
                                # Enviar lista actualizada de peers a todos
                                peers_list = [{"name": p["name"], "ip": p["ip"], "port": p["port"]}
                                            for p in peers.values()]
                                peers_data = json.dumps(peers_list).encode()
                                for peer_sock in peers:
                                    try:
                                        peer_sock.send(peers_data)
                                    except:
                                        pass
                            s.close()
        except KeyboardInterrupt:
            signal_handler(signal.SIGINT, None)
        except Exception as e:
            print(f"Error crítico: {e}")
            continue

if __name__ == "__main__":
    main()