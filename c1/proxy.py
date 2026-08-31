import socket
import json
import sys

def parse_HTTP_message(http_message: bytes) -> dict:
    message_parts = http_message.split(b'\r\n\r\n', 1)

    head = message_parts[0].decode()
    headers = head.split('\r\n')

    method, path, version = headers[0].split(' ')

    headers_dict = {}

    for header in headers[1:]:
        key, value = header.split(': ', 1)
        headers_dict[key] = value

    message_dict = {
        'method': method,
        'path': path,
        'version': version,
        'headers': headers_dict,
        'body': message_parts[1]
    }

    return message_dict

def create_HTTP_message(message_dict: dict) -> bytes:
    method = message_dict['method']
    path = message_dict['path']
    version = message_dict['version']
    headers = message_dict['headers']
    body = message_dict['body']

    request_line = f"{method} {path} {version}\r\n"
    headers_str = ''.join(f"{key}: {value}\r\n" for key, value in headers.items())
    http_message = f"{request_line}{headers_str}\r\n".encode() + body

    return http_message

if __name__ == "__main__":
    # verificamos que se haya proporcionado un archivo de configuración como argumento
    if len(sys.argv) < 2:
        print("Error: No se proporcionó el archivo de configuración.")
        sys.exit(1)

    # cargamos la configuración desde el archivo JSON
    with open(sys.argv[1], 'r') as f:
        config = json.load(f)

    my_name = config["nombre"]

    # definimos el tamaño del buffer de recepción y la dirección del socket del servidor
    buff_size = 4096
    server_socket_address = ('192.168.100.129', 8000)

    print('Creando socket - Servidor')
    # armamos el socket
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.bind(server_socket_address)
    server_socket.listen(3)

    # nos quedamos esperando a que llegue una petición de conexión
    print('... Esperando clientes')
    while True:
        # cuando llega una petición de conexión la aceptamos
        # y se crea un nuevo socket que se comunicará con el cliente
        new_socket, new_socket_address = server_socket.accept()

        # recibimos el mensaje
        recv_message = new_socket.recv(buff_size)

        print(f'Request crudo:\n{recv_message}')

        html_body = b"<html><body><h1>Hola desde mi proxy en Debian!</h1></body></html>"

        response_dict = {
            'method': 'HTTP/1.1',
            'path': '200',
            'version': 'OK',
            'headers': {
                'Content-Type': 'text/html; charset=UTF-8',
                'Content-Length': str(len(html_body)),
                'Connection': 'close',
                'X-ElQuePregunta': my_name
            },
            'body': html_body
        }

        if recv_message:
            # parseamos el mensaje
            parsed_request = parse_HTTP_message(recv_message)

            host_header = parsed_request['headers']['Host']

            # si el header Host contiene un número de puerto, lo extraemos
            if ':' in host_header:
                destiny_host, destiny_port = host_header.split(':')
                destiny_port = int(destiny_port)
            # si no, asumimos que el puerto es 80
            else:
                destiny_host = host_header
                destiny_port = 80

            # creamos un socket para conectarnos al servidor destino
            destiny_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

            # intentamos conectarnos al servidor destino
            try:
                destiny_socket.connect((destiny_host, destiny_port))

                # enviamos la petición al servidor destino
                destiny_socket.send(recv_message)

                # recibimos la respuesta del servidor destino
                server_response = destiny_socket.recv(buff_size)
                if server_response:
                    print(f'Response crudo:\n{server_response}')
                    new_socket.send(server_response)

                destiny_socket.close()

            except Exception as e:
                print(f"Error al conectar con {destiny_host}:{destiny_port}: {e}")
                new_socket.close()
                continue

        # cerramos la conexión
        new_socket.close()
        print(f"conexión con {new_socket_address} ha sido cerrada\n")

        # seguimos esperando por si llegan otras conexiones