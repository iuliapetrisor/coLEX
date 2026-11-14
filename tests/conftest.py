"""Shared test harness (G0-QA-01).

`make test` is always offline (D-006): the network is blocked for the whole
session, in this process.

Known limits of this guard (R-002, deferred):
- subprocesses started by tests are not covered;
- code that uses the C-level `_socket.socket` type directly is not covered,
  because that type is immutable and cannot be patched.
"""
from __future__ import annotations

import socket

import pytest


class NetworkBlocked(RuntimeError):
    """Raised when a test tries to use the network."""


def _blocked(*_args, **_kwargs):
    raise NetworkBlocked("make test is offline: network access is blocked by tests/conftest.py")


# Every name-resolution function of the socket module (R-001).
_RESOLVERS = ("getaddrinfo", "gethostbyname", "gethostbyname_ex", "gethostbyaddr", "getnameinfo")


@pytest.fixture(scope="session", autouse=True)
def _no_network():
    patch = pytest.MonkeyPatch()
    for name in ("connect", "connect_ex", "sendto", "sendmsg"):
        patch.setattr(socket.socket, name, _blocked)
    patch.setattr(socket, "create_connection", _blocked)
    for name in _RESOLVERS:
        patch.setattr(socket, name, _blocked)
    yield
    patch.undo()


@pytest.fixture
def colex_db_path(tmp_path, monkeypatch):
    """A fresh SQLite path per test, exported as COLEX_DB.

    The runtime store (G0-RT-02) reads COLEX_DB, so no test touches a shared database.
    """
    path = tmp_path / "colex.db"
    monkeypatch.setenv("COLEX_DB", str(path))
    return path
