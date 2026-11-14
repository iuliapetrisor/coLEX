"""The harness itself: offline by construction, isolated database path."""
from __future__ import annotations

import os
import socket

import pytest

from tests.conftest import NetworkBlocked


def test_tcp_connect_is_blocked():
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        with pytest.raises(NetworkBlocked):
            sock.connect(("127.0.0.1", 9))
    finally:
        sock.close()


def test_create_connection_is_blocked():
    with pytest.raises(NetworkBlocked):
        socket.create_connection(("127.0.0.1", 9), timeout=1)


def test_dns_lookup_is_blocked():
    with pytest.raises(NetworkBlocked):
        socket.getaddrinfo("openrouter.ai", 443)


def test_udp_send_is_blocked():
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        with pytest.raises(NetworkBlocked):
            sock.sendto(b"x", ("127.0.0.1", 9))
    finally:
        sock.close()


def test_db_path_is_per_test_and_exported(colex_db_path, tmp_path):
    assert colex_db_path.parent == tmp_path
    assert os.environ["COLEX_DB"] == str(colex_db_path)
    assert not colex_db_path.exists()
