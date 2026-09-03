import socket
from dnslib import DNSRecord

def parse_dns_message(data: bytes):
    parsed_data = DNSRecord.parse(data)

    dns_data = {
        "qname": str(parsed_data.q.qname),
        "ancount": parsed_data.header.a,
        "nscount": parsed_data.header.auth,
        "arcount": parsed_data.header.ar,
        "answer": parsed_data.rr,
        "authority": parsed_data.auth,
        "additional": parsed_data.ar
    }

    return dns_data, parsed_data

if __name__ == "__main__":
    root_ip = '198.41.0.4'
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

            dns_data, parsed_data = parse_dns_message(data)

            print(f"\nConsulta recibida de {client_address}")
            print(f"Dominio consultado (Qname): {dns_data['qname']}")
            print(f"ANCOUNT (Respuestas): {dns_data['ancount']}")
            print(f"NSCOUNT (Autoridades): {dns_data['nscount']}")
            print(f"ARCOUNT (Adicionales): {dns_data['arcount']}")
            
    except KeyboardInterrupt:
        print("\nCerrando servidor...")

    finally:
        server_socket.close()

    