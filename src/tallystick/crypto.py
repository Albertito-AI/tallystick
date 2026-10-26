"""Recorder signatures and RFC 6962-style Merkle inclusion proofs.

These primitives authenticate a local recorder and an observed log representation.
They do not authenticate upstream sports facts, trusted time, or external witnesses.
"""
from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from typing import Any

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)


def canonical_json(value: Any) -> bytes:
    """Stable local JSON encoding; not a claim of RFC 8785 conformance."""
    def check(item: Any, depth: int = 0) -> None:
        if depth > 32:
            raise ValueError("JSON nesting exceeds 32 levels")
        if item is None or type(item) in (bool, int, str):
            if type(item) is int and abs(item) > 2**53 - 1:
                raise ValueError("JSON integer exceeds exact interoperable range")
            return
        if type(item) is float:
            if not math.isfinite(item):
                raise ValueError("JSON numbers must be finite")
            return
        if type(item) is list:
            for child in item:
                check(child, depth + 1)
            return
        if type(item) is dict:
            if any(type(key) is not str for key in item):
                raise ValueError("JSON object keys must be strings")
            for child in item.values():
                check(child, depth + 1)
            return
        raise ValueError("Unsupported JSON value")

    check(value)
    result = json.dumps(value, sort_keys=True, ensure_ascii=False,
                        allow_nan=False, separators=(",", ":")).encode("utf-8")
    if len(result) > 1024 * 1024:
        raise ValueError("Signed JSON exceeds 1 MiB")
    return result


@dataclass(frozen=True)
class SigningKey:
    """An Ed25519 local recorder key. Never export its seed in a report."""
    _key: Ed25519PrivateKey

    @classmethod
    def generate(cls) -> "SigningKey":
        return cls(Ed25519PrivateKey.generate())

    @classmethod
    def from_seed(cls, seed: bytes) -> "SigningKey":
        if type(seed) is not bytes or len(seed) != 32:
            raise ValueError("Ed25519 seeds must contain exactly 32 bytes")
        return cls(Ed25519PrivateKey.from_private_bytes(seed))

    @property
    def public_key_hex(self) -> str:
        return self._key.public_key().public_bytes(
            serialization.Encoding.Raw, serialization.PublicFormat.Raw).hex()

    def private_seed(self) -> bytes:
        """For owner-controlled local storage only, never an API response."""
        return self._key.private_bytes(serialization.Encoding.Raw,
                                      serialization.PrivateFormat.Raw,
                                      serialization.NoEncryption())

    def sign(self, payload: Any) -> str:
        return self._key.sign(canonical_json(payload)).hex()


def verify_signature(payload: Any, signature_hex: str,
                     trusted_public_key_hex: str) -> bool:
    try:
        if type(signature_hex) is not str or len(signature_hex) != 128:
            return False
        if type(trusted_public_key_hex) is not str or len(trusted_public_key_hex) != 64:
            return False
        key = Ed25519PublicKey.from_public_bytes(bytes.fromhex(trusted_public_key_hex))
        key.verify(bytes.fromhex(signature_hex), canonical_json(payload))
        return True
    except (InvalidSignature, ValueError, TypeError):
        return False


def _leaf_hash(leaf: bytes) -> bytes:
    return hashlib.sha256(b"\x00" + leaf).digest()


def _node_hash(left: bytes, right: bytes) -> bytes:
    return hashlib.sha256(b"\x01" + left + right).digest()


def _split(size: int) -> int:
    return 1 << ((size - 1).bit_length() - 1)


def _root(leaves: list[bytes]) -> bytes:
    if not leaves:
        return hashlib.sha256(b"").digest()
    if len(leaves) == 1:
        return _leaf_hash(leaves[0])
    split = _split(len(leaves))
    return _node_hash(_root(leaves[:split]), _root(leaves[split:]))


def merkle_root(leaves: list[bytes]) -> str:
    if type(leaves) is not list or any(type(item) is not bytes for item in leaves):
        raise ValueError("Merkle leaves must be byte strings")
    return _root(leaves).hex()


def inclusion_proof(leaves: list[bytes], index: int) -> dict:
    if type(index) is not int or not 0 <= index < len(leaves):
        raise ValueError("Invalid Merkle leaf index")
    if any(type(item) is not bytes for item in leaves):
        raise ValueError("Merkle leaves must be byte strings")

    def path(items: list[bytes], i: int) -> list[dict]:
        if len(items) == 1:
            return []
        split = _split(len(items))
        if i < split:
            return path(items[:split], i) + [{"side": "right", "hash": _root(items[split:]).hex()}]
        return path(items[split:], i - split) + [{"side": "left", "hash": _root(items[:split]).hex()}]

    return {"index": index, "tree_size": len(leaves), "audit_path": path(leaves, index)}


def _expected_sides(index: int, size: int) -> list[str]:
    if size == 1:
        return []
    split = _split(size)
    if index < split:
        return _expected_sides(index, split) + ["right"]
    return _expected_sides(index - split, size - split) + ["left"]


def verify_inclusion(leaf: bytes, proof: dict, root_hash: str) -> bool:
    try:
        if type(leaf) is not bytes or type(proof) is not dict:
            return False
        if set(proof) != {"index", "tree_size", "audit_path"}:
            return False
        index, size = proof["index"], proof["tree_size"]
        if type(index) is not int or type(size) is not int or not 0 <= index < size <= 1_000_000:
            return False
        path = proof["audit_path"]
        sides = _expected_sides(index, size)
        if type(path) is not list or len(path) != len(sides):
            return False
        digest = _leaf_hash(leaf)
        for item, side in zip(path, sides):
            if type(item) is not dict or set(item) != {"side", "hash"} or item["side"] != side:
                return False
            sibling = bytes.fromhex(item["hash"])
            if len(sibling) != 32:
                return False
            digest = _node_hash(sibling, digest) if side == "left" else _node_hash(digest, sibling)
        return len(root_hash) == 64 and digest.hex() == root_hash
    except (ValueError, TypeError, KeyError, RecursionError):
        return False


def verify_bundle(bundle: dict, trusted_public_key_hex: str) -> bool:
    """Verify an inclusion bundle against an independently obtained recorder key."""
    try:
        if type(bundle) is not dict or set(bundle) != {"entry", "proof", "checkpoint"}:
            return False
        checkpoint = bundle["checkpoint"]
        if type(checkpoint) is not dict or set(checkpoint) != {
                "domain", "log_id", "source_registry_hash", "tree_size", "root_hash",
                "recorded_at", "signature", "public_key"}:
            return False
        if type(checkpoint["tree_size"]) is not int or not 1 <= checkpoint["tree_size"] <= 1_000_000:
            return False
        signed = {key: value for key, value in checkpoint.items()
                  if key not in ("signature", "public_key")}
        if signed.get("domain") != "tallystick.checkpoint.v1":
            return False
        if checkpoint.get("public_key") != trusted_public_key_hex:
            return False
        if not verify_signature(signed, checkpoint["signature"], trusted_public_key_hex):
            return False
        entry = bundle["entry"]
        if type(entry) is not dict or set(entry) != {
                "domain", "log_id", "source_registry_hash", "sequence", "previous_hash",
                "recorded_at", "kind", "payload", "idempotency_key", "entry_hash", "signature"}:
            return False
        if type(entry["sequence"]) is not int or type(bundle["proof"]) is not dict:
            return False
        envelope = {key: value for key, value in entry.items()
                    if key not in ("signature", "entry_hash")}
        if envelope.get("domain") != "tallystick.entry.v1":
            return False
        if entry["log_id"] != checkpoint["log_id"]:
            return False
        if entry["source_registry_hash"] != checkpoint["source_registry_hash"]:
            return False
        if entry["sequence"] - 1 != bundle["proof"]["index"]:
            return False
        if bundle["proof"]["tree_size"] != checkpoint["tree_size"]:
            return False
        if hashlib.sha256(canonical_json(envelope)).hexdigest() != entry["entry_hash"]:
            return False
        if not verify_signature(envelope, entry["signature"], trusted_public_key_hex):
            return False
        return verify_inclusion(canonical_json(entry), bundle["proof"], checkpoint["root_hash"])
    except (KeyError, TypeError, ValueError, RecursionError):
        return False
