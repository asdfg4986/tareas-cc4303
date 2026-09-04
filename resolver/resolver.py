import socket
from dnslib import DNSRecord
from collections import deque, Counter

class DNSCache:

    def __init__(self):
        self.record = deque(maxlen=20)  # Almacena las ultimas 20 consultas
        self.cache = {} # Diccionario para almacenar las respuestas que se usaran para el cache

    def get(self, qname: str) -> bytes:
        if qname in self.cache:
            return self.cache[qname]
        return b""

    def update(self, qname: str, response: bytes):
        self.record.append(qname)

        counter = Counter(self.record)

        top_3_tuples = counter.most_common(3)
        top_3_qnames = [t[0] for t in top_3_tuples]

        actual_keys = list(self.cache.keys())
        for key in actual_keys:
            if key not in top_3_qnames:
                del self.cache[key]

        if qname in top_3_qnames:
            self.cache[qname] = response

def parse_dns_message(data: bytes) -> dict:
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

    return dns_data

def resolver(query: bytes, ip_address: str = '198.41.0.4', ns_name: str = '.') -> bytes:
    dns_data_query = parse_dns_message(query)
    qname = dns_data_query["qname"]

    print(f"(debug) Consultando '{qname}' a '{ns_name}' con direccion IP '{ip_address}'")

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.sendto(query, (ip_address, 53))
        data, _ = sock.recvfrom(4096)
    finally:
        sock.close()

    dns_data = parse_dns_message(data)

    # Caso base: Si hay respuestas en la sección de respuesta, devolvemos la respuesta completa
    if dns_data["ancount"] > 0:
        for rr in dns_data["answer"]:
            if rr.rtype == 1: # Tipo 1 'A' (IPv4)
                return data

    # Caso recursivo: Si no hay respuestas, pero hay registros de autoridad, intentamos resolver usando los Name Servers
    if dns_data["nscount"] > 0:
        ns_domain = ""
        for authority in dns_data["authority"]:
            if authority.rtype == 2: # Tipo 2 'NS' (Name Server)
                ns_domain = str(authority.rdata)
                break

        if not ns_domain:
            return b"" # Ignorar si no hay registros NS

        for ar_rr in dns_data["additional"]:
            if str(ar_rr.rname) == ns_domain and ar_rr.rtype == 1: # Tipo 1 'A' (IPv4)
                ns_ip = str(ar_rr.rdata)
                return resolver(query, ns_ip, ns_domain)

        query_for_ns = DNSRecord.question(ns_domain)
        ns_response = resolver(query_for_ns.pack(), '198.41.0.4', '.')

        if ns_response:
            ns_dns_data = parse_dns_message(ns_response)
            for rr in ns_dns_data["answer"]:
                if rr.rtype == 1: # Tipo 1 'A' (IPv4)
                    ns_ip = str(rr.rdata)
                    return resolver(query, ns_ip, ns_domain)

    return b"" # Ignorar cualquier otro tipo de respuesta

        
if __name__ == "__main__":
    root_ip = '198.41.0.4'
    root_name = '.'
    buff_size = 4096
    server_socket_address = ('192.168.100.129', 8000)

    print('Creando socket - Servidor')
    # Armamos el socket principal que escuchará al navegador
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    server_socket.bind(server_socket_address)
    cache = DNSCache()

    print('... Esperando clientes')
    try:
        while True:
            data, client_address = server_socket.recvfrom(buff_size)
            print(f"Recibido mensaje de {client_address}")

            dns_data = parse_dns_message(data)
            qname = dns_data["qname"]

            cached_response = cache.get(qname)
            if cached_response:
                print(f"(debug) Respuesta en cache para '{qname}'")

                parsed_response = DNSRecord.parse(cached_response)
                parsed_query = DNSRecord.parse(data)
                parsed_response.header.id = parsed_query.header.id

                print(f"Enviando respuesta a {client_address} usando cache")
                server_socket.sendto(parsed_response.pack(), client_address)

                cache.update(qname, parsed_response.pack())
                
            else:
                response = resolver(data, root_ip)

                if response:
                    print(f"Enviando respuesta a {client_address}")
                    server_socket.sendto(response, client_address)
                    cache.update(qname, response)

    except KeyboardInterrupt:
        print("\nCerrando servidor...")

    finally:
        server_socket.close()

    