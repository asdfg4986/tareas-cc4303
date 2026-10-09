import socket

class SocketTCP:
    def __init__(self):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

        self.dest_addr = None
        self.seq_num = 0
        self.ack_num = 0

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