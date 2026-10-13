import socket
import sys
from sockettcp import SocketTCP

if __name__ == "__main__":
    try:
        if len(sys.argv) != 3:
            print("Uso correcto: python3 cliente.py <ip> <puerto> < archivo.txt")
            sys.exit(1)

        ip = sys.argv[1]
        puerto = int(sys.argv[2])
        datos_archivo = sys.stdin.buffer.read()

        client_socket = SocketTCP()
        print(f"Conectando a {ip}:{puerto}...")
        client_socket.connect((ip, puerto))

        print("\nEjecutando Test 1 (16 bytes)...")
        client_socket.send("Mensje de len=16".encode())

        print("\nEjecutando Test 2 (19 bytes, un solo envío)...")
        client_socket.send("Mensaje de largo 19".encode())

        print("\nEjecutando Test 3 (19 bytes, lectura dividida)...")
        client_socket.send("Mensaje de largo 19".encode())

        print(f"\nEjecutando Test 4 (Archivo de texto de {len(datos_archivo)} bytes)...")
        client_socket.send(datos_archivo)

        print("\nTodos los tests enviados. Iniciando cierre...")
        client_socket.close()
    except KeyboardInterrupt:
        print("\nCerrando cliente...")