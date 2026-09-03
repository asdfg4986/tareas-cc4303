import socket

if __name__ == "__main__":
    buff_size = 4096
    server_socket_address = ('192.168.100.129', 8000)

    print('Creando socket - Servidor')
    # Armamos el socket principal que escuchará al navegador
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    server_socket.bind(server_socket_address)

    print('... Esperando clientes')
    try:
        while True:
            data, client_address = server_socket.recvfrom(buff_size)

            print(f"\nConsulta recibida de {client_address}: \n{data}")
            
    except KeyboardInterrupt:
        print("\nCerrando servidor...")

    finally:
        server_socket.close()

    