"""In-memory, integer-unit batch acceptance simulator for synthetic replay.

This module has no transport, account authentication, cash balances, live
wagering, or authority to place orders. Watermarks and mandates are trusted
test inputs. They are not verified declarations from external providers.
"""

from __future__ import annotations

import copy
import hashlib
import json
import re
from decimal import Decimal, InvalidOperation
from typing import Any

_ID = re.compile(r"[A-Za-z0-9_.:-]{1,80}\Z")
_DECIMAL = re.compile(r"[0-9]+(?:\.[0-9]{1,12})?\Z")
_MAX_TIME = 2**53 - 1
_MAX_UNITS = 10**12
_MAX_REQUESTS = 10_000


class GatewayError(ValueError):
    def __init__(self, message: str, code: str = "INVALID_GATEWAY_INPUT") -> None:
        super().__init__(message)
        self.code = code


def _integer(value: Any, name: str, low: int, high: int) -> int:
    if type(value) is not int or not low <= value <= high:
        raise GatewayError(f"{name} must be an integer between {low} and {high}")
    return value


def _identifier(value: Any, name: str) -> str:
    if not isinstance(value, str) or _ID.fullmatch(value) is None:
        raise GatewayError(f"{name} must be a short identifier")
    return value


def _object(value: Any, name: str, fields: set[str]) -> dict[str, Any]:
    if type(value) is not dict or set(value) != fields:
        raise GatewayError(f"{name} must contain exactly: {', '.join(sorted(fields))}")
    return copy.deepcopy(value)


def _odds(value: Any, name: str) -> Decimal:
    if not isinstance(value, str) or len(value) > 32 or _DECIMAL.fullmatch(value) is None:
        raise GatewayError(f"{name} must be a decimal string with at most 12 fractional places")
    try:
        number = Decimal(value)
    except InvalidOperation as exc:
        raise GatewayError(f"{name} is invalid") from exc
    if not number.is_finite() or not Decimal(1) <= number <= Decimal(10**9):
        raise GatewayError(f"{name} must be between 1 and 1000000000")
    return number


class BatchSimulator:
    """Reserve synthetic units, wait for declared watermarks, and close batches."""

    def __init__(
        self,
        window_ms: int = 250,
        required_sources: list[str] | tuple[str, ...] = ("demo-official",),
        max_market_units: int = 1000,
        max_family_units: int = 600,
    ) -> None:
        self.window_ms = _integer(window_ms, "window_ms", 1, 60_000)
        if not isinstance(required_sources, (list, tuple)) or not 1 <= len(required_sources) <= 16:
            raise GatewayError("required_sources must contain 1 to 16 identifiers")
        self.required_sources = tuple(_identifier(s, "source") for s in required_sources)
        if len(set(self.required_sources)) != len(self.required_sources):
            raise GatewayError("required_sources must be distinct")
        self.max_market_units = _integer(max_market_units, "max_market_units", 1, _MAX_UNITS)
        self.max_family_units = _integer(max_family_units, "max_family_units", 1, _MAX_UNITS)
        self._mandates: dict[str, dict[str, Any]] = {}
        self._requests: dict[str, dict[str, Any]] = {}
        self._watermarks: dict[str, int] = {}
        self._closed_batches: dict[int, dict[str, Any]] = {}
        self._market_units: dict[str, int] = {}
        self._family_units: dict[str, int] = {}
        self._mandate_units: dict[str, int] = {}
        self._clock_ms = 0
        self._closed_through = -1
        self._incidents: list[dict[str, Any]] = []
        self.halted = False

    def register_mandate(self, mandate: dict[str, Any]) -> dict[str, Any]:
        data = _object(mandate, "mandate", {
            "mandate_id", "agent_id", "model_family", "market_ids",
            "max_stake_units", "budget_units", "valid_from_ms", "valid_until_ms",
            "revoked", "consumer",
        })
        for name in ("mandate_id", "agent_id", "model_family"):
            _identifier(data[name], name)
        markets = data["market_ids"]
        if not isinstance(markets, list) or not 1 <= len(markets) <= 64:
            raise GatewayError("market_ids must contain 1 to 64 identifiers")
        for market in markets:
            _identifier(market, "market_id")
        if len(set(markets)) != len(markets):
            raise GatewayError("market_ids must be distinct")
        _integer(data["max_stake_units"], "max_stake_units", 1, _MAX_UNITS)
        _integer(data["budget_units"], "budget_units", 1, _MAX_UNITS)
        start = _integer(data["valid_from_ms"], "valid_from_ms", 0, _MAX_TIME)
        end = _integer(data["valid_until_ms"], "valid_until_ms", 1, _MAX_TIME)
        if start >= end:
            raise GatewayError("Mandate validity must have positive duration")
        if type(data["revoked"]) is not bool or type(data["consumer"]) is not bool:
            raise GatewayError("revoked and consumer must be booleans")
        if data["consumer"]:
            raise GatewayError("Consumer mandates are outside this simulator", "CONSUMER_UNSUPPORTED")
        mandate_id = data["mandate_id"]
        existing = self._mandates.get(mandate_id)
        if existing is not None:
            if existing != data:
                raise GatewayError("Mandate identifiers cannot be replaced or expanded", "MANDATE_CONFLICT")
            return copy.deepcopy(existing)
        if len(self._mandates) >= 1000:
            raise GatewayError("Mandate capacity reached", "CAPACITY_REACHED")
        self._mandates[mandate_id] = data
        return copy.deepcopy(data)

    def revoke(self, mandate_id: str) -> dict[str, Any]:
        _identifier(mandate_id, "mandate_id")
        if mandate_id not in self._mandates:
            raise GatewayError("Unknown mandate", "UNKNOWN_MANDATE")
        self._mandates[mandate_id]["revoked"] = True
        return {"mandate_id": mandate_id, "revoked": True}

    def _mandate_reason(self, mandate: dict[str, Any], market: str, units: int, at: int) -> str | None:
        if mandate["revoked"]:
            return "MANDATE_REVOKED"
        if not mandate["valid_from_ms"] <= at < mandate["valid_until_ms"]:
            return "MANDATE_NOT_CURRENT"
        if market not in mandate["market_ids"]:
            return "MARKET_NOT_PERMITTED"
        if units > mandate["max_stake_units"]:
            return "STAKE_LIMIT"
        return None

    def submit(self, intent: dict[str, Any], received_at_ms: int) -> dict[str, Any]:
        data = _object(intent, "intent", {
            "request_id", "market_id", "mandate_id", "stake_units", "min_decimal_odds",
        })
        for name in ("request_id", "market_id", "mandate_id"):
            _identifier(data[name], name)
        units = _integer(data["stake_units"], "stake_units", 1, _MAX_UNITS)
        _odds(data["min_decimal_odds"], "min_decimal_odds")
        at = _integer(received_at_ms, "received_at_ms", 0, _MAX_TIME - self.window_ms)
        request_id = data["request_id"]
        existing = self._requests.get(request_id)
        if existing is not None:
            if existing["intent"] != data or existing["received_at_ms"] != at:
                raise GatewayError("Request identifier was reused with different data", "IDEMPOTENCY_CONFLICT")
            return copy.deepcopy(existing["submission_receipt"])
        if at < self._clock_ms:
            raise GatewayError("Arrival time cannot move backwards", "NON_MONOTONIC_TIME")
        if len(self._requests) >= _MAX_REQUESTS:
            raise GatewayError("Request capacity reached", "CAPACITY_REACHED")
        self._clock_ms = at
        batch_end = (at // self.window_ms + 1) * self.window_ms
        mandate = self._mandates.get(data["mandate_id"])
        reason = "GLOBAL_HALT" if self.halted else None
        if reason is None and mandate is None:
            reason = "UNKNOWN_MANDATE"
        if reason is None and mandate is not None:
            reason = self._mandate_reason(mandate, data["market_id"], units, at)
            if reason is None and self._mandate_units.get(data["mandate_id"], 0) + units > mandate["budget_units"]:
                reason = "MANDATE_BUDGET"
            if reason is None and self._market_units.get(data["market_id"], 0) + units > self.max_market_units:
                reason = "MARKET_CAP"
            if reason is None and self._family_units.get(mandate["model_family"], 0) + units > self.max_family_units:
                reason = "FAMILY_CAP"
        status = "REJECTED" if reason else "QUEUED"
        receipt = {
            "receipt_type": "submission", "request_id": request_id,
            "status": status, "reason": reason, "batch_end_ms": batch_end,
            "received_at_ms": at, "units": units,
        }
        record = {"intent": data, "received_at_ms": at, "batch_end_ms": batch_end,
                  "submission_receipt": copy.deepcopy(receipt), "disposition": copy.deepcopy(receipt),
                  "reserved": reason is None}
        self._requests[request_id] = record
        if reason is None:
            self._mandate_units[data["mandate_id"]] = self._mandate_units.get(data["mandate_id"], 0) + units
            self._market_units[data["market_id"]] = self._market_units.get(data["market_id"], 0) + units
            family = mandate["model_family"]
            self._family_units[family] = self._family_units.get(family, 0) + units
        return copy.deepcopy(receipt)

    def advance_watermark(self, source_id: str, event_time_ms: int) -> dict[str, Any]:
        _identifier(source_id, "source_id")
        if source_id not in self.required_sources:
            raise GatewayError("Unknown source", "UNKNOWN_SOURCE")
        at = _integer(event_time_ms, "event_time_ms", 0, _MAX_TIME)
        if at < self._watermarks.get(source_id, -1):
            raise GatewayError("A declared source watermark cannot regress", "WATERMARK_REGRESSION")
        self._watermarks[source_id] = at
        return {"source_id": source_id, "watermark_ms": at, "trust": "synthetic caller declaration"}

    def _release(self, record: dict[str, Any]) -> None:
        if not record["reserved"]:
            return
        intent = record["intent"]
        units = intent["stake_units"]
        family = self._mandates[intent["mandate_id"]]["model_family"]
        self._mandate_units[intent["mandate_id"]] -= units
        self._market_units[intent["market_id"]] -= units
        self._family_units[family] -= units
        record["reserved"] = False

    def close_batch(self, end_ms: int, quotes: dict[str, str], now_ms: int) -> dict[str, Any]:
        end = _integer(end_ms, "end_ms", self.window_ms, _MAX_TIME)
        now = _integer(now_ms, "now_ms", 0, _MAX_TIME)
        if end % self.window_ms:
            raise GatewayError("end_ms must be a batch boundary")
        if type(quotes) is not dict or len(quotes) > 64:
            raise GatewayError("quotes must map at most 64 market identifiers to decimal strings")
        for market, value in quotes.items():
            _identifier(market, "quote market")
            _odds(value, "closing quote")
        closed = self._closed_batches.get(end)
        if closed is not None:
            if closed["quotes"] != quotes:
                raise GatewayError("A closed batch cannot be repriced", "BATCH_CONFLICT")
            return copy.deepcopy(closed)
        if now < self._clock_ms:
            raise GatewayError("Close time cannot move backwards", "NON_MONOTONIC_TIME")
        self._clock_ms = now
        result: dict[str, Any] = {"batch_end_ms": end, "now_ms": now, "status": "PENDING", "decisions": []}
        if self.halted:
            return {**result, "status": "HALTED", "reason": "LATE_FACT_INCIDENT"}
        if now < end:
            return {**result, "reason": "WINDOW_OPEN"}
        if end <= self._closed_through:
            raise GatewayError("A previous batch boundary cannot be closed again", "BATCH_ORDER")
        if len(self._closed_batches) >= _MAX_REQUESTS:
            raise GatewayError("Closed batch capacity reached", "CAPACITY_REACHED")
        if any(r["disposition"]["status"] == "QUEUED" and r["batch_end_ms"] < end for r in self._requests.values()):
            return {**result, "reason": "EARLIER_BATCH_PENDING"}
        missing = [source for source in self.required_sources if self._watermarks.get(source, -1) < end]
        if missing:
            return {**result, "reason": "SOURCE_WATERMARK_PENDING", "waiting_for_sources": missing}
        queued = [r for r in self._requests.values() if r["batch_end_ms"] == end and r["disposition"]["status"] == "QUEUED"]
        queued.sort(key=lambda r: (
            hashlib.sha256(json.dumps(
                [end, r["intent"]["request_id"], r["intent"]["market_id"]],
                separators=(",", ":"),
            ).encode()).digest(),
            r["intent"]["request_id"],
        ))
        decisions = []
        for record in queued:
            intent = record["intent"]
            mandate = self._mandates[intent["mandate_id"]]
            reason = self._mandate_reason(mandate, intent["market_id"], intent["stake_units"], now)
            quote = quotes.get(intent["market_id"])
            if reason is None and quote is None:
                reason = "MISSING_QUOTE"
            if reason is None and _odds(quote, "closing quote") < _odds(intent["min_decimal_odds"], "min_decimal_odds"):
                reason = "PRICE_LIMIT"
            decision = {
                "request_id": intent["request_id"], "market_id": intent["market_id"],
                "mandate_id": intent["mandate_id"], "status": "REJECTED" if reason else "ACCEPTED",
                "reason": reason, "units": intent["stake_units"],
                "decimal_odds": None if reason else quote, "accepted_at_ms": None if reason else now,
                "batch_end_ms": end,
            }
            if reason:
                self._release(record)
            record["disposition"] = decision
            decisions.append(copy.deepcopy(decision))
        complete = {**result, "status": "CLOSED", "decisions": decisions,
                    "quotes": copy.deepcopy(quotes), "watermarks": copy.deepcopy(self._watermarks),
                    "ordering": "deterministic hash for replay; not unpredictability or fairness proof"}
        self._closed_batches[end] = copy.deepcopy(complete)
        self._closed_through = end
        return complete

    def observe_late(self, source_id: str, event_time_ms: int) -> dict[str, Any]:
        _identifier(source_id, "source_id")
        if source_id not in self.required_sources:
            raise GatewayError("Unknown source", "UNKNOWN_SOURCE")
        at = _integer(event_time_ms, "event_time_ms", 0, _MAX_TIME)
        if len(self._incidents) >= 1000:
            raise GatewayError("Incident capacity reached", "CAPACITY_REACHED")
        affects_closed = at <= self._closed_through
        incident = {"source_id": source_id, "event_time_ms": at,
                    "closed_through_ms": self._closed_through,
                    "status": "HALTED" if affects_closed else "RECORDED",
                    "reason": "LATE_FACT_AFTER_CLOSE" if affects_closed else "NO_CLOSED_BATCH_AFFECTED",
                    "action": "manual correction review; accepted records preserved" if affects_closed else "inspect pending replay inputs"}
        if affects_closed:
            self.halted = True
        self._incidents.append(copy.deepcopy(incident))
        return incident

    def get_request(self, request_id: str) -> dict[str, Any]:
        _identifier(request_id, "request_id")
        if request_id not in self._requests:
            raise GatewayError("Unknown request", "UNKNOWN_REQUEST")
        return copy.deepcopy(self._requests[request_id]["disposition"])

    def exposure(self) -> dict[str, Any]:
        """Cumulative accepted plus pending reserved units within this process."""
        return {"market_units": copy.deepcopy(self._market_units),
                "family_units": copy.deepcopy(self._family_units),
                "mandate_units": copy.deepcopy(self._mandate_units),
                "halted": self.halted, "scope": "pending plus accepted synthetic units; no cash or cross-operator registry"}
