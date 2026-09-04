import socket
from dnslib import DNSRecord
from collections import deque, Counter

class DNSCache:
    """
    Implementa un sistema de caché personalizado para el servidor DNS.
    Mantiene un historial de las últimas 20 consultas y almacena físicamente las 
    respuestas de los 3 dominios más frecuentes dentro de ese historial.
    """

    def __init__(self):
        self.record = deque(maxlen=20)  # Almacena las ultimas 20 consultas
        self.cache = {} # Diccionario para almacenar las respuestas que se usaran para el cache

    def get(self, qname: str) -> bytes:
        """
        Busca un dominio en la memoria caché.
        
        :param qname: El nombre de dominio consultado (ej. 'www.uchile.cl.')
        :return: Los bytes de la respuesta guardada, o b"" si no está en caché.
        """

        if qname in self.cache:
            return self.cache[qname]
        return b""

    def update(self, qname: str, response: bytes):
        """
        Actualiza el historial de consultas y recalcula el Top 3 de dominios.
        Si el dominio entra al Top 3, guarda su respuesta en memoria.
        
        :param qname: El nombre de dominio consultado.
        :param response: Los bytes de la respuesta DNS a guardar.
        """

        self.record.append(qname)

        # Contamos la frecuencia de cada dominio en las últimas 20 consultas
        counter = Counter(self.record)

        # Obtenemos los 3 dominios con mayor frecuencia
        top_3_tuples = counter.most_common(3)
        top_3_qnames = [t[0] for t in top_3_tuples]

        # Limpiamos el caché físico: eliminamos lo que ya no esté en el Top 3
        actual_keys = list(self.cache.keys())
        for key in actual_keys:
            if key not in top_3_qnames:
                del self.cache[key]

        # Si el dominio actual pertenece al Top 3, lo guardamos/actualizamos
        if qname in top_3_qnames:
            self.cache[qname] = response

def parse_dns_message(data: bytes) -> dict:
    """
    Toma un mensaje DNS en crudo (bytes) y lo convierte en una estructura
    de diccionario manejable utilizando la librería dnslib.
    
    :param data: Bytes del paquete DNS recibido.
    :return: Diccionario con el dominio, contadores y listas de Resource Records.
    """

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
    """
    Motor principal de resolución DNS. Funciona de manera iterativa (preguntando
    servidor por servidor) y recursiva (para resolver IPs de NameServers delegados).
    
    :param query: El paquete DNS original de la consulta en bytes.
    :param ip_address: La IP del NameServer al que se le preguntará en esta iteración.
    :param ns_name: El nombre del NameServer (usado exclusivamente para el modo debug).
    :return: Los bytes de la respuesta DNS final, o b"" si falla.
    """

    dns_data_query = parse_dns_message(query)
    qname = dns_data_query["qname"]

    print(f"(debug) Consultando '{qname}' a '{ns_name}' con direccion IP '{ip_address}'")

    # Creamos un socket cliente para comunicarnos con el NameServer externo
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

    # Caso iterativo/recursivo: Si no hay respuestas, pero hay registros de autoridad, intentamos resolver usando los Name Servers
    if dns_data["nscount"] > 0:
        ns_domain = ""
        for authority in dns_data["authority"]:
            if authority.rtype == 2: # Tipo 2 'NS' (Name Server)
                ns_domain = str(authority.rdata)
                break

        if not ns_domain:
            return b"" # Ignorar si no hay registros NS

        # Iteración directa: Buscamos la IP en la sección Additional
        for ar_rr in dns_data["additional"]:
            if str(ar_rr.rname) == ns_domain and ar_rr.rtype == 1: # Tipo 1 'A' (IPv4)
                ns_ip = str(ar_rr.rdata)
                return resolver(query, ns_ip, ns_domain)

        # Recursión: No nos entregaron la IP del NS.
        # Pausamos la búsqueda actual y creamos una nueva consulta buscando la IP del NS.
        query_for_ns = DNSRecord.question(ns_domain)
        # Iniciamos la búsqueda del NameServer partiendo desde el servidor raíz
        ns_response = resolver(query_for_ns.pack(), '198.41.0.4', '.')

        if ns_response:
            ns_dns_data = parse_dns_message(ns_response)
            for rr in ns_dns_data["answer"]:
                if rr.rtype == 1: # Tipo 1 'A' (IPv4)
                    ns_ip = str(rr.rdata)
                    # Retomamos la consulta original usando la IP recién descubierta
                    return resolver(query, ns_ip, ns_domain)

    # Ignorar cualquier otro tipo de respuesta
    return b"" 

        
if __name__ == "__main__":
    # Configuración de variables globales del servidor local
    root_ip = '198.41.0.4'
    root_name = '.'
    buff_size = 4096
    server_socket_address = ('192.168.100.129', 8000)

    print('Creando socket - Servidor')
    # Armamos el socket principal que escuchará peticiones de clientes
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    server_socket.bind(server_socket_address)
    cache = DNSCache()

    print('... Esperando clientes')
    try:
        while True:
            # Bloquea la ejecución hasta recibir un mensaje
            data, client_address = server_socket.recvfrom(buff_size)
            print(f"Recibido mensaje de {client_address}")

            dns_data = parse_dns_message(data)
            qname = dns_data["qname"]

            # Verificamos si la respuesta ya existe en nuestra caché
            cached_response = cache.get(qname)

            if cached_response:
                print(f"(debug) Respuesta en cache para '{qname}'")

                # Actualizamos el Transaction ID (Header ID) de la respuesta guardada
                # para que coincida con la consulta actual y el cliente no la rechace
                parsed_response = DNSRecord.parse(cached_response)
                parsed_query = DNSRecord.parse(data)
                parsed_response.header.id = parsed_query.header.id

                print(f"Enviando respuesta a {client_address} usando cache")
                server_socket.sendto(parsed_response.pack(), client_address)

                # Actualizamos el registro histórico
                cache.update(qname, parsed_response.pack())

            else:
                # Si no está en caché, iniciamos el proceso de resolución por internet
                response = resolver(data, root_ip)

                if response:
                    print(f"Enviando respuesta a {client_address}")
                    server_socket.sendto(response, client_address)
                    # Guardamos la nueva respuesta en la caché
                    cache.update(qname, response)

    except KeyboardInterrupt:
        print("\nCerrando servidor...")

    finally:
        # Liberamos el puerto a nivel de sistema operativo
        server_socket.close()

    