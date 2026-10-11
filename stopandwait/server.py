import socket
from sockettcp import SocketTCP

if __name__ == "__main__":
    try:
        address = ("127.0.0.1", 8000)
        
        # SERVER
        server_socketTCP = SocketTCP()
        server_socketTCP.bind(address)
        print(f"Servidor escuchando en {address}...")
        
        connection_socketTCP, new_address = server_socketTCP.accept()
        print(f"\nConexión establecida con {new_address}. Iniciando tests...\n")
        
        # test 1: Recibir exactamente 16 bytes
        buff_size = 16
        full_message = connection_socketTCP.recv(buff_size)
        print("Test 1 received:", full_message.decode(errors='replace'))
        if full_message == "Mensje de len=16".encode(): 
            print("Test 1: Passed\n")
        else: 
            print("Test 1: Failed\n")
        
        # test 2: Recibir 19 bytes (mayor al tamaño máximo de paquete)
        buff_size = 19
        full_message = connection_socketTCP.recv(buff_size)
        print("Test 2 received:", full_message.decode(errors='replace'))
        if full_message == "Mensaje de largo 19".encode(): 
            print("Test 2: Passed\n")
        else: 
            print("Test 2: Failed\n")
        
        # test 3: Recibir un mensaje en dos llamadas separadas (prueba el unprocessed_data)
        buff_size = 14
        message_part_1 = connection_socketTCP.recv(buff_size)
        message_part_2 = connection_socketTCP.recv(buff_size)
        print("Test 3 received:", (message_part_1 + message_part_2).decode(errors='replace'))
        if (message_part_1 + message_part_2) == "Mensaje de largo 19".encode(): 
            print("Test 3: Passed\n")
        else: 
            print("Test 3: Failed\n")

        connection_socketTCP.recv_close()
    except KeyboardInterrupt:
        print("\nCerrando servidor...")