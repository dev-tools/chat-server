# -*- coding: utf-8 -*-
import pytest
from twisted.test import proto_helpers

from ircserver import IRCServerFactory


@pytest.fixture
def fake_connection():
    factory = IRCServerFactory()
    protocol = factory.buildProtocol(('127.0.0.1', 0))
    transport = proto_helpers.StringTransport()
    protocol.makeConnection(transport)
    return protocol, transport


def test_single_connection(fake_connection):
    proto, tr = fake_connection
    proto.dataReceived("PING\r\n")
    assert tr.value().split()[1] == 'PONG'