import ctypes
import functools
import random
import struct
import typing as t
from fcntl import ioctl

from trio import socket

from wrath.bpf import create_filter


IP_VERSION = 4
IP_IHL = 5
IP_DSCP = 0
IP_ECN = 0
IP_TOTAL_LEN = 40
IP_ID = 0x1337
IP_FLAGS = 0x2  # DF
IP_FRAGMENT_OFFSET = 0
IP_TTL = 255
IP_PROTOCOL = 6  # TCP
IP_CHECKSUM = 0


TCP_SRC = 6969  # source port
TCP_ACK_NO = 0
TCP_DATA_OFFSET = 5
TCP_RESERVED = 0
TCP_NS = 0
TCP_CWR = 0
TCP_ECE = 0
TCP_URG = 0
TCP_ACK = 0
TCP_PSH = 0
TCP_RST = 0
TCP_SYN = 1
TCP_FIN = 0
TCP_WINDOW = 0x7110
TCP_CHECKSUM = 0
TCP_URG_PTR = 0

SIOCGIFADDR = 0x8915


@functools.cache
def get_iface_ip(interface: str) -> str:
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    ip_addr = socket.inet_ntoa(
        ioctl(
            sock.fileno(),
            SIOCGIFADDR,
            struct.pack("256s", bytes(interface[:15], "UTF-8")),
        )[20:24]
    )
    sock.close()
    return ip_addr


def create_send_sock() -> socket.SocketType:
    send_sock = socket.socket(socket.AF_INET, socket.SOCK_RAW, socket.IPPROTO_RAW)
    send_sock.setsockopt(socket.IPPROTO_IP, socket.IP_HDRINCL, 1)
    return send_sock


def create_recv_sock(target: str) -> socket.SocketType:
    recv_sock = socket.socket(socket.AF_PACKET, socket.SOCK_RAW, 0x0800)
    fprog = create_filter(target)
    recv_sock.setsockopt(socket.SOL_SOCKET, 26, fprog)
    return recv_sock


def inet_checksum(header: bytes) -> int:
    checksum = 0
    for idx in range(0, len(header), 2):
        checksum += (header[idx] << 8) | header[idx + 1]
    checksum = (checksum >> 16) + (checksum & 0xFFFF)
    checksum = ~checksum & 0xFFFF
    return checksum


@functools.cache
def build_ipv4_datagram(interface: str, target: str) -> bytes:
    ip_src = get_iface_ip(interface)
    src = socket.inet_aton(ip_src)
    dest = socket.inet_aton(target)

    size = struct.calcsize("!BBHHHBBH4s4s")
    assert size == 20

    buf = ctypes.create_string_buffer(size)

    struct.pack_into(
        "!BBHHHBBH4s4s",
        buf,  # type: ignore
        0,
        (IP_VERSION << 4) | IP_IHL,
        IP_DSCP | IP_ECN,
        IP_TOTAL_LEN,
        IP_ID,
        (IP_FLAGS << 13) | IP_FRAGMENT_OFFSET,
        IP_TTL,
        IP_PROTOCOL,
        IP_CHECKSUM,
        src,
        dest,
    )

    struct.pack_into("!H", buf, 10, inet_checksum(bytes(buf)))  # type: ignore

    return bytes(buf)


def build_tcp_segment(interface: str, target: str, port: int) -> bytes:
    ip_src = get_iface_ip(interface)

    seq_no = random.randint(0, 2 ** 32 - 1)
    size = struct.calcsize("!HHIIBBHHH")
    assert size == 20

    buf = ctypes.create_string_buffer(size)

    struct.pack_into(
        "!HHIIHHHH",
        buf,  # type: ignore
        0,
        TCP_SRC,
        port,
        seq_no,
        TCP_ACK_NO,
        (TCP_DATA_OFFSET << 12)
        | (TCP_RESERVED << 9)
        | (TCP_NS << 8)
        | (TCP_CWR << 7)
        | (TCP_ECE << 6)
        | (TCP_URG << 5)
        | (TCP_ACK << 4)
        | (TCP_PSH << 3)
        | (TCP_RST << 2)
        | (TCP_SYN << 1)
        | TCP_FIN,
        TCP_WINDOW,
        TCP_CHECKSUM,
        TCP_URG_PTR,
    )

    tcp_pseudo_header = struct.pack(
        "!4s4sHHH",
        socket.inet_aton(ip_src),
        socket.inet_aton(target),
        IP_PROTOCOL,
        len(buf),
        TCP_CHECKSUM,
    )

    struct.pack_into("!H", buf, 16, inet_checksum(tcp_pseudo_header + bytes(buf)))  # type: ignore

    return bytes(buf)


def unpack(data: bytes) -> t.Tuple[int, int]:
    buf = ctypes.create_string_buffer(data[14:54], 40)
    unpacked = struct.unpack("!BBHHHBBH4s4sHHIIBBHHH", buf)  # type: ignore
    src, flags = unpacked[10], unpacked[15]
    return src, flags
