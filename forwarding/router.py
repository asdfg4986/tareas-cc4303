import socket
import sys

def parse_packet(IP_packet: bytes):
    if len(IP_packet) < 7:
        raise ValueError("El paquete debe contener al menos 7 bytes de header.")

    ip = ".".join(str(byte) for byte in IP_packet[:4])
    puerto = int.from_bytes(IP_packet[4:6], byteorder="big")
    ttl = IP_packet[6]
    mensaje = IP_packet[7:]

    return {
        "ip": ip,
        "puerto": puerto,
        "ttl": ttl,
        "mensaje": mensaje,
    }


def create_packet(parsed_IP_packet):
    ip_bytes = bytes(
        int(parte) for parte in parsed_IP_packet["ip"].split(".")
    )

    if len(ip_bytes) != 4:
        raise ValueError("La dirección IPv4 debe tener 4 componentes.")

    puerto_bytes = parsed_IP_packet["puerto"].to_bytes(
        2,
        byteorder="big"
    )

    ttl_bytes = parsed_IP_packet["ttl"].to_bytes(
        1,
        byteorder="big"
    )

    return (
        ip_bytes
        + puerto_bytes
        + ttl_bytes
        + parsed_IP_packet["mensaje"]
    )

next_route_index = {}

def check_routes(routes_file_name: str, destination_address: tuple[str, int]):
    destination_ip, destination_port = destination_address

    area = None
    possible_routes = []

    with open(routes_file_name, "r") as routes_file:
        for line in routes_file:
            line = line.strip()

            if not line or line.startswith("#"):
                continue

            (
                destination_network,
                initial_port,
                final_port,
                next_hop_ip,
                next_hop_port,
            ) = line.split()

            network_ip = destination_network.split("/")[0]
            initial_port = int(initial_port)
            final_port = int(final_port)

            if (
                destination_ip == network_ip
                and initial_port <= destination_port <= final_port
            ):
                current_area = (
                    destination_network,
                    initial_port,
                    final_port,
                )

                # Conserva la primera área que coincide, como antes.
                if area is None:
                    area = current_area

                # Junta todas las rutas posibles de esa misma área.
                if current_area == area:
                    possible_routes.append(
                        (next_hop_ip, int(next_hop_port))
                    )

    if area is None:
        return None

    route_key = (routes_file_name, area)

    # La primera vez selecciona la primera ruta de la tabla.
    route_index = next_route_index.get(route_key, 0)

    selected_route = possible_routes[route_index]

    # Guarda cuál ruta debe utilizar la próxima vez.
    next_route_index[route_key] = (
        route_index + 1
    ) % len(possible_routes)

    return selected_route

if __name__ == "__main__":
    try:
        # Validación de argumentos por línea de comandos
        if len(sys.argv) != 4:
            print("Uso correcto: python3 router.py <ip> <puerto> <archivo_rutas>")
            sys.exit(1)

        router_ip = sys.argv[1]
        archivo_rutas = sys.argv[3]

        try:
            router_puerto = int(sys.argv[2])

            if not 1 <= router_puerto <= 65535:
                raise ValueError("Puerto fuera de rango")
        except ValueError:
            print("El puerto debe ser un entero entre 1 y 65535.")
            sys.exit(1)

        # Creación del socket UDP
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as router_socket:
            router_socket.bind((router_ip, router_puerto))

            print(f"Router escuchando en {router_ip}:{router_puerto}")
            print(f"Archivo de rutas: {archivo_rutas}")

            # Recepción bloqueante de un paquete
            while True:
                paquete, origen = router_socket.recvfrom(65535)

                paquete_parseado = parse_packet(paquete)

                if paquete_parseado["ttl"] == 0:
                    print(f"Se recibió paquete {paquete} con TTL 0")
                    continue

                destination_address = (
                    paquete_parseado["ip"],
                    paquete_parseado["puerto"],
                )

                # El paquete llegó a su router final
                if destination_address == (router_ip, router_puerto):
                    print(
                        "Mensaje recibido:",
                        paquete_parseado["mensaje"].decode()
                    )

                # El paquete debe ser reenviado
                else:
                    next_hop = check_routes(
                        archivo_rutas,
                        destination_address
                    )

                    if next_hop is None:
                        print(
                            f"No hay rutas hacia {destination_address} "
                            f"para paquete {paquete}"
                        )
                    else:
                        paquete_parseado["ttl"] -= 1
                        paquete = create_packet(paquete_parseado)

                        router_socket.sendto(paquete, next_hop)

                        print(
                            f"redirigiendo paquete {paquete} "
                            f"con destino final {destination_address} "
                            f"desde {(router_ip, router_puerto)} "
                            f"hacia {next_hop}"
                        )

    except KeyboardInterrupt:
        print("\nCerrando router...")