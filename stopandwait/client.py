import socket
from sockettcp import SocketTCP

if __name__ == "__main__":
    try:
        address = ("127.0.0.1", 8000)
        # CLIENT
        client_socketTCP = SocketTCP()
        print(f"Conectando al servidor {address}...")
        client_socketTCP.connect(address)
        print("\nConexión exitosa. Enviando tests...\n")

        # test 1: Enviar exactamente 16 bytes
        message = "Mensje de len=16".encode()
        client_socketTCP.send(message)
        print("Test 1 enviado.")

        # test 2: Enviar 19 bytes (requiere fragmentación)
        message = "Mensaje de largo 19".encode()
        client_socketTCP.send(message)
        print("Test 2 enviado.")

        # test 3: Enviar 19 bytes (el servidor lo leerá en dos partes)
        message = "Mensaje de largo 19".encode()
        client_socketTCP.send(message)
        print("Test 3 enviado.")

        client_socketTCP.close()
    except KeyboardInterrupt:
        print("\nCerrando cliente...")