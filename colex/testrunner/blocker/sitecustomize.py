"""Loaded automatically by Python in the sandboxed test process: no network from tests."""
import socket


def _blocked(*_args, **_kwargs):
    raise OSError("network access is blocked in the coLEX test sandbox")


for _name in ("connect", "connect_ex", "sendto", "sendmsg", "bind"):
    setattr(socket.socket, _name, _blocked)
for _name in ("create_connection", "getaddrinfo", "gethostbyname", "gethostbyname_ex", "gethostbyaddr"):
    setattr(socket, _name, _blocked)
