"""API key generation utility — ASP-FEAT-ASP-00 v1.0 §10 (S-1).

Format:  asp_<prefix12>_<secret32>
  - prefix: 12 chars, base36 ([a-z0-9]), ~62 bits. UNIQUE INDEX enforced by DB.
  - secret: 32 chars, base62 ([A-Za-z0-9]), ~190 bits.
  - scheme tag and separator are literal.

Total key length: 50 characters (4 + 12 + 1 + 32 + 1).

Generation uses `secrets.choice` to guarantee CSPRNG-grade entropy.
Hashing uses bcrypt at the library's default work factor (12 rounds).

Public API:
    generate_api_key() -> tuple[str, str, str]
        Returns (raw_key, prefix, hashed_key_str). The raw key is the full
        plaintext `asp_<prefix12>_<secret32>`; the hash is bcrypt over the
        raw key (UTF-8), already decoded to str for direct storage.

    is_new_format(key: str) -> bool
        Regex-only format check. No DB lookup.

    parse_prefix(key: str) -> str | None
        Returns the 12-char prefix if the key matches the new format,
        else None. Safe to log the prefix; NEVER log the full key.
"""
from __future__ import annotations

import re
import secrets
import string

import bcrypt

_ALPHABET_PREFIX = string.digits + string.ascii_lowercase            # base36
_ALPHABET_SECRET = string.digits + string.ascii_letters              # base62
_PREFIX_LEN = 12
_SECRET_LEN = 32
_SCHEME = "asp_"

_NEW_FORMAT_RE = re.compile(r"^asp_[a-z0-9]{12}_[A-Za-z0-9]{32}$")


def generate_api_key() -> tuple[str, str, str]:
    """Generate a fresh new-format API key.

    Returns:
        (raw_key, prefix, hashed_key_str)

        raw_key         — full plaintext key to deliver to the consumer ONCE.
                          MUST NOT be persisted or logged.
        prefix          — 12-char base36 string for storage in
                          tenant_api_keys.key_prefix (O(1) lookup).
        hashed_key_str  — bcrypt hash of the raw key, UTF-8 decoded. Store in
                          tenant_api_keys.api_key_hash.
    """
    prefix = "".join(secrets.choice(_ALPHABET_PREFIX) for _ in range(_PREFIX_LEN))
    secret = "".join(secrets.choice(_ALPHABET_SECRET) for _ in range(_SECRET_LEN))
    raw_key = f"{_SCHEME}{prefix}_{secret}"
    hashed = bcrypt.hashpw(raw_key.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
    return raw_key, prefix, hashed


def is_new_format(key: str) -> bool:
    """Return True iff `key` matches the canonical new-format regex."""
    if not isinstance(key, str):
        return False
    return bool(_NEW_FORMAT_RE.match(key))


def parse_prefix(key: str) -> str | None:
    """Return the 12-char prefix of a new-format key, else None.

    Never raises on malformed input — returns None. Safe for logging.
    """
    if not is_new_format(key):
        return None
    return key[len(_SCHEME) : len(_SCHEME) + _PREFIX_LEN]
