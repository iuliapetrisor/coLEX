"""Code Breaker: holes in the offline guard of tests/conftest.py.

Checks identity against the blocking function, so this test never touches the network itself.
"""
from __future__ import annotations

import socket

from tests.conftest import _blocked


def test_all_dns_entry_points_are_blocked():
    unblocked = [
        name
        for name in ("getaddrinfo", "gethostbyname", "gethostbyname_ex", "gethostbyaddr")
        if getattr(socket, name) is not _blocked
    ]
    assert unblocked == []
