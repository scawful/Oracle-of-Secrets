from mesen2_client_lib.cart_sram import compute_inverse_checksum, apply_inverse_checksum, validate_inverse_checksum


def test_inverse_checksum_roundtrip():
    # Make a fake save block with deterministic content.
    b = bytearray(0x500)
    for i in range(0x4FE):
        b[i] = (i * 7 + 3) & 0xFF

    fixed = apply_inverse_checksum(bytes(b))
    assert validate_inverse_checksum(fixed) is True

    # If we flip a byte, validation should fail until re-applied.
    tampered = bytearray(fixed)
    tampered[0x10] ^= 0xFF
    assert validate_inverse_checksum(bytes(tampered)) is False
    refixed = apply_inverse_checksum(bytes(tampered))
    assert validate_inverse_checksum(refixed) is True


def test_inverse_checksum_matches_compute():
    b = bytes([0] * 0x500)
    inv = compute_inverse_checksum(b)
    fixed = apply_inverse_checksum(b)
    stored = fixed[0x4FE] | (fixed[0x4FF] << 8)
    assert stored == inv
