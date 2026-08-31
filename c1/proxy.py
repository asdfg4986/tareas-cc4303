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

            requested_path = parsed_request['path']
            full_url = destiny_host + requested_path

            if requested_path.endswith('/403.jpg'):
                try:
                    with open("403.jpg", "rb") as f:
                        image_data = f.read()
                    img_dict = {
                        'method': 'HTTP/1.1',
                        'path': '200',
                        'version': 'OK',
                        'headers': {
                            'Content-Type': 'image/jpeg',
                            'Content-Length': str(len(image_data)),
                            'Connection': 'close'
                        },
                        'body': image_data
                    }

                    new_socket.send(create_HTTP_message(img_dict))
                except FileNotFoundError:
                    error_dict = {
                        'method': 'HTTP/1.1',
                        'path': '404',
                        'version': 'Not Found',
                        'headers': {'Connection': 'close'},
                        'body': b''
                    }
                    new_socket.send(create_HTTP_message(error_dict))

                new_socket.close()
                continue

            is_blocked = False
            # verificamos si la URL está en la lista de bloqueadas
            for blocked_url in config["blocked"]:
                if blocked_url in full_url:
                    is_blocked = True
                    break

            if is_blocked:
                print(f"URL bloqueada: {full_url}")
                html_blocked = (
                    "<html><head><title>Bloqueado</title></head>"
                    "<body><h1>Acceso Denegado (403)</h1>"
                    "<img src='/403.jpg' alt='Gato bloqueador'>"
                    "</body></html>"
                ).encode()

                blocked_dict = {
                    'method': 'HTTP/1.1',
                    'path': '403',
                    'version': 'Forbidden',
                    'headers': {
                        'Content-Type': 'text/html; charset=UTF-8',
                        'Content-Length': str(len(html_blocked)),
                        'Connection': 'close'
                    },
                    'body': html_blocked
                }

                new_socket.send(create_HTTP_message(blocked_dict))
                new_socket.close()
                continue

            # creamos un socket para conectarnos al servidor destino
            destiny_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

            parsed_request['headers']['X-ElQuePregunta'] = config["user"]

            modified_request = create_HTTP_message(parsed_request)

            # intentamos conectarnos al servidor destino
            try:
                destiny_socket.connect((destiny_host, destiny_port))
                
                # enviamos la petición al servidor destino
                destiny_socket.send(modified_request)

                # recibimos la respuesta del servidor destino
                server_response = destiny_socket.recv(buff_size)

                if server_response:
                    print(f'Response crudo:\n{server_response}')
                    parsed_response = parse_HTTP_message(server_response)

                    body_response = parsed_response['body']

                    # verificamos si la respuesta contiene alguna palabra prohibida
                    for forbidden_word in config["forbidden_words"]:
                        for word, replacement in forbidden_word.items():
                            body_response = body_response.replace(word.encode(), replacement.encode())

                    parsed_response['body'] = body_response

                    if 'Content-Length' in parsed_response['headers']:
                        parsed_response['headers']['Content-Length'] = str(len(body_response))

                    modified_response = create_HTTP_message(parsed_response)

                    new_socket.send(modified_response)

                destiny_socket.close()

            except Exception as e:
                print(f"Error al conectar con {destiny_host}:{destiny_port}: {e}")

        # cerramos la conexión
        new_socket.close()
        print(f"conexión con {new_socket_address} ha sido cerrada\n")

        # seguimos esperando por si llegan otras conexiones