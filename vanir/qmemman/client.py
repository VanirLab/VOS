import socket
import fcntl

class QMemmanClient:
    def request_memory(self, amount):
        self.sock = socket.socket(socket.AF_UNIX)

        flags = fcntl.fcntl(self.sock.fileno(), fcntl.F_GETFD)
        flags |= fcntl.FD_CLOEXEC
        fcntl.fcntl(self.sock.fileno(), fcntl.F_SETFD, flags)

        self.sock.connect("/var/run/vanir/qmemman.sock")
        self.sock.send(str(int(amount)).encode('ascii')+b"\n")
        received = self.sock.recv(1024).strip()
        if received == b'OK':
            return True
        else:
            return False

    def close(self):
        self.sock.close()