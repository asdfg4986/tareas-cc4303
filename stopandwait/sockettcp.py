import socket
import random

class SocketTCP:
    def __init__(self):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

        self.addr = None
        self.dest_addr = None
        self.seq_num = 0

        self.remaining_bytes = 0
        self.unprocessed_data = b""

    @staticmethod
    def create_segment(seq: int, syn: bool, ack: bool, fin: bool, data: bytes) -> bytes:
        seq_bytes = seq.to_bytes(4, byteorder='big')

        syn_byte = (1 if syn else 0).to_bytes(1, byteorder='big')
        ack_byte = (1 if ack else 0).to_bytes(1, byteorder='big')
        fin_byte = (1 if fin else 0).to_bytes(1, byteorder='big')

        header = seq_bytes + syn_byte + ack_byte + fin_byte
        return header + data

    @staticmethod
    def parse_segment(segment: bytes) -> tuple[int, bool, bool, bool, bytes]:
        header = segment[:7]
        data = segment[7:]

        seq = int.from_bytes(header[:4], byteorder='big')
        syn = bool(int.from_bytes(header[4:5], byteorder='big'))
        ack = bool(int.from_bytes(header[5:6], byteorder='big'))
        fin = bool(int.from_bytes(header[6:7], byteorder='big'))

        return seq, syn, ack, fin, data

    def bind(self, address: tuple[str, int]) -> None:
        self.addr = address
        self.sock.bind(address)

    def connect(self, address: tuple[str, int]) -> None:
        # Enviar SYN
        self.seq_num = random.randint(0, 100)
        syn_seg = self.create_segment(self.seq_num, syn=True, ack=False, fin=False, data=b'')   

        self.sock.settimeout(1.0)  # Establecer un tiempo de espera para el SYN-ACK

        while True:
            self.sock.sendto(syn_seg, address)
            print(f"Enviado SYN con seq={self.seq_num} a {address}")
            try:
                # Esperar SYN-ACK
                syn_ack_seg, new_addr = self.sock.recvfrom(1024)
                syn_ack_seq, syn_ack_syn, syn_ack_ack, _, _ = self.parse_segment(syn_ack_seg)

                if syn_ack_syn and syn_ack_ack and syn_ack_seq == self.seq_num + 1:
                    print(f"Recibido SYN-ACK con seq={syn_ack_seq} de {new_addr}")
                    self.dest_addr = new_addr

                    self.seq_num = syn_ack_seq + 1  # Incrementar el número de secuencia para el ACK

                    # Enviar ACK
                    ack_segment = self.create_segment(self.seq_num, syn=False, ack=True, fin=False, data=b'')
                    self.sock.sendto(ack_segment, self.dest_addr)
                    print(f"Enviado ACK con seq={self.seq_num} a {new_addr}. Handshake cliente completo.")
                    break
            except socket.timeout:
                print("Timeout esperando SYN-ACK, reenviando SYN...")
                continue  # Reenviar el SYN si no se recibe SYN-ACK dentro del tiempo de espera

        self.sock.settimeout(None)  # Restablecer el tiempo de espera a None (bloqueante) después del handshake

    def accept(self) -> tuple['SocketTCP', tuple[str, int]]:
        # Esperar SYN
        while True:
            syn_seg, client_addr = self.sock.recvfrom(1024)
            syn_seq, syn_syn, syn_ack, _, _ = self.parse_segment(syn_seg)

            if syn_syn and not syn_ack:
                print(f"Recibido SYN con seq={syn_seq} de {client_addr}. Iniciando handshake.")
                break

        # Crear nuevo socket para esta conexión específica
        new_socket = SocketTCP()
        # Bind a la misma IP, pero puerto 0 (se asignará un puerto libre)
        new_socket.bind((self.addr[0], 0))
        new_socket.dest_addr = client_addr
        
        # Le asignamos una secuencia inicial aleatoria
        new_socket.seq_num = syn_seq + 1

        # 2. Enviar SYN-ACK desde el NUEVO socket
        syn_ack_segment = new_socket.create_segment(new_socket.seq_num, syn=True, ack=True, fin=False, data=b"")
        new_socket.sock.settimeout(1.0)  # Establecer un tiempo de espera para el ACK final

        # 3. Esperar el ACK final en el NUEVO socket
        while True:
            new_socket.sock.sendto(syn_ack_segment, new_socket.dest_addr)
            print(f"[Nuevo Socket] Enviado SYN-ACK a {new_socket.dest_addr}")
            try:
                ack_segment, _ = new_socket.sock.recvfrom(1024)
                seq_ack, syn_ack, ack_ack, fin_ack, _ = new_socket.parse_segment(ack_segment)

                # Caso en que el ACK es correcto y completa el handshake
                if ack_ack and not syn_ack and seq_ack == new_socket.seq_num + 1:
                    print(f"[Nuevo Socket] Recibido ACK. Handshake servidor completo.")

                    new_socket.seq_num = seq_ack
                    break

                if not syn_ack and not ack_ack and not fin_ack:
                    print("[Nuevo Socket] Caso Borde: Paquete de datos recibido durante handshake")
                    new_socket.seq_num = seq_ack
                    break  # Salir del bucle si se recibe un paquete de datos durante el handshake
            except socket.timeout:
                print("[Nuevo Socket] Timeout esperando ACK, reenviando SYN-ACK...")
                continue  # Reenviar el SYN-ACK si no se recibe ACK dentro del tiempo de espera

        new_socket.sock.settimeout(None)  # Restablecer el tiempo de espera a None (bloqueante) después del handshake
        # Retorna el nuevo objeto socketTCP y la dirección del cliente
        return new_socket, new_socket.dest_addr

    def _send_reliable(self, data: bytes) -> None:
        segment = self.create_segment(self.seq_num, syn=False, ack=False, fin=False, data=data)
        self.sock.settimeout(1.0)  # Establecer un tiempo de espera para el ACK

        while True:
            self.sock.sendto(segment, self.dest_addr)
            try:
                ack_seg, _ = self.sock.recvfrom(1024)
                ack_seq, ack_syn, ack_ack, ack_fin, _ = self.parse_segment(ack_seg)

                if ack_ack and ack_seq == self.seq_num + len(data):
                    self.seq_num = ack_seq  
                    break  # ACK recibido correctamente, salir del bucle
            except socket.timeout:
                print("Timeout esperando ACK, reenviando segmento...")
                continue  # Reenviar el segmento si no se recibe ACK dentro del tiempo de espera

        self.sock.settimeout(None)  # Restablecer el tiempo de espera a None (bloqueante) después de recibir el ACK

    def send(self, message: bytes) -> None:
        # 1. Enviar la longitud del mensaje como un entero de 4 bytes
        msg_len_bytes = len(message).to_bytes(4, byteorder='big')
        self._send_reliable(msg_len_bytes)

        # 2. Enviar el mensaje en segmentos de 16 bytes
        for i in range(0, len(message), 16):
            chunk = message[i:i + 16]
            self._send_reliable(chunk)

    def recv(self, buff_size: int) -> bytes:
        ret_data = b""

        if self.unprocessed_data:
            take = min(len(self.unprocessed_data), buff_size)
            ret_data = self.unprocessed_data[:take]
            self.unprocessed_data = self.unprocessed_data[take:]

            if len(ret_data) == buff_size:
                return ret_data

        needed_bytes = buff_size - len(ret_data)

        if self.remaining_bytes == 0:
            while True:
                seg, _ = self.sock.recvfrom(1024)
                seq, syn, ack, fin, data = self.parse_segment(seg)

                if not syn and not ack and not fin:
                    if len(data) == 4 and seq == self.seq_num:
                        self.remaining_bytes = int.from_bytes(data, byteorder='big')
                        self.seq_num += len(data)
                        
                        ack_seg = self.create_segment(self.seq_num, syn=False, ack=True, fin=False, data=b'')
                        self.sock.sendto(ack_seg, self.dest_addr)

                        if self.remaining_bytes > 0:
                            break
                        
                    elif seq < self.seq_num:
                        print(f"Duplicado atrapado (seq={seq}) esperando nuevo mensaje. Reenviando ACK...")
                        ack_seg = self.create_segment(self.seq_num, syn=False, ack=True, fin=False, data=b'')
                        self.sock.sendto(ack_seg, self.dest_addr)

        bytes_to_receive = min(needed_bytes, self.remaining_bytes)
        initial_ret_len = len(ret_data)

        while (len(ret_data) - initial_ret_len) < bytes_to_receive:
            seg, _ = self.sock.recvfrom(1024)
            seq, syn, ack, fin, data = self.parse_segment(seg)

            if not syn and not ack and not fin:
                if seq == self.seq_num:
                    ret_data += data
                    self.seq_num += len(data)
                    self.remaining_bytes -= len(data)
                elif seq < self.seq_num:
                    print(f"Recibido segmento duplicado con seq={seq}, reenviando ACK...")

                ack_seg = self.create_segment(self.seq_num, syn=False, ack=True, fin=False, data=b'')
                self.sock.sendto(ack_seg, self.dest_addr)

        target_len = initial_ret_len + bytes_to_receive
        if len(ret_data) > target_len:
            self.unprocessed_data += ret_data[target_len:]
            ret_data = ret_data[:target_len]

        return ret_data

    def close(self) -> None:
        print("\nHost A Iniciando cierre de conexión...")

        fin_seg = self.create_segment(self.seq_num, syn=False, ack=False, fin=True, data=b'')

        self.sock.settimeout(1.0)  # Establecer un tiempo de espera para el ACK + FIN
        timeouts_count = 0

        # 1 y 2. Enviar FIN y esperar FIN+ACK (con hasta 3 reintentos)
        while timeouts_count < 3:
            self.sock.sendto(fin_seg, self.dest_addr)
            try:
                seg, _ = self.sock.recvfrom(1024)
                seq, _, ack, fin, _ = self.parse_segment(seg)
                
                if fin and ack and seq == self.seq_num + 1:
                    print(f"Recibido FIN+ACK con seq={seq}")
                    self.seq_num = seq + 1
                    break
            except socket.timeout:
                timeouts_count += 1
                print(f"Timeout esperando FIN+ACK (intento {timeouts_count}/3)")
                
        if timeouts_count == 3:
            print("Se alcanzó el límite de timeouts. Forzando cierre.")
        else:
            # 3. Enviar ACK final 3 veces seguidas (como pide la tarea)
            ack_seg = self.create_segment(self.seq_num, syn=False, ack=True, fin=False, data=b'')
            print(f"Enviando ráfaga de 3 ACKs finales...")
            for _ in range(3):
                self.sock.sendto(ack_seg, self.dest_addr)
                try:
                    # Esperamos un momento entre envíos imitando un pequeño delay
                    self.sock.recvfrom(1024) 
                except socket.timeout:
                    pass
            print("ACKs enviados. Conexión cerrada limpiamente.")
            
        self.sock.close()

    def recv_close(self) -> None:
        print("\nHost B Iniciando cierre de conexión...")

        # Esperar FIN del Host A
        while True:
            seg, _ = self.sock.recvfrom(1024)
            seq, syn, ack, fin, _ = self.parse_segment(seg)

            if fin and not ack and not syn and seq == self.seq_num:
                print(f"Recibido FIN con seq={seq}. Enviando FIN + ACK...")
                self.seq_num += 1
                break

            elif seq < self.seq_num:
                print(f"Recibido segmento duplicado con seq={seq}, reenviando ACK...")
                ack_seg = self.create_segment(self.seq_num, syn=False, ack=True, fin=False, data=b'')
                self.sock.sendto(ack_seg, self.dest_addr)

        # Enviar ACK + FIN al Host A
        fin_ack_seg = self.create_segment(self.seq_num, syn=False, ack=True, fin=True, data=b'')
        
        self.sock.settimeout(1.0)
        timeouts_count = 0
        
        # 3. Esperar ACK final con hasta 3 timeouts
        while timeouts_count < 3:
            self.sock.sendto(fin_ack_seg, self.dest_addr)
            try:
                seg, _ = self.sock.recvfrom(1024)
                seq, syn, ack, fin, _ = self.parse_segment(seg)
                
                if ack and not fin and not syn and seq == self.seq_num + 1:
                    print(f"Recibido ACK final con seq={seq}. Cierre completo.")
                    break
            except socket.timeout:
                timeouts_count += 1
                print(f"Timeout esperando ACK final (intento {timeouts_count}/3)")
                
        if timeouts_count == 3:
            print("Se alcanzó límite de timeouts. Asumiendo desconexión del cliente.")
            
        self.sock.close()