import socket
from sockettcp import SocketTCP

"""Servidor de prueba para la implementación de SocketTCP (Stop & Wait sobre UDP).

Este script actúa como el receptor/servidor de la comunicación (Host B). Se encarga de:
1. Enlazar el socket pasivo a un puerto conocido y esperar conexiones entrantes.
2. Aceptar la conexión del cliente (Handshake de 3 vías), delegando la sesión a un
   socket nuevo e independiente en un puerto efímero.
3. Ejecutar 4 pruebas de recepción que validan las garantías del protocolo TCP:
   - Test 1: Lectura exacta de un fragmento de 16 bytes.
   - Test 2: Lectura de un mensaje mayor a un fragmento (19 bytes), validando el ensamblado interno.
   - Test 3: Lectura dividida con buffers pequeños (14 bytes), comprobando el correcto
             almacenamiento y entrega desde el buffer de datos no procesados (`unprocessed_data`).
   - Test 4: Lectura en dos bloques sucesivos de tamaño n=19 bytes de un archivo enviado por el cliente.
4. Efectuar el cierre pasivo de la conexión (`recv_close`) respondiendo al FIN del cliente.

Uso:
    python server.py
"""

if __name__ == "__main__":
    try:
        puerto = 8000
        server_socket = SocketTCP()
        # Enlace del socket a la dirección IP local y puerto de escucha
        server_socket.bind(("127.0.0.1", puerto))

        print(f"Servidor escuchando en el puerto {puerto}...")
        # Espera pasiva del cliente (SYN) y completitud del handshake de 3 vías.
        # Retorna un nuevo SocketTCP exclusivo para la conexión con el cliente.
        conn, addr = server_socket.accept()
        print(f"Conexión establecida con {addr}. Iniciando pruebas...\n")

        # --- Test 1: Lectura exacta ---
        # El cliente envía 16 bytes; el servidor solicita exactamente 16 bytes.
        full_message = conn.recv(16)
        print("Test 1 recibido:", full_message.decode(errors='replace'))
        if full_message == b"Mensje de len=16":
            print("Test 1: Superado\n")

        # --- Test 2: Lectura mayor al tamaño máximo de paquete ---
        # El cliente envía 19 bytes (fragmentados en red como 16 + 3 bytes).
        # El servidor solicita los 19 bytes completos en una sola llamada recv().
        full_message = conn.recv(19)
        print("Test 2 recibido:", full_message.decode(errors='replace'))
        if full_message == b"Mensaje de largo 19":
            print("Test 2: Superado\n")

        # --- Test 3: Lectura dividida (Prueba de unprocessed_data) ---
        # El cliente envía 19 bytes. El servidor lee con un buffer menor (14 bytes),
        # por lo que los 5 bytes sobrantes deben guardarse en `unprocessed_data`
        # y entregarse en la siguiente llamada a recv(14).
        buff_size = 14
        message_part_1 = conn.recv(buff_size)
        message_part_2 = conn.recv(buff_size)
        print("Test 3 recibido:", (message_part_1 + message_part_2).decode(errors='replace'))
        if (message_part_1 + message_part_2) == b"Mensaje de largo 19":
            print("Test 3: Superado\n")

        # --- Test 4: Prueba específica de 2n bytes (Archivo desde stdin) ---
        # Se reciben dos bloques sucesivos de tamaño n=19 para reconstruir
        # el archivo completo enviado desde el cliente por stdin.
        n = 19
        print(f"Test 4: Esperando archivo (2 llamadas consecutivas de recv({n}))...")
        mitad_1 = conn.recv(n)
        print(f"Test 4 - Bloque 1 ({len(mitad_1)} bytes): {mitad_1.decode(errors='replace')}")

        mitad_2 = conn.recv(n)
        print(f"Test 4 - Bloque 2 ({len(mitad_2)} bytes): {mitad_2.decode(errors='replace')}")

        mensaje_completo = mitad_1 + mitad_2
        print(f"Test 4 completado. Archivo final rearmado:\n{mensaje_completo.decode(errors='replace')}")

        # Espera del proceso de cierre pasivo de la conexión iniciado por el cliente
        print("\nTodas las pruebas recibidas. Esperando cierre de conexión...")
        conn.recv_close()
    except KeyboardInterrupt:
        print("\nCerrando servidor...")