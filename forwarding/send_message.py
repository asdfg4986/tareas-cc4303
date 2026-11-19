import socket
import sys

from router import create_packet


if __name__ == "__main__":
    try:
        # Validación de argumentos por línea de comandos
        if len(sys.argv) != 7:
            print(
                "Uso correcto: python send_message.py "
                "<ip_final> <puerto_final> <ttl> "
                "<mensaje> <ip_envio> <puerto_envio>"
            )
            sys.exit(1)

        ip_final = sys.argv[1]
        puerto_final = int(sys.argv[2])
        ttl = int(sys.argv[3])
        mensaje = sys.argv[4]
        ip_envio = sys.argv[5]
        puerto_envio = int(sys.argv[6])

        if not 1 <= ttl <= 255:
            print("El TTL debe ser un entero entre 1 y 255.")
            sys.exit(1)

        # Creación del paquete con destino final y mensaje
        paquete = create_packet({
            "ip": ip_final,
            "puerto": puerto_final,
            "ttl": ttl,
            "mensaje": mensaje.encode(),
        })

        # Envío UDP hacia el router inicial
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sender_socket:
            sender_socket.sendto(paquete, (ip_envio, puerto_envio))

        print(f"Paquete enviado a {ip_envio}:{puerto_envio}")
        print(f"Destino final: {ip_final}:{puerto_final}")
        print(f"Mensaje: {mensaje}")

    except ValueError:
        print("Los puertos deben ser números enteros.")

    except KeyboardInterrupt:
        print("\nEnvío cancelado.")