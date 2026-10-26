"""A local SQLite recorder with signed append-only entries and receipt proofs."""
from __future__ import annotations

import hashlib
import json
import sqlite3
import threading
from pathlib import Path
from typing import Any

from .crypto import (SigningKey, canonical_json, inclusion_proof, merkle_root,
                     verify_signature)
from .settlement import (STATES, active_snapshot, parse_time, utc_now,
                         validate_fact_shape, validate_revision)


class LedgerError(ValueError):
    def __init__(self, message: str, code: str = "INVALID_FACT") -> None:
        super().__init__(message)
        self.code = code


class Ledger:
    """Record authorised input supplied by a trusted local operator.

    A registry's source roles are operator configuration, not remotely verified
    supplier credentials. SQLite triggers prevent accidental UPDATE/DELETE of
    entries; an owner with filesystem access can replace the database. Preserve
    externally pinned checkpoints when an audit requires detection of rewriting.
    """

    def __init__(self, path: str | Path, signer: SigningKey, sources: dict,
                 log_id: str = "tallystick-local") -> None:
        if not isinstance(signer, SigningKey):
            raise ValueError("A local signing key is required")
        if type(log_id) is not str or not 1 <= len(log_id) <= 160:
            raise ValueError("Invalid log identifier")
        if type(sources) is not dict or len(sources) > 1000:
            raise ValueError("Sources must be a bounded registry")
        for source_id, entry in sources.items():
            if type(source_id) is not str or not source_id or type(entry) is not dict:
                raise ValueError("Invalid source registry entry")
            if type(entry.get("independence_group")) is not str or not entry["independence_group"]:
                raise ValueError("Every source requires an independence group")
            if type(entry.get("official_kinds")) is not list or any(
                    type(kind) is not str for kind in entry["official_kinds"]):
                raise ValueError("Every source requires an official_kinds list")
        self.signer = signer
        self.sources = json.loads(canonical_json(sources))
        self.log_id = log_id
        self.registry_hash = hashlib.sha256(canonical_json(self.sources)).hexdigest()
        self._lock = threading.RLock()
        self._conn = sqlite3.connect(str(path), timeout=5, isolation_level=None,
                                     check_same_thread=False)
        self._conn.execute("PRAGMA foreign_keys = ON")
        self._conn.execute("PRAGMA journal_mode = WAL")
        self._conn.executescript("""
            CREATE TABLE IF NOT EXISTS metadata(key TEXT PRIMARY KEY, value TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS entries(
                sequence INTEGER PRIMARY KEY,
                body TEXT NOT NULL,
                entry_hash TEXT NOT NULL UNIQUE
            );
            CREATE TABLE IF NOT EXISTS requests(
                idempotency_key TEXT PRIMARY KEY,
                request_hash TEXT NOT NULL,
                sequence INTEGER NOT NULL REFERENCES entries(sequence)
            );
            CREATE TABLE IF NOT EXISTS heads(
                observation_id TEXT PRIMARY KEY,
                fact_id TEXT NOT NULL UNIQUE,
                sequence INTEGER NOT NULL REFERENCES entries(sequence)
            );
            CREATE TRIGGER IF NOT EXISTS no_entry_update BEFORE UPDATE ON entries
                BEGIN SELECT RAISE(ABORT, 'entries are append-only'); END;
            CREATE TRIGGER IF NOT EXISTS no_entry_delete BEFORE DELETE ON entries
                BEGIN SELECT RAISE(ABORT, 'entries are append-only'); END;
        """)
        expected = {"schema_version": "0.1", "log_id": log_id,
                    "public_key": signer.public_key_hex,
                    "source_registry_hash": self.registry_hash}
        with self._lock:
            self._conn.execute("BEGIN IMMEDIATE")
            try:
                saved = dict(self._conn.execute("SELECT key,value FROM metadata"))
                if saved and saved != expected:
                    raise LedgerError("Recorder key, registry or log identity does not match database",
                                      "LOG_IDENTITY_MISMATCH")
                if not saved:
                    self._conn.executemany("INSERT INTO metadata(key,value) VALUES(?,?)", expected.items())
                self._conn.execute("COMMIT")
            except Exception:
                self._conn.execute("ROLLBACK")
                self._conn.close()
                raise

    def __enter__(self) -> "Ledger":
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()

    def close(self) -> None:
        with self._lock:
            self._conn.close()

    def _check_source_state(self, fact: dict) -> None:
        unknown = [source for source in fact["source_ids"] if source not in self.sources]
        if unknown:
            raise LedgerError("Fact references an unknown source", "UNKNOWN_SOURCE")
        groups = {self.sources[source]["independence_group"] for source in fact["source_ids"]}
        if fact["state"] == "corroborated" and len(groups) < 2:
            raise LedgerError("Corroboration requires two configured independent groups", "SOURCE_AUTHORITY")
        if STATES[fact["state"]] >= STATES["official"] and not any(
                fact["kind"] in self.sources[source]["official_kinds"] for source in fact["source_ids"]):
            raise LedgerError("No designated official source supports this fact kind", "SOURCE_AUTHORITY")

    def append_fact(self, fact: dict, idempotency_key: str,
                    recorded_at: str | None = None) -> dict:
        return self._append("fact", fact, idempotency_key, recorded_at)

    def append(self, kind: str, payload: Any, idempotency_key: str,
               recorded_at: str | None = None) -> dict:
        if kind == "fact":
            raise LedgerError("Facts must use append_fact", "INVALID_ENTRY_KIND")
        return self._append(kind, payload, idempotency_key, recorded_at)

    def _append(self, kind: str, payload: Any, idempotency_key: str,
                recorded_at: str | None) -> dict:
        if type(kind) is not str or not 1 <= len(kind) <= 80 or any(ord(c) < 33 for c in kind):
            raise LedgerError("Invalid entry kind", "INVALID_ENTRY_KIND")
        if type(idempotency_key) is not str or not 1 <= len(idempotency_key) <= 200:
            raise LedgerError("Invalid idempotency key", "INVALID_IDEMPOTENCY_KEY")
        try:
            payload = json.loads(canonical_json(payload))
            request_hash = hashlib.sha256(canonical_json({"kind": kind, "payload": payload})).hexdigest()
        except (ValueError, UnicodeError) as exc:
            raise LedgerError(str(exc), "INVALID_PAYLOAD") from exc
        with self._lock:
            self._conn.execute("BEGIN IMMEDIATE")
            try:
                prior = self._conn.execute(
                    "SELECT request_hash,sequence FROM requests WHERE idempotency_key=?",
                    (idempotency_key,)).fetchone()
                if prior:
                    if prior[0] != request_hash:
                        raise LedgerError("Idempotency key was already used for different content",
                                          "IDEMPOTENCY_CONFLICT")
                    entry = json.loads(self._conn.execute(
                        "SELECT body FROM entries WHERE sequence=?", (prior[1],)).fetchone()[0])
                    self._conn.execute("COMMIT")
                    return entry
                timestamp = recorded_at if recorded_at is not None else utc_now()
                try:
                    recorded = parse_time(timestamp)
                    if kind == "fact":
                        validate_fact_shape(payload)
                        if parse_time(payload["received_at"]) > recorded:
                            raise ValueError("Receipt cannot follow recorder time")
                        self._check_source_state(payload)
                        row = self._conn.execute(
                            "SELECT e.body FROM heads h JOIN entries e ON e.sequence=h.sequence "
                            "WHERE h.observation_id=?", (payload["observation_id"],)).fetchone()
                        previous = json.loads(row[0])["payload"] if row else None
                        validate_revision(payload, previous)
                        if previous is not None and payload["value"] != previous["value"] and recorded >= parse_time(previous["correction_deadline"]):
                            raise ValueError("Recorder observed this correction after its window closed")
                        if self._conn.execute(
                            "SELECT 1 FROM entries WHERE json_extract(body,'$.kind')='fact' "
                            "AND json_extract(body,'$.payload.fact_id')=?", (payload["fact_id"],)).fetchone():
                            raise ValueError("Fact identifier already exists")
                except (ValueError, TypeError, KeyError) as exc:
                    if isinstance(exc, LedgerError):
                        raise
                    raise LedgerError(str(exc)) from exc
                last = self._conn.execute("SELECT sequence,body,entry_hash FROM entries ORDER BY sequence DESC LIMIT 1").fetchone()
                sequence = last[0] + 1 if last else 1
                previous_hash = last[2] if last else "0" * 64
                if last and recorded < parse_time(json.loads(last[1])["recorded_at"]):
                    raise LedgerError("Recorder time cannot move backwards", "TIME_ORDER")
                envelope = {"domain": "tallystick.entry.v1", "log_id": self.log_id,
                            "source_registry_hash": self.registry_hash, "sequence": sequence,
                            "previous_hash": previous_hash, "recorded_at": timestamp,
                            "kind": kind, "payload": payload, "idempotency_key": idempotency_key}
                entry = dict(envelope, entry_hash=hashlib.sha256(canonical_json(envelope)).hexdigest(),
                             signature=self.signer.sign(envelope))
                encoded = canonical_json(entry).decode("utf-8")
                self._conn.execute("INSERT INTO entries(sequence,body,entry_hash) VALUES(?,?,?)",
                                   (sequence, encoded, entry["entry_hash"]))
                self._conn.execute("INSERT INTO requests(idempotency_key,request_hash,sequence) VALUES(?,?,?)",
                                   (idempotency_key, request_hash, sequence))
                if kind == "fact":
                    self._conn.execute(
                        "INSERT INTO heads(observation_id,fact_id,sequence) VALUES(?,?,?) "
                        "ON CONFLICT(observation_id) DO UPDATE SET fact_id=excluded.fact_id,sequence=excluded.sequence",
                        (payload["observation_id"], payload["fact_id"], sequence))
                self._conn.execute("COMMIT")
                return entry
            except Exception:
                self._conn.execute("ROLLBACK")
                raise

    def entries(self) -> list[dict]:
        with self._lock:
            return [json.loads(row[0]) for row in self._conn.execute("SELECT body FROM entries ORDER BY sequence")]

    def facts(self) -> list[dict]:
        return [entry["payload"] for entry in self.entries() if entry["kind"] == "fact"]

    def active_facts(self, event_id: str | None = None) -> list[dict]:
        result = active_snapshot(self.facts())
        return result if event_id is None else [fact for fact in result if fact["event_id"] == event_id]

    def _checkpoint_for(self, entries: list[dict]) -> dict:
        content = {"domain": "tallystick.checkpoint.v1", "log_id": self.log_id,
                   "source_registry_hash": self.registry_hash, "tree_size": len(entries),
                   "root_hash": merkle_root([canonical_json(entry) for entry in entries]),
                   "recorded_at": entries[-1]["recorded_at"] if entries else None}
        return dict(content, signature=self.signer.sign(content), public_key=self.signer.public_key_hex)

    def checkpoint(self) -> dict:
        with self._lock:
            return self._checkpoint_for(self.entries())

    def inclusion_proof(self, sequence: int) -> dict:
        with self._lock:
            entries = self.entries()
            if type(sequence) is not int or not 1 <= sequence <= len(entries):
                raise LedgerError("Entry sequence is not in this log", "ENTRY_NOT_FOUND")
            leaves = [canonical_json(entry) for entry in entries]
            return {"entry": entries[sequence - 1], "proof": inclusion_proof(leaves, sequence - 1),
                    "checkpoint": self._checkpoint_for(entries)}

    def verify(self, trusted_public_key_hex: str) -> dict:
        """Audit current entries and derived idempotency/head records with a pinned key."""
        errors: list[str] = []
        with self._lock:
            try:
                entries = self.entries()
                if trusted_public_key_hex != self.signer.public_key_hex:
                    errors.append("trusted_key_mismatch")
                previous_hash, previous_time = "0" * 64, None
                facts = []
                expected_heads = {}
                expected_facts = {}
                expected_requests = {}
                for expected_sequence, entry in enumerate(entries, 1):
                    if type(entry) is not dict or set(entry) != {
                            "domain", "log_id", "source_registry_hash", "sequence", "previous_hash",
                            "recorded_at", "kind", "payload", "idempotency_key", "entry_hash", "signature"}:
                        raise ValueError("Malformed entry fields")
                    envelope = {key: value for key, value in entry.items()
                                if key not in ("entry_hash", "signature")}
                    if type(entry["sequence"]) is not int or entry["sequence"] != expected_sequence or entry["previous_hash"] != previous_hash:
                        errors.append(f"chain:{expected_sequence}")
                    if entry.get("domain") != "tallystick.entry.v1" or entry["log_id"] != self.log_id:
                        errors.append(f"identity:{expected_sequence}")
                    if entry["source_registry_hash"] != self.registry_hash:
                        errors.append(f"registry:{expected_sequence}")
                    if hashlib.sha256(canonical_json(envelope)).hexdigest() != entry["entry_hash"]:
                        errors.append(f"hash:{expected_sequence}")
                    if not verify_signature(envelope, entry["signature"], trusted_public_key_hex):
                        errors.append(f"signature:{expected_sequence}")
                    timestamp = parse_time(entry["recorded_at"])
                    if previous_time is not None and timestamp < previous_time:
                        errors.append(f"time:{expected_sequence}")
                    previous_time, previous_hash = timestamp, entry["entry_hash"]
                    request_hash = hashlib.sha256(canonical_json(
                        {"kind": entry["kind"], "payload": entry["payload"]})).hexdigest()
                    if entry["idempotency_key"] in expected_requests:
                        errors.append(f"duplicate_request:{expected_sequence}")
                    expected_requests[entry["idempotency_key"]] = (request_hash, expected_sequence)
                    if entry["kind"] == "fact":
                        fact = entry["payload"]
                        validate_fact_shape(fact)
                        self._check_source_state(fact)
                        if parse_time(fact["received_at"]) > timestamp:
                            errors.append(f"receipt_time:{expected_sequence}")
                        prior = expected_facts.get(fact["observation_id"])
                        if prior is not None and prior["value"] != fact["value"] and timestamp >= parse_time(prior["correction_deadline"]):
                            errors.append(f"correction_time:{expected_sequence}")
                        expected_facts[fact["observation_id"]] = fact
                        facts.append(fact)
                        expected_heads[fact["observation_id"]] = (fact["fact_id"], expected_sequence)
                active_snapshot(facts)
                actual_heads = {row[0]: (row[1], row[2]) for row in self._conn.execute(
                    "SELECT observation_id,fact_id,sequence FROM heads")}
                actual_requests = {row[0]: (row[1], row[2]) for row in self._conn.execute(
                    "SELECT idempotency_key,request_hash,sequence FROM requests")}
                if actual_heads != expected_heads:
                    errors.append("derived_heads_mismatch")
                if actual_requests != expected_requests:
                    errors.append("idempotency_records_mismatch")
                rows = list(self._conn.execute("SELECT sequence,entry_hash FROM entries ORDER BY sequence"))
                if rows != [(entry["sequence"], entry["entry_hash"]) for entry in entries]:
                    errors.append("stored_entry_index_mismatch")
                return {"valid": not errors, "errors": errors, "entries": len(entries),
                        "root_hash": merkle_root([canonical_json(entry) for entry in entries])}
            except (ValueError, TypeError, KeyError, sqlite3.DatabaseError) as exc:
                return {"valid": False, "errors": errors + [f"malformed_log:{type(exc).__name__}"],
                        "entries": None, "root_hash": None}
