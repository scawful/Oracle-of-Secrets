"""
Tests for P_ASSERT command encoding.
"""

from mesen2_client_lib.bridge import MesenBridge


def test_p_assert_uses_expected_p_key(mock_server, mock_socket_path):
    mock_server.set_response("P_ASSERT", {"success": True, "data": {"id": 123}})
    bridge = MesenBridge(socket_path=mock_socket_path)

    res = bridge.p_assert(0x0188C9, expected=0x00, mask=0x30)

    assert res.get("success") is True
    cmd = mock_server.received_commands[-1]
    assert cmd["type"] == "P_ASSERT"
    assert cmd["addr"] == "0x0188C9"
    assert cmd["expected_p"] == "0x00"
    assert cmd["mask"] == "0x30"
