from socketUDP import SocketUDP
from slidingWindowCC import SlidingWindowCC
import random
import time

"""Implementación de un socket TCP sobre UDP usando el protocolo Stop & Wait.

Este módulo implementa la clase SocketTCP, emulando los servicios fundamentales
de la capa de transporte TCP (orientado a conexión, confiable, control de flujo
y orientado a flujo de bytes) utilizando sockets UDP subyacentes.

Características principales del protocolo:
- Encabezado personalizado de 7 bytes:
    * Número de secuencia (seq): 4 bytes (entero sin signo, big-endian).
    * Flag SYN: 1 byte (0 o 1).
    * Flag ACK: 1 byte (0 o 1).
    * Flag FIN: 1 byte (0 o 1).
- Handshake de 3 vías para establecimiento de conexión (SYN -> SYN-ACK -> ACK).
- Demultiplexación de conexiones en el servidor (bind a puerto efímero tras SYN).
- Transferencia confiable de datos con Stop & Wait (un paquete en vuelo a la vez):
    * Envío previo de longitud total del mensaje (4 bytes).
    * Fragmentación en segmentos de carga útil de 16 bytes (MSS).
    * Detección de pérdidas mediante timeouts (1 segundo).
    * Re-transmisión ante timeout y descarte/re-acuse de duplicados.
    * Reconstrucción orientada a flujo mediante buffer `unprocessed_data`.
- Cierre ordenado de conexión de 4 vías simplificado (FIN -> FIN+ACK -> ráfaga de ACKs).
"""

class SocketTCP:
    """Emulación de socket TCP con protocolo Stop & Wait sobre datagramas UDP.

    Atributos:
        sock (socket.socket): Socket UDP subyacente de la biblioteca estándar.
        addr (tuple[str, int] | None): Dirección IP y puerto local vinculados.
        dest_addr (tuple[str, int] | None): Dirección IP y puerto del host remoto.
        seq_num (int): Número de secuencia actual del host para el seguimiento del flujo.
        remaining_bytes (int): Contador de bytes pendientes por recibir del mensaje en curso.
        unprocessed_data (bytes): Buffer acumulativo para bytes recibidos que aún no han
                                  sido leídos por la aplicación mediante recv().
    """

    def __init__(self):
        """Inicializa una nueva instancia de SocketTCP con un socket UDP subyacente."""
        self.sock = SocketUDP()

        self.addr = None
        self.dest_addr = None
        self.seq_num = 0

        self.remaining_bytes = 0
        self.unprocessed_data = b""

    @staticmethod
    def create_segment(seq: int, syn: bool, ack: bool, fin: bool, data: bytes) -> bytes:
        """Construye un segmento con encabezado binario de 7 bytes y carga útil.

        Formato del encabezado:
            [0:4] seq (4 bytes, big-endian)
            [4:5] syn (1 byte, 1 si es True, 0 si es False)
            [5:6] ack (1 byte, 1 si es True, 0 si es False)
            [6:7] fin (1 byte, 1 si es True, 0 si es False)
            [7:]  data (bytes de datos adjuntos)

        Args:
            seq (int): Número de secuencia del paquete.
            syn (bool): Bandera de sincronización (inicio de conexión).
            ack (bool): Bandera de reconocimiento / acuse de recibo.
            fin (bool): Bandera de finalización (cierre de conexión).
            data (bytes): Carga útil a transmitir dentro del segmento.

        Returns:
            bytes: Segmento completo serializado listo para ser enviado por la red.
        """
        seq_bytes = seq.to_bytes(4, byteorder='big')

        syn_byte = (1 if syn else 0).to_bytes(1, byteorder='big')
        ack_byte = (1 if ack else 0).to_bytes(1, byteorder='big')
        fin_byte = (1 if fin else 0).to_bytes(1, byteorder='big')

        header = seq_bytes + syn_byte + ack_byte + fin_byte
        return header + data

    @staticmethod
    def parse_segment(segment: bytes) -> tuple[int, bool, bool, bool, bytes]:
        """Deserializa un segmento recibido separando el encabezado de los datos.

        Args:
            segment (bytes): Segmento recibido a través de la red (mínimo 7 bytes).

        Returns:
            tuple[int, bool, bool, bool, bytes]: Tupla con los campos:
                - seq (int): Número de secuencia.
                - syn (bool): Estado del flag SYN.
                - ack (bool): Estado del flag ACK.
                - fin (bool): Estado del flag FIN.
                - data (bytes): Carga útil recibida (payload).
        """
        header = segment[:7]
        data = segment[7:]

        seq = int.from_bytes(header[:4], byteorder='big')
        syn = bool(int.from_bytes(header[4:5], byteorder='big'))
        ack = bool(int.from_bytes(header[5:6], byteorder='big'))
        fin = bool(int.from_bytes(header[6:7], byteorder='big'))

        return seq, syn, ack, fin, data

    def bind(self, address: tuple[str, int]) -> None:
        """Asocia el socket UDP local a una dirección IP y puerto específicos.

        Args:
            address (tuple[str, int]): Tupla con (ip, puerto).
        """
        self.addr = address
        self.sock.bind(address)

    def connect(self, address: tuple[str, int]) -> None:
        """Inicia y completa el handshake de 3 vías con un servidor remoto (Host A).

        Procedimiento:
            1. Genera un número de secuencia inicial aleatorio (ISN).
            2. Envía un segmento SYN al servidor y entra en un bucle con temporizador (1.0 s).
            3. Si no recibe respuesta a tiempo (TimeoutError), retransmite el SYN.
            4. Al recibir un SYN-ACK con el número de secuencia esperado (seq == isn + 1):
               - Actualiza la dirección de destino al nuevo puerto efímero del servidor.
               - Incrementa el número de secuencia.
               - Envía un segmento ACK confirmando el establecimiento.
            5. Configura el socket nuevamente a modo bloqueante (timeout = None).

        Args:
            address (tuple[str, int]): Dirección (IP, puerto) de escucha del servidor.
        """
        # Paso 1: Generar ISN y construir segmento SYN
        self.seq_num = random.randint(0, 100)
        syn_seg = self.create_segment(self.seq_num, syn=True, ack=False, fin=False, data=b'')   

        self.sock.settimeout(1.0)  # Establecer un tiempo de espera para el SYN-ACK

        # Paso 2: Transmisión y retransmisión ante timeout de SYN
        while True:
            self.sock.sendto(syn_seg, address)
            print(f"Enviado SYN con seq={self.seq_num} a {address}")
            try:
                # Esperar SYN-ACK del servidor
                syn_ack_seg, new_addr = self.sock.recvfrom(1024)
                syn_ack_seq, syn_ack_syn, syn_ack_ack, _, _ = self.parse_segment(syn_ack_seg)

                # Verificar banderas SYN y ACK y número de secuencia esperado
                if syn_ack_syn and syn_ack_ack and syn_ack_seq == self.seq_num + 1:
                    print(f"Recibido SYN-ACK con seq={syn_ack_seq} de {new_addr}")
                    # Actualizar dest_addr: el servidor responde desde un nuevo socket/puerto
                    self.dest_addr = new_addr

                    self.seq_num = syn_ack_seq + 1  # Incrementar el número de secuencia para el ACK

                    # Detener el timer del SYN y apagar timeout antes del ACK final
                    if self.sock.timer_list[0] is not None:
                        self.sock.stop_timer(0)
                    self.sock.settimeout(-1.0)

                    # Paso 3: Enviar ACK final al nuevo puerto del servidor (sin timer)
                    ack_segment = self.create_segment(self.seq_num, syn=False, ack=True, fin=False, data=b'')
                    self.sock.sendto(ack_segment, self.dest_addr)
                    print(f"Enviado ACK con seq={self.seq_num} a {new_addr}. Handshake cliente completo.")
                    break
            except TimeoutError:
                print("Timeout esperando SYN-ACK, reenviando SYN...")
                if self.sock.timer_list[0] is not None:
                    self.sock.stop_timer(0)
                continue  # Reenviar el SYN si no se recibe SYN-ACK dentro del tiempo de espera

    def accept(self) -> tuple['SocketTCP', tuple[str, int]]:
        """Acepta una conexión entrante completando el handshake de 3 vías (Host B).

        Procedimiento:
            1. Bloquea la ejecución en el socket de bienvenida hasta recibir un SYN válido.
            2. Crea una nueva instancia de SocketTCP exclusiva para atender al cliente.
            3. Asocia (bind) el nuevo socket al puerto 0 para que el sistema operativo
               le asigne automáticamente un puerto libre efímero (demultiplexación).
            4. Envía un SYN-ACK desde el nuevo socket y espera el ACK del cliente con timeout.
            5. Si expira el temporizador, retransmite el SYN-ACK hasta recibir el ACK.
            6. Retorna el nuevo socket ya conectado y la dirección del cliente.

        Returns:
            tuple[SocketTCP, tuple[str, int]]: Tupla compuesta por:
                - Nuevo SocketTCP dedicado para la transmisión de datos.
                - Dirección (IP, puerto) del cliente conectado.
        """
        # Paso 1: Esperar la llegada de un segmento SYN en el socket pasivo de escucha
        while True:
            syn_seg, client_addr = self.sock.recvfrom(1024)
            syn_seq, syn_syn, syn_ack, _, _ = self.parse_segment(syn_seg)

            if syn_syn and not syn_ack:
                print(f"Recibido SYN con seq={syn_seq} de {client_addr}. Iniciando handshake.")
                break

        # Paso 2: Crear socket dedicado para la conexión
        new_socket = SocketTCP()
        # Bind a la misma IP, pero puerto 0 (el SO asigna un puerto efímero libre)
        new_socket.bind((self.addr[0], 0))
        new_socket.dest_addr = client_addr
        
        # Asignar secuencia inicial sincronizada con el SYN del cliente
        new_socket.seq_num = syn_seq + 1

        # Paso 3: Enviar SYN-ACK desde el NUEVO socket
        syn_ack_segment = new_socket.create_segment(new_socket.seq_num, syn=True, ack=True, fin=False, data=b"")
        new_socket.sock.settimeout(1.0)  # Establecer un tiempo de espera para el ACK final

        # Paso 4: Esperar el ACK final en el NUEVO socket con retransmisión
        while True:
            new_socket.sock.sendto(syn_ack_segment, new_socket.dest_addr)
            print(f"[Nuevo Socket] Enviado SYN-ACK a {new_socket.dest_addr}")
            try:
                ack_segment, _ = new_socket.sock.recvfrom(1024)
                seq_ack, syn_ack, ack_ack, fin_ack, _ = new_socket.parse_segment(ack_segment)

                # Caso normal: el ACK es correcto y completa el handshake
                if ack_ack and not syn_ack and seq_ack == new_socket.seq_num + 1:
                    print(f"[Nuevo Socket] Recibido ACK. Handshake servidor completo.")

                    new_socket.seq_num = seq_ack
                    break

                # Caso borde: si el ACK se pierde pero el emisor ya comenzó a enviar datos
                if not syn_ack and not ack_ack and not fin_ack:
                    print("[Nuevo Socket] Caso Borde: Paquete de datos recibido durante handshake")
                    new_socket.seq_num = seq_ack
                    break  # Salir del bucle si se recibe un paquete de datos durante el handshake
            except TimeoutError:
                print("[Nuevo Socket] Timeout esperando ACK, reenviando SYN-ACK...")
                if new_socket.sock.timer_list[0] is not None:
                    new_socket.sock.stop_timer(0)
                continue  # Reenviar el SYN-ACK si no se recibe ACK dentro del tiempo de espera

        if new_socket.sock.timer_list[0] is not None:
            new_socket.sock.stop_timer(0)
        new_socket.sock.settimeout(-1.0)  # Restablecer el tiempo de espera a -1.0 (sin timeout) después del handshake
        # Retorna el nuevo objeto socketTCP y la dirección del cliente
        return new_socket, new_socket.dest_addr

    def _send_reliable_stop_and_wait(self, data: bytes) -> None:
        """Transmite un bloque de datos de forma confiable usando el protocolo Stop & Wait.

        Garantiza la entrega del bloque:
            1. Empaqueta el bloque en un segmento sin banderas especiales (datos puros).
            2. Configura un temporizador de retransmisión de 1.0 segundo.
            3. Envía el paquete y espera la confirmación (ACK) del receptor.
            4. Si expira el temporizador (TimeoutError), retransmite el mismo segmento.
            5. Al recibir un ACK con número de secuencia ack_seq == seq_num + len(data),
               avanza el número de secuencia local y culmina la transmisión.

        Args:
            data (bytes): Bloque binario a transmitir confiablemente.
        """
        # Paso 1: Crear segmento de datos con el número de secuencia actual
        segment = self.create_segment(self.seq_num, syn=False, ack=False, fin=False, data=data)
        self.sock.settimeout(1.0)  # Establecer un tiempo de espera para el ACK

        # Paso 2: Bucle Stop & Wait (envío y espera de ACK)
        while True:
            self.sock.sendto(segment, self.dest_addr)
            try:
                ack_seg, _ = self.sock.recvfrom(1024)
                ack_seq, ack_syn, ack_ack, ack_fin, _ = self.parse_segment(ack_seg)

                # Verificar que sea un ACK válido y que reconozca los bytes transmitidos
                if ack_ack and ack_seq == self.seq_num + len(data):
                    self.seq_num = ack_seq  
                    break  # ACK recibido correctamente, salir del bucle
            except TimeoutError:
                print("Timeout esperando ACK, reenviando segmento...")
                if self.sock.timer_list[0] is not None:
                    self.sock.stop_timer(0)
                continue  # Reenviar el segmento si no se recibe ACK dentro del tiempo de espera

        if self.sock.timer_list[0] is not None:
            self.sock.stop_timer(0)
        self.sock.settimeout(-1.0)  # Restablecer el tiempo de espera a -1.0 (sin timeout) después de recibir el ACK

    def send_using_stop_and_wait(self, message: bytes) -> None:
        """Envía un mensaje completo a través del canal confiable.

        Mecanismo de fragmentación y enmarcado:
            1. Enmarca el mensaje enviando primero un prefijo de 4 bytes (big-endian)
               con la longitud total del mensaje en bytes.
            2. Fragmenta el mensaje en trozos de tamaño máximo de 16 bytes (MSS).
            3. Transmite cada trozo secuencialmente utilizando el protocolo confiable
               Stop & Wait (_send_reliable).

        Args:
            message (bytes): Mensaje binario completo a ser transmitido.
        """
        # 1. Enviar la longitud del mensaje como un entero de 4 bytes
        msg_len_bytes = len(message).to_bytes(4, byteorder='big')
        self._send_reliable_stop_and_wait(msg_len_bytes)

        # 2. Enviar el mensaje fragmentado en segmentos de hasta 16 bytes
        for i in range(0, len(message), 16):
            chunk = message[i:i + 16]
            self._send_reliable_stop_and_wait(chunk)

    def recv_using_stop_and_wait(self, buff_size: int) -> bytes:
        """Recibe hasta buff_size bytes de datos simulando una interfaz de flujo (stream).

        Funcionamiento del buffer y recepción:
            1. Vacía prioritariamente los datos pendientes en el buffer interno (`unprocessed_data`).
               Si satisface los `buff_size` solicitados, retorna inmediatamente.
            2. Si no hay un mensaje en recepción (`remaining_bytes == 0`), espera el paquete
               de prefijo de 4 bytes con la longitud total del nuevo mensaje.
               - Si detecta un número de secuencia duplicado previo (seq < seq_num), reenvía
                 el ACK correspondiente para destrabar al emisor.
            3. Entra en un ciclo de recepción de fragmentos hasta recolectar la cantidad
               necesaria o agotar los bytes restantes del mensaje en curso:
               - Paquetes en orden (seq == seq_num): acumula los datos, incrementa `seq_num`
                 y decrementa `remaining_bytes`.
               - Paquetes duplicados (seq < seq_num): los descarta pero reenvía el ACK
                 para confirmar su recepción previa.
               - Envía un segmento ACK con el número de secuencia actualizado.
            4. Si se recibieron más bytes de los pedidos por la aplicación en esta llamada,
               guarda el excedente en `unprocessed_data`.

        Args:
            buff_size (int): Cantidad máxima de bytes que la aplicación desea leer.

        Returns:
            bytes: Datos leídos del flujo de red (hasta buff_size bytes).
        """
        ret_data = b""

        # Paso 1: Consumir datos remanentes en el buffer interno si existen
        if self.unprocessed_data:
            take = min(len(self.unprocessed_data), buff_size)
            ret_data = self.unprocessed_data[:take]
            self.unprocessed_data = self.unprocessed_data[take:]

            # Si el buffer cubrió completamente lo solicitado, retornamos de inmediato
            if len(ret_data) == buff_size:
                return ret_data

        needed_bytes = buff_size - len(ret_data)

        # Paso 2: Si no hay un mensaje activo en curso, esperar el paquete con la longitud (4 bytes)
        if self.remaining_bytes == 0:
            while True:
                seg, _ = self.sock.recvfrom(1024)
                seq, syn, ack, fin, data = self.parse_segment(seg)

                if not syn and not ack and not fin:
                    # Paquete de longitud esperado (4 bytes de entero en orden)
                    if len(data) == 4 and seq == self.seq_num:
                        self.remaining_bytes = int.from_bytes(data, byteorder='big')
                        self.seq_num += len(data)
                        
                        # Confirmar la recepción del tamaño del mensaje
                        ack_seg = self.create_segment(self.seq_num, syn=False, ack=True, fin=False, data=b'')
                        self.sock.sendto(ack_seg, self.dest_addr)

                        if self.remaining_bytes > 0:
                            break
                        
                    # Paquete duplicado rezagado: reenviar ACK para confirmar
                    elif seq < self.seq_num:
                        print(f"Duplicado atrapado (seq={seq}) esperando nuevo mensaje. Reenviando ACK...")
                        ack_seg = self.create_segment(self.seq_num, syn=False, ack=True, fin=False, data=b'')
                        self.sock.sendto(ack_seg, self.dest_addr)

        # Calcular cuántos bytes recibir en esta iteración sin sobrepasar el mensaje actual
        bytes_to_receive = min(needed_bytes, self.remaining_bytes)
        initial_ret_len = len(ret_data)

        # Paso 3: Bucle de recepción de fragmentos de datos
        while (len(ret_data) - initial_ret_len) < bytes_to_receive:
            seg, _ = self.sock.recvfrom(1024)
            seq, syn, ack, fin, data = self.parse_segment(seg)

            if not syn and not ack and not fin:
                # Segmento esperado en orden
                if seq == self.seq_num:
                    ret_data += data
                    self.seq_num += len(data)
                    self.remaining_bytes -= len(data)
                # Segmento duplicado por retransmisión
                elif seq < self.seq_num:
                    print(f"Recibido segmento duplicado con seq={seq}, reenviando ACK...")

                # Enviar siempre acuse de recibo con el seq_num acumulado
                ack_seg = self.create_segment(self.seq_num, syn=False, ack=True, fin=False, data=b'')
                self.sock.sendto(ack_seg, self.dest_addr)

        # Paso 4: Gestionar excedente si se recibió más de lo solicitado por buff_size
        target_len = initial_ret_len + bytes_to_receive
        if len(ret_data) > target_len:
            self.unprocessed_data += ret_data[target_len:]
            ret_data = ret_data[:target_len]

        return ret_data

    def send_using_go_back_n(self, message: bytes) -> None:
        self.sock.settimeout(1.0)

        # 1. Enmarcado y fragmentación
        msg_len_bytes = len(message).to_bytes(4, byteorder='big')
        data_list = [msg_len_bytes] + [message[i:i + 16] for i in range(0, len(message), 16)]
        
        window_size = 8
        # Creamos la ventana con los datos y nuestro número de secuencia actual
        data_window = SlidingWindowCC(window_size, data_list, self.seq_num)
        
        # Este índice rastrea cuántos paquetes de la ventana actual ya enviamos
        next_idx_to_send = 0 
        
        # Mientras queden datos no confirmados en la base de la ventana
        while data_window.get_data(0) is not None:
            
            # a) Enviar todos los segmentos disponibles en la ventana que no hayan sido enviados
            while next_idx_to_send < window_size and data_window.get_data(next_idx_to_send) is not None:
                curr_data = data_window.get_data(next_idx_to_send)
                curr_seq = data_window.get_sequence_number(next_idx_to_send)
                segment = self.create_segment(curr_seq, syn=False, ack=False, fin=False, data=curr_data)
                
                # SocketUDP iniciará (o reiniciará) el timer automáticamente
                self.sock.sendto(segment, self.dest_addr, timer_index=0)
                next_idx_to_send += 1

            # b) Esperar el ACK de confirmación
            try:
                # Usamos el recvfrom del SocketUDP que levanta TimeoutError
                ack_seg, _ = self.sock.recvfrom(1024)
                ack_seq, ack_syn, ack_ack, ack_fin, _ = self.parse_segment(ack_seg)
                
                if ack_ack:
                    base_seq = data_window.get_sequence_number(0)
                    
                    # Go-Back N usa ACKs acumulativos (si ack_seq es mayor a la base, confirmamos)
                    if ack_seq > base_seq:
                        # Calculamos cuántos espacios debe avanzar la ventana
                        steps = 0
                        for i in range(window_size):
                            seq_i = data_window.get_sequence_number(i)
                            if seq_i is not None and seq_i < ack_seq:
                                steps += 1
                            else:
                                break
                                
                        if steps > 0:
                            data_window.move_window(steps)
                            next_idx_to_send -= steps  # Ajustamos el índice relativo al avance
                            self.seq_num = ack_seq

                            # Detener el timer de la base confirmada
                            if self.sock.timer_list[0] is not None:
                                self.sock.stop_timer(0)

                            # Si aún quedan paquetes en vuelo y no se enviará uno nuevo que active el timer
                            if next_idx_to_send > 0:
                                will_send_new = (next_idx_to_send < window_size and data_window.get_data(next_idx_to_send) is not None)
                                if not will_send_new:
                                    from threading import Timer
                                    self.sock.timer_list[0] = Timer(self.sock.timeout, self.sock._time_up_function, args=(0,))
                                    self.sock.timer_list[0].start()
                            
            except TimeoutError:
                # c) Manejo de Pérdida: Timeout en GBN significa retransmitir TODA la ventana
                print("Timeout en Go-Back N, reenviando la ventana completa...")
                if self.sock.timer_list[0] is not None:
                    self.sock.stop_timer(0)
                next_idx_to_send = 0  # Reiniciando el índice a 0 reenviará toda la ventana en el próximo ciclo



        if self.sock.timer_list[0] is not None:

            self.sock.stop_timer(0)

        self.sock.settimeout(-1.0)

    def recv_using_go_back_n(self, buff_size: int) -> bytes:
        """En Go-Back N, el receptor funciona exactamente igual que en Stop & Wait."""
        return self.recv_using_stop_and_wait(buff_size)

    def send(self, message: bytes, mode="stop_and_wait"):
        if mode == "stop_and_wait":
            self.send_using_stop_and_wait(message)
        elif mode == "go_back_n":
            self.send_using_go_back_n(message)

    def recv(self, buff_size: int, mode="stop_and_wait"):
        if mode == "stop_and_wait":
            return self.recv_using_stop_and_wait(buff_size)
        elif mode == "go_back_n":
            return self.recv_using_go_back_n(buff_size)

    def close(self) -> None:
        """Ejecuta el cierre activo de la conexión (Host A).

        Procedimiento:
            1. Genera un segmento FIN (`fin=True`) con el número de secuencia actual.
            2. Envía el FIN y espera la respuesta conjunta FIN+ACK del receptor,
               con un temporizador de 1.0 s y un máximo de 3 reintentos.
            3. Al recibir el FIN+ACK, incrementa el número de secuencia y envía una
               ráfaga de 3 segmentos ACK consecutivos al receptor (técnica para
               mitigar la pérdida del ACK final en UDP sin requerir estado TIME_WAIT).
            4. Cierra definitivamente el socket UDP subyacente.
        """
        print("\nHost A Iniciando cierre de conexión...")

        # Paso 1: Construir segmento FIN
        fin_seg = self.create_segment(self.seq_num, syn=False, ack=False, fin=True, data=b'')

        self.sock.settimeout(1.0)  # Establecer un tiempo de espera para el ACK + FIN
        timeouts_count = 0

        # Pasos 1 y 2: Enviar FIN y esperar FIN+ACK (con hasta 3 reintentos)
        while timeouts_count < 3:
            self.sock.sendto(fin_seg, self.dest_addr)
            try:
                seg, _ = self.sock.recvfrom(1024)
                seq, _, ack, fin, _ = self.parse_segment(seg)
                
                # Comprobar recepción de FIN+ACK sincronizado
                if fin and ack and seq == self.seq_num + 1:
                    print(f"Recibido FIN+ACK con seq={seq}")
                    self.seq_num = seq + 1
                    break
            except TimeoutError:
                if self.sock.timer_list[0] is not None:
                    self.sock.stop_timer(0)
                timeouts_count += 1
                print(f"Timeout esperando FIN+ACK (intento {timeouts_count}/3)")
                
        if timeouts_count == 3:
            print("Se alcanzó el límite de timeouts. Forzando cierre.")
        else:
            # Detener temporizador antes de la ráfaga de cierre
            if self.sock.timer_list[0] is not None:
                self.sock.stop_timer(0)
            self.sock.settimeout(-1.0)

            # Paso 3: Enviar ráfaga de 3 ACKs finales consecutivos para asegurar entrega
            ack_seg = self.create_segment(self.seq_num, syn=False, ack=True, fin=False, data=b'')
            print(f"Enviando ráfaga de 3 ACKs finales...")
            for _ in range(3):
                self.sock.sendto(ack_seg, self.dest_addr)
            print("ACKs enviados. Conexión cerrada limpiamente.")
            
        # Paso 4: Cerrar el socket UDP del sistema
        self.sock.close()

    def recv_close(self) -> None:
        """Ejecuta el cierre pasivo de la conexión (Host B).

        Procedimiento:
            1. Espera pasivamente a que el cliente (Host A) inicie la desconexión
               enviando un paquete FIN.
               - Si recibe segmentos duplicados anteriores, responde con su ACK acumulado.
            2. Al recibir el FIN válido, responde enviando un segmento combinado FIN+ACK.
            3. Entra en un bucle con temporizador (1.0 s) esperando el ACK final del cliente,
               permitiendo hasta 3 reintentos de transmisión del FIN+ACK si ocurre timeout.
            4. Una vez recibido el ACK final o superado el número máximo de reintentos,
               cierra definitivamente el socket UDP subyacente.
        """
        print("\nHost B Iniciando cierre de conexión...")

        # Paso 1: Esperar recepción del segmento FIN de Host A
        while True:
            seg, _ = self.sock.recvfrom(1024)
            seq, syn, ack, fin, _ = self.parse_segment(seg)

            if fin and not ack and not syn and seq == self.seq_num:
                print(f"Recibido FIN con seq={seq}. Enviando FIN + ACK...")
                self.seq_num += 1
                break

            # Si llega un segmento rezagado anterior, re-acusar para no bloquear al emisor
            elif seq < self.seq_num:
                print(f"Recibido segmento duplicado con seq={seq}, reenviando ACK...")
                ack_seg = self.create_segment(self.seq_num, syn=False, ack=True, fin=False, data=b'')
                self.sock.sendto(ack_seg, self.dest_addr)

        # Paso 2: Construir y enviar segmento combinado FIN + ACK hacia Host A
        fin_ack_seg = self.create_segment(self.seq_num, syn=False, ack=True, fin=True, data=b'')
        
        self.sock.settimeout(1.0)
        timeouts_count = 0
        
        # Paso 3: Esperar el ACK final con hasta 3 reintentos ante timeouts
        while timeouts_count < 3:
            self.sock.sendto(fin_ack_seg, self.dest_addr)
            try:
                seg, _ = self.sock.recvfrom(1024)
                seq, syn, ack, fin, _ = self.parse_segment(seg)
                
                if ack and not fin and not syn and seq == self.seq_num + 1:
                    print(f"Recibido ACK final con seq={seq}. Cierre completo.")
                    break
            except TimeoutError:
                if self.sock.timer_list[0] is not None:
                    self.sock.stop_timer(0)
                timeouts_count += 1
                print(f"Timeout esperando ACK final (intento {timeouts_count}/3)")
                
        if timeouts_count == 3:
            print("Se alcanzó límite de timeouts. Asumiendo desconexión del cliente.")
            
        # Paso 4: Cerrar el socket UDP del sistema
        self.sock.close()