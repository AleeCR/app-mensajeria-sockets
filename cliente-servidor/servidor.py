import socket
import sys
import select
import errno

# Constantes
TAMANIO_BUFFER = 4096
SEPARADOR = b"<SEP>"
PREFIJO_ARCHIVO = b"ARCHIVO:"


def reenviar_mensaje(socket_origen, mensaje, clientes, nombres_clientes):
    """
    Reenvía un mensaje a todos los clientes conectados, excepto al emisor.
    """
    for cliente in clientes:
        if cliente != socket_origen:
            try:
                cliente.send(mensaje)
            except socket.error as error:
                if error.errno == errno.EWOULDBLOCK or error.errno == 10035:
                    continue
                else:
                    cliente.close()
                    clientes.remove(cliente)
                    del nombres_clientes[cliente]


def iniciar_servidor():
    if len(sys.argv) != 2:
        print("Uso: python servidor.py <puerto>")
        sys.exit(1)

    host = '0.0.0.0'
    puerto = int(sys.argv[1])

    socket_servidor = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    socket_servidor.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    socket_servidor.bind((host, puerto))
    socket_servidor.listen(10)
    socket_servidor.setblocking(False)

    lista_sockets = [socket_servidor]
    clientes = []
    nombres_clientes = {}  # socket -> nombre
    nombre_a_socket = {}   # nombre -> socket

    print(f"Servidor iniciado en el puerto {puerto}")

    while True:
        try:
            sockets_lectura, _, _ = select.select(lista_sockets, [], [], 1)
            for sock in sockets_lectura:
                if sock == socket_servidor:
                    cliente_socket, direccion = socket_servidor.accept()
                    cliente_socket.setblocking(False)
                    lista_sockets.append(cliente_socket)
                    clientes.append(cliente_socket)
                    print(f"Cliente {direccion} conectado. Esperando su nombre (enviado por el cliente).")

                else:
                    try:
                        datos = sock.recv(TAMANIO_BUFFER)
                        if datos:
                            if sock not in nombres_clientes:
                                # El primer mensaje recibido es el nombre del cliente
                                nombre = datos.decode().strip()
                                if not nombre:
                                    nombre = "Desconocido"

                                if nombre in nombre_a_socket:
                                    sock.send(b"Este nombre ya esta en uso. Por favor, elige otro.\n")
                                    sock.close()
                                    lista_sockets.remove(sock)
                                    clientes.remove(sock)
                                    continue

                                nombres_clientes[sock] = nombre
                                nombre_a_socket[nombre] = sock
                                print(f"Cliente {sock.getpeername()} se ha identificado como '{nombre}'")

                                mensaje_union = f"{nombre} se ha unido al chat.\n".encode()
                                reenviar_mensaje(sock, mensaje_union, clientes, nombres_clientes)

                            else:
                                if datos.startswith(PREFIJO_ARCHIVO):
                                    # Procesar encabezado de archivo
                                    fin_encabezado = datos.find(b"\n")
                                    if fin_encabezado != -1:
                                        encabezado = datos[:fin_encabezado].decode()
                                        partes = encabezado.split("<SEP>")
                                        if len(partes) == 2 and partes[0].startswith("ARCHIVO:"):

                                            nombre_archivo = partes[8:]
                                            tamanio_archivo = int(partes)
                                            remitente = nombres_clientes[sock]

                                            print(f"Recibiendo archivo: {nombre_archivo} ({tamanio_archivo} bytes) de {remitente}")

                                            encabezado_prefijo = f"{remitente} envía archivo: {nombre_archivo}<SEP>{tamanio_archivo}\n".encode()
                                            reenviar_mensaje(sock, encabezado_prefijo, clientes, nombres_clientes)

                                            if len(datos) > fin_encabezado + 1:
                                                reenviar_mensaje(sock, datos[fin_encabezado + 1:], clientes, nombres_clientes)
                                                bytes_recibidos = len(datos) - fin_encabezado - 1
                                            else:
                                                print("Encabezado de archivo inválido")
                                                continue
                                        else:
                                            continue

                                        while bytes_recibidos < tamanio_archivo:
                                            try:
                                                bloque = sock.recv(TAMANIO_BUFFER)
                                                if not bloque:
                                                    break
                                                reenviar_mensaje(sock, bloque, clientes, nombres_clientes)
                                                print(f"Reenviando bloque de archivo: {len(bloque)} bytes")
                                                bytes_recibidos += len(bloque)
                                            except socket.error as error:
                                                if error.errno == errno.EWOULDBLOCK or error.errno == 10035:
                                                    continue
                                                else:
                                                    raise
                                        print(f"Archivo {nombre_archivo} reenviado completamente")

                                else:
                                    texto = datos.decode().strip()
                                    remitente = nombres_clientes[sock]

                                    if texto.startswith("/priv "):
                                        partes_comando = texto.split(" ", 2)
                                        if len(partes_comando) < 3:
                                            sock.send(b"Uso: /priv <nombre> <mensaje>\n")
                                            continue

                                        destinatario_nombre = partes_comando[1]
                                        mensaje_privado = partes_comando

                                        if destinatario_nombre in nombre_a_socket:
                                            destinatario_socket = nombre_a_socket[destinatario_nombre]
                                            mensaje_formateado_privado = f"[PRIVADO] {remitente}: {mensaje_privado}\n".encode()
                                            destinatario_socket.send(mensaje_formateado_privado)
                                            sock.send(f"[PRIVADO a {destinatario_nombre}]: {mensaje_privado}\n".encode())
                                        else:
                                            sock.send(f"Usuario {destinatario_nombre} no encontrado.\n".encode())
                                    else:
                                        print(f"Recibido de {remitente}: {texto}")
                                        mensaje_formateado_publico = f"{remitente}: {texto}\n".encode()
                                        reenviar_mensaje(sock, mensaje_formateado_publico, clientes, nombres_clientes)
                                        print(f"Mensaje reenviado: {mensaje_formateado_publico.decode().strip()}")

                        else:
                            lista_sockets.remove(sock)
                            clientes.remove(sock)
                            remitente_nombre = nombres_clientes.get(sock, "Desconocido")
                            if sock in nombres_clientes:
                                del nombres_clientes[sock]
                            if remitente_nombre in nombre_a_socket:
                                del nombre_a_socket[remitente_nombre]
                            sock.close()
                            print(f"Cliente {remitente_nombre} desconectado.")
                            mensaje_salida = f"{remitente_nombre} ha dejado el chat.\n".encode()
                            reenviar_mensaje(sock, mensaje_salida, clientes, nombres_clientes)

                    except socket.error as error:
                        if error.errno == errno.EWOULDBLOCK or error.errno == 10035:
                            continue
                        else:
                            raise

        except KeyboardInterrupt:
            print("\nCerrando servidor...")
            socket_servidor.close()
            sys.exit(0)

        except Exception as error_critico:
            print(f"Error crítico: {error_critico}")
            continue


if __name__ == "__main__":
    iniciar_servidor()
