import ctypes
import struct
from trio import socket

buf = None  # pylint: disable=invalid-name


def create_filter(target: str) -> bytes:
    """
    Creates an eBPF filter that only allows packets coming from the target.
    """
    target_ip_addr = int.from_bytes(socket.inet_aton(target), "big")

    # the filter is generated using `tcpdump(8)`
    bpf_filter = [
        [0x28, 0, 0, 0x0000000C],
        [0x15, 0, 12, 0x00000800],
        [0x20, 0, 0, 0x0000001A],
        [0x15, 0, 10, target_ip_addr],
        [0x30, 0, 0, 0x00000017],
        [0x15, 2, 0, 0x00000084],
        [0x15, 1, 0, 0x00000006],
        [0x15, 0, 6, 0x00000011],
        [0x28, 0, 0, 0x00000014],
        [0x45, 4, 0, 0x00001FFF],
        [0xB1, 0, 0, 0x0000000E],
        [0x48, 0, 0, 0x00000010],
        [0x15, 0, 1, 0x00001B39],
        [0x6, 0, 0, 0x00040000],
        [0x6, 0, 0, 0x00000000],
    ]

    filters = b"".join(x for x in [struct.pack("HBBI", *x) for x in bpf_filter])

    global buf  # pylint: disable=global-statement, invalid-name
    buf = ctypes.create_string_buffer(filters)

    fprog = struct.pack("HL", len(bpf_filter), ctypes.addressof(buf))
    return fprog
