import socket
import json
import sys

def parse_HTTP_message(http_message: bytes) -> dict:
    """
    Toma un mensaje HTTP crudo en bytes y lo convierte en un diccionario estructurado.
    Separa la línea de petición (Request Line), las cabeceras (Headers) y el cuerpo (Body).
    """
    # Separamos el mensaje en dos partes: Headers y Body usando el doble salto de línea
    message_parts = http_message.split(b'\r\n\r\n', 1)

    # Decodificamos solo la parte de los headers a string para procesarlos
    head = message_parts[0].decode()
    headers = head.split('\r\n')

    # Extraemos el Método (ej: GET), la Ruta (ej: /index.html) y la Versión (ej: HTTP/1.1)
    method, path, version = headers[0].split(' ')

    # Parseamos el resto de las cabeceras a un diccionario clave-valor
    headers_dict = {}
    for header in headers[1:]:
        key, value = header.split(': ', 1)
        headers_dict[key] = value

    # Empaquetamos todo
    message_dict = {
        'method': method,
        'path': path,
        'version': version,
        'headers': headers_dict,
        'body': message_parts[1]
    }

    return message_dict

def create_HTTP_message(message_dict: dict) -> bytes:
    """
    Realiza la operación inversa a parse_HTTP_message.
    Toma un diccionario con los componentes HTTP y lo ensambla en un mensaje de bytes
    listo para ser enviado por el socket.
    """
    method = message_dict['method']
    path = message_dict['path']
    version = message_dict['version']
    headers = message_dict['headers']
    body = message_dict['body']

    # Reconstruimos la primera línea (Request/Response Line)
    request_line = f"{method} {path} {version}\r\n"
    
    # Reconstruimos las cabeceras, asegurando el salto de línea \r\n después de cada una
    headers_str = ''.join(f"{key}: {value}\r\n" for key, value in headers.items())
    
    # Concatenamos todo. Codificamos el texto a bytes y le sumamos el body (que ya está en bytes)
    http_message = f"{request_line}{headers_str}\r\n".encode() + body

    return http_message

def receive_full_message(sock: socket.socket, buff_size: int) -> bytes:
    """
    Lee datos del socket de forma segura, iterando hasta asegurarse de recibir
    el mensaje HTTP completo, sin importar qué tan pequeño sea el buffer.
    """
    acc = b''
    
    # FASE 1: Leer hasta encontrar el final de las cabeceras (\r\n\r\n)
    while b'\r\n\r\n' not in acc:
        part = sock.recv(buff_size)
        if not part:
            return b'' # El cliente cerró la conexión
        acc += part

    # Separamos temporalmente las cabeceras del cuerpo parcial recibido
    head, body = acc.split(b'\r\n\r\n', 1)
    head_str = head.decode()
    body_length = 0
    
    # Buscamos el header Content-Length para saber matemáticamente cuánto debe pesar el cuerpo
    for line in head_str.split('\r\n'):
        if line.lower().startswith('content-length:'):
            body_length = int(line.split(':', 1)[1].strip())
            break

    # FASE 2: Si el cuerpo que tenemos es menor al prometido, seguimos leyendo del socket
    while len(body) < body_length:
        part = sock.recv(buff_size)
        if not part:
            break
        body += part

    # Reensamblamos el mensaje total y lo retornamos en bytes
    return head + b'\r\n\r\n' + body

if __name__ == "__main__":
    # Verificamos que se haya proporcionado el archivo JSON como argumento por consola
    if len(sys.argv) < 2:
        print("Error: No se proporcionó el archivo de configuración.")
        sys.exit(1)

    # Cargamos la configuración (nombre de usuario, páginas bloqueadas y palabras censuradas)
    with open(sys.argv[1], 'r') as f:
        config = json.load(f)

    # Definimos un buffer intencionalmente pequeño para probar la robustez de receive_full_message
    buff_size = 50
    server_socket_address = ('192.168.100.129', 8000)

    print('Creando socket - Servidor')
    # Armamos el socket principal que escuchará al navegador
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.bind(server_socket_address)
    server_socket.listen(3)

    print('... Esperando clientes')
    while True:
        # Aceptamos la conexión del cliente (Navegador o curl)
        new_socket, new_socket_address = server_socket.accept()

        # Usamos nuestra función robusta para garantizar la lectura completa
        recv_message = receive_full_message(new_socket, buff_size)

        if recv_message:
            # Parseamos la petición del cliente para entender qué quiere
            parsed_request = parse_HTTP_message(recv_message)
            host_header = parsed_request['headers']['Host']

            # Resolvemos la IP/Dominio y el Puerto de destino basándonos en el header 'Host'
            if ':' in host_header:
                destiny_host, destiny_port = host_header.split(':')
                destiny_port = int(destiny_port)
            else:
                destiny_host = host_header
                destiny_port = 80

            requested_path = parsed_request['path']
            full_url = destiny_host + requested_path

            # -- BLOQUE 1: Intercepción de la Imagen --
            # Si el navegador pide específicamente la imagen del bloqueo, la servimos desde local
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
                            'Connection': 'close' # Evitamos que el navegador se quede esperando
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
                continue # Terminamos con este cliente y volvemos al inicio del while

            # -- BLOQUE 2: Verificación de Sitios Prohibidos --
            is_blocked = False
            for blocked_url in config["blocked"]:
                if blocked_url in full_url:
                    is_blocked = True
                    break

            # Si está bloqueado, inyectamos el HTML con el código 403 y cerramos
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

            # -- BLOQUE 3: Proxy Transparente y Modificación de Paquetes --
            destiny_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

            # Inyectamos nuestro header personalizado leyendo el nombre desde el JSON
            parsed_request['headers']['X-ElQuePregunta'] = config["user"]
            modified_request = create_HTTP_message(parsed_request)

            try:
                # Conectamos con el servidor en internet
                destiny_socket.connect((destiny_host, destiny_port))
                
                # Enviamos la petición modificada
                destiny_socket.send(modified_request)

                # Recibimos la respuesta completa del servidor real
                server_response = receive_full_message(destiny_socket, buff_size)

                if server_response:
                    
                    # Parseamos la respuesta para poder modificar su HTML
                    parsed_response = parse_HTTP_message(server_response)
                    body_response = parsed_response['body']

                    # Buscamos y reemplazamos cada palabra prohibida según el JSON
                    for forbidden_word in config["forbidden_words"]:
                        for word, replacement in forbidden_word.items():
                            body_response = body_response.replace(word.encode(), replacement.encode())

                    # Guardamos el cuerpo modificado
                    parsed_response['body'] = body_response

                    # Recalculamos el Content-Length ya que el tamaño del HTML cambió por el reemplazo
                    if 'Content-Length' in parsed_response['headers']:
                        parsed_response['headers']['Content-Length'] = str(len(body_response))

                    # Reconstruimos la respuesta final modificada y se la enviamos al navegador del cliente
                    modified_response = create_HTTP_message(parsed_response)
                    new_socket.send(modified_response)

                destiny_socket.close()

            except Exception as e:
                print(f"Error al conectar con {destiny_host}:{destiny_port}: {e}")

        # Cerramos siempre la conexión con el cliente al finalizar
        new_socket.close()
        print(f"conexión con {new_socket_address} ha sido cerrada\n")