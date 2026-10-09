import socket
from sockettcp import SocketTCP

if __name__ == "__main__":
    # Configuración
    IP = "127.0.0.1"
    PORT = 8000

    # Solicitar la ruta del archivo
    file_path = input("Ingrese la ruta del archivo a enviar: ")

    # Creación del socket UDP
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    actual_seq_num = 0

    try:
        with open(file_path, "rb") as f:
            while True:
                # Leer el archivo en trozos de 16 bytes
                piece = f.read(16)

                if not piece:
                    break # Fin del archivo

                # Empaquetamos el trozo con nuestro header
                segment = SocketTCP.create_segment(
                    seq=actual_seq_num, 
                    syn=False, 
                    ack=False, 
                    fin=False, 
                    data=piece
                )

                sock.sendto(segment, (IP, PORT))
                actual_seq_num += 1

        print(f"\nArchivo '{file_path}' enviado en trozos de 16 bytes.")
    except FileNotFoundError:
        print("Error: No se encontró el archivo. Verifica la ruta.")