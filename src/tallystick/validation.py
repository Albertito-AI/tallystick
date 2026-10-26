"""Bounded JSON and explicit data validation. Input never becomes executable code."""
from __future__ import annotations

import json
import math
import re
from datetime import datetime, timezone
from typing import Any

MAX_JSON_BYTES = 1_048_576
TOKEN = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:/-]{0,127}\Z")
UTC_TIME = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?Z\Z", re.ASCII)


class InputError(ValueError):
    def __init__(self, message: str, code: str = "INVALID_INPUT"):
        super().__init__(message)
        self.code = code


def require(condition: bool, message: str, code: str = "INVALID_INPUT") -> None:
    if not condition:
        raise InputError(message, code)


def exact_keys(value: Any, required: set[str], optional: set[str] | None = None) -> None:
    require(type(value) is dict, "An object is required")
    require(required <= value.keys(), f"Missing fields: {sorted(required - value.keys())}")
    require(value.keys() <= required | (optional or set()), "Unknown fields are not permitted")


def token(value: Any, field: str) -> str:
    require(type(value) is str and TOKEN.fullmatch(value) is not None, f"Invalid {field}")
    return value


def integer(value: Any, field: str, minimum: int, maximum: int) -> int:
    require(type(value) is int and minimum <= value <= maximum,
            f"{field} must be an integer in [{minimum}, {maximum}]")
    return value


def utc(value: Any) -> datetime:
    require(type(value) is str and UTC_TIME.fullmatch(value) is not None,
            "Time must be a calendar UTC timestamp ending in Z, with at most six fractional digits")
    try:
        parsed = datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as error:
        raise InputError("Invalid timestamp") from error
    require(parsed.tzinfo == timezone.utc, "UTC is required")
    return parsed


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def loads(text: str | bytes, limit: int = MAX_JSON_BYTES) -> Any:
    try:
        raw = text.encode("utf-8") if type(text) is str else text
    except UnicodeError as error:
        raise InputError("JSON input contains invalid Unicode") from error
    require(type(raw) is bytes and len(raw) <= limit, "JSON input exceeds the byte limit")

    def pairs(items):
        out = {}
        for key, value in items:
            require(key not in out, "Duplicate JSON keys are not permitted")
            out[key] = value
        return out

    def constant(value):
        raise InputError(f"Non-finite JSON number: {value}")

    try:
        result = json.loads(raw, object_pairs_hook=pairs, parse_constant=constant)
    except (UnicodeError, ValueError, RecursionError) as error:
        raise InputError("Invalid or excessively nested JSON") from error
    stack = [(result, 0)]
    count = 0
    while stack:
        value, depth = stack.pop()
        count += 1
        require(depth <= 32 and count <= 100_000, "JSON structure exceeds limits")
        if type(value) is dict:
            stack.extend((key, depth + 1) for key in value)
            stack.extend((v, depth + 1) for v in value.values())
        elif type(value) is list:
            stack.extend((v, depth + 1) for v in value)
        elif type(value) is float:
            require(math.isfinite(value), "Non-finite JSON numbers are not permitted")
        elif type(value) is int:
            require(abs(value) <= 2 ** 53 - 1, "JSON integer exceeds the interoperable range")
        elif type(value) is str:
            try:
                value.encode("utf-8")
            except UnicodeError as error:
                raise InputError("JSON strings must contain valid Unicode") from error
    return result
