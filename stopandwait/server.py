import socket
from sockettcp import SocketTCP

if __name__ == "__main__":
    # Configuración
    IP = "127.0.0.1"
    PORT = 8000
    
    # Creación del socket UDP
    print('Creando socket - Servidor')
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind((IP, PORT))
    
    print('... Esperando clientes')

    try:
        while True:
            # Recibimos 23 bytes (7 de header + 16 de datos)
            data, addr = sock.recvfrom(23)

            # Desempaquetamos el segmento recibido
            seq, syn, ack, fin, data = SocketTCP.parse_segment(data)

            # Imprimimos la información del segmento recibido
            print(f"\n[Seq: {seq} | SYN: {syn} | ACK: {ack} | FIN: {fin}] -> ", end='')
            print(data.decode('utf-8', errors='replace'), end='', flush=True)
    except KeyboardInterrupt:
        print("\nCerrando servidor...")