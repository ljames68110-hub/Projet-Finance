import socket, os
host = os.getenv("SMTP_HOST","127.0.0.1")
port = int(os.getenv("SMTP_PORT","1026"))
s = socket.socket()
s.settimeout(5)
try:
    s.connect((host, port))
    print("TCP OK:", host, port)
except Exception as e:
    print("TCP ERR:", repr(e))
finally:
    s.close()
