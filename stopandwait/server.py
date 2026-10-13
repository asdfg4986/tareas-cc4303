import socket
from sockettcp import SocketTCP

if __name__ == "__main__":
    try:
        puerto = 8000
        server_socket = SocketTCP()
        server_socket.bind(("127.0.0.1", puerto))

        print(f"Servidor escuchando en el puerto {puerto}...")
        conn, addr = server_socket.accept()
        print(f"Conexión establecida con {addr}. Iniciando pruebas...\n")

        # --- Test 1: Lectura exacta ---
        full_message = conn.recv(16)
        print("Test 1 recibido:", full_message.decode(errors='replace'))
        if full_message == b"Mensje de len=16":
            print("Test 1: Superado\n")

        # --- Test 2: Lectura mayor al tamaño máximo de paquete ---
        full_message = conn.recv(19)
        print("Test 2 recibido:", full_message.decode(errors='replace'))
        if full_message == b"Mensaje de largo 19":
            print("Test 2: Superado\n")

        # --- Test 3: Lectura dividida (Prueba de unprocessed_data) ---
        buff_size = 14
        message_part_1 = conn.recv(buff_size)
        message_part_2 = conn.recv(buff_size)
        print("Test 3 recibido:", (message_part_1 + message_part_2).decode(errors='replace'))
        if (message_part_1 + message_part_2) == b"Mensaje de largo 19":
            print("Test 3: Superado\n")

        # --- Test 4: Prueba específica de 2n bytes (Archivo desde stdin) ---
        n = 19
        print(f"Test 4: Esperando archivo (2 llamadas consecutivas de recv({n}))...")
        mitad_1 = conn.recv(n)
        print(f"Test 4 - Bloque 1 ({len(mitad_1)} bytes): {mitad_1.decode(errors='replace')}")

        mitad_2 = conn.recv(n)
        print(f"Test 4 - Bloque 2 ({len(mitad_2)} bytes): {mitad_2.decode(errors='replace')}")

        mensaje_completo = mitad_1 + mitad_2
        print(f"Test 4 completado. Archivo final rearmado:\n{mensaje_completo.decode(errors='replace')}")

        print("\nTodas las pruebas recibidas. Esperando cierre de conexión...")
        conn.recv_close()
    except KeyboardInterrupt:
        print("\nCerrando servidor...")