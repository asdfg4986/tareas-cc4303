import socket
import sys
from sockettcp import SocketTCP

"""Cliente de prueba para la implementación de SocketTCP (Stop & Wait sobre UDP).

Este script actúa como el cliente de la comunicación (Host A). Se encarga de:
1. Conectarse al servidor mediante un handshake de 3 vías emulado.
2. Ejecutar 4 pruebas de transferencia con distintas características:
   - Test 1: Mensaje de tamaño exacto igual al MSS (16 bytes).
   - Test 2: Mensaje mayor al MSS (19 bytes) enviado en una sola llamada.
   - Test 3: Mensaje de 19 bytes para verificar recepción dividida en el servidor.
   - Test 4: Transmisión de un archivo arbitrario leído desde standard input (stdin).
3. Cerrar la conexión activamente mediante el protocolo de desconexión definido.

Uso:
    python client.py <ip> <puerto> < archivo.txt
"""

if __name__ == "__main__":
    try:
        # Validación de argumentos por línea de comandos
        if len(sys.argv) != 3:
            print("Uso correcto: python3 cliente.py <ip> <puerto> < archivo.txt")
            sys.exit(1)

        ip = sys.argv[1]
        puerto = int(sys.argv[2])
        # Lectura de los datos binarios del archivo recibido por tubería/redirección (stdin)
        datos_archivo = sys.stdin.buffer.read()

        # Instanciación del socket personalizado
        client_socket = SocketTCP()
        print(f"Conectando a {ip}:{puerto}...")
        # Handshake de tres vías con el servidor
        client_socket.connect((ip, puerto))

        # Test 1: Envío de exactamente 16 bytes (coincide con el tamaño de fragmento)
        print("\nEjecutando Test 1 (16 bytes)...")
        client_socket.send("Mensje de len=16".encode(), mode="go_back_n")

        # Test 2: Envío de 19 bytes (requiere fragmentación en bloques de 16 y 3 bytes)
        print("\nEjecutando Test 2 (19 bytes, un solo envío)...")
        client_socket.send("Mensaje de largo 19".encode(), mode="go_back_n")

        # Test 3: Envío de 19 bytes que el servidor leerá en fragmentos menores (ej. 14 bytes)
        print("\nEjecutando Test 3 (19 bytes, lectura dividida)...")
        client_socket.send("Mensaje de largo 19".encode(), mode="go_back_n")

        # Test 4: Envío de un archivo completo de longitud arbitraria
        print(f"\nEjecutando Test 4 (Archivo de texto de {len(datos_archivo)} bytes)...")
        client_socket.send(datos_archivo, mode="go_back_n")

        # Cierre activo de la conexión una vez culminadas las transferencias
        print("\nTodos los tests enviados. Iniciando cierre...")
        client_socket.close()
    except KeyboardInterrupt:
        print("\nCerrando cliente...")