"""Code Breaker: the offline guard does not reach the C-level socket type.

Checks identity against the blocking function, so this test never touches the network itself.
"""
from __future__ import annotations

import _socket

import pytest

from tests.conftest import _blocked


@pytest.mark.xfail(strict=True, reason="R-002 (deferred): _socket.socket is immutable and cannot be patched")
def test_c_level_socket_connect_is_blocked():
    assert _socket.socket.connect is _blocked
