import array
import fcntl
import socket
import struct


def get_interfaces():
    """
    returns all non loopback interfaces available on the system
    """
    max_possible = 128
    bytes_ = max_possible * 32
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    names = array.array('B', b'\0' * bytes_)
    outbytes = struct.unpack('iL', fcntl.ioctl(
        s.fileno(),
        0x8912,
        struct.pack('iL', bytes_, names.buffer_info()[0])
    ))[0]
    namestr = names.tostring()
    interfaces = []
    for i in range(0, outbytes, 40):
        name = namestr[i:i + 16].split(b'\0', 1)[0]
        name = name.decode()
        if name != 'lo':
            interfaces.append(name)
    return interfaces
