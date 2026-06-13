import hashlib

# Base58 alphabet used by Bitcoin / Tron (no 0, O, I, l)
_B58_ALPHABET = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"

# A mainnet TRON address is base58check of 21 bytes:
#   0x41 prefix + 20-byte account, followed by a 4-byte double-sha256 checksum.
# Encoded it is always 34 chars and starts with "T".
_TRON_PREFIX_BYTE = 0x41
_TRON_DECODED_LEN = 25  # 1 prefix + 20 address + 4 checksum


def _b58decode(value: str):
    """Decode a base58 string to bytes. Returns None on invalid characters."""
    num = 0
    for char in value:
        index = _B58_ALPHABET.find(char)
        if index == -1:
            return None
        num = num * 58 + index

    decoded = num.to_bytes((num.bit_length() + 7) // 8, "big") if num else b""

    # Restore leading zero bytes (encoded as leading '1' characters).
    pad = len(value) - len(value.lstrip("1"))
    return b"\x00" * pad + decoded


def is_valid_tron_address(address: str) -> bool:
    """
    Validate a TRON (TRC20) mainnet address: correct length, prefix,
    base58 encoding and double-sha256 checksum.
    """
    if not isinstance(address, str):
        return False

    address = address.strip()
    if len(address) != 34 or not address.startswith("T"):
        return False

    raw = _b58decode(address)
    if raw is None or len(raw) != _TRON_DECODED_LEN:
        return False
    if raw[0] != _TRON_PREFIX_BYTE:
        return False

    payload, checksum = raw[:21], raw[21:]
    expected = hashlib.sha256(hashlib.sha256(payload).digest()).digest()[:4]
    return checksum == expected
