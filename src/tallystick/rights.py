"""Checks declared fixture permissions. This does not authenticate a legal licence."""
from __future__ import annotations

from copy import deepcopy
from .validation import exact_keys, token, utc, require

USES = {"display", "pricing", "settlement", "redistribution", "training"}
FACT_TYPES = {"corner.awarded", "goal.scored", "period.closed", "event.abandoned"}


class RightsRegistry:
    def __init__(self, licences: list[dict], sources: dict):
        require(type(licences) is list and 0 < len(licences) <= 128, "Invalid licence registry")
        require(type(sources) is dict and 0 < len(sources) <= 1000, "Invalid source registry")
        for source_id, source in sources.items():
            token(source_id, "source_id")
            exact_keys(source, {"independence_group", "official_kinds"})
            token(source["independence_group"], "independence_group")
            kinds = source["official_kinds"]
            require(type(kinds) is list and len(kinds) <= len(FACT_TYPES), "Invalid official fact kinds")
            for kind in kinds:
                token(kind, "official_kind")
            require(len(set(kinds)) == len(kinds) and set(kinds) <= FACT_TYPES,
                    "Unknown or duplicate official fact kind")
        self.sources = deepcopy(sources)
        self.licences = {}
        for licence in licences:
            exact_keys(licence, {"schema_version", "licence_id", "source_ids", "uses",
                       "territories", "valid_from", "valid_until", "fact_types", "synthetic"})
            require(licence["schema_version"] == "0.1", "Unknown licence schema")
            lid = token(licence["licence_id"], "licence_id")
            require(lid not in self.licences, "Duplicate licence")
            for field in ("source_ids", "uses", "territories", "fact_types"):
                values = licence[field]
                require(type(values) is list and 0 < len(values) <= 128, f"Invalid {field}")
                for value in values:
                    token(value, field)
                require(len(values) == len(set(values)), f"Duplicate {field}")
            require(set(licence["source_ids"]) <= self.sources.keys(), "Unknown licensed source")
            require(set(licence["uses"]) <= USES, "Unknown licensed use")
            require(set(licence["fact_types"]) <= FACT_TYPES, "Unknown licensed fact type")
            require(utc(licence["valid_from"]) < utc(licence["valid_until"]), "Invalid licence dates")
            require(licence["synthetic"] is True, "Only synthetic licences are supported", "LIVE_DATA_DISABLED")
            self.licences[lid] = deepcopy(licence)

    def check(self, licence_id: str, use: str, territory: str, fact_type: str,
              source_ids: list[str], as_of: str) -> dict:
        for field, value in (("licence_id", licence_id), ("use", use),
                             ("territory", territory), ("fact_type", fact_type)):
            token(value, field)
        require(use in USES and fact_type in FACT_TYPES, "Unknown permission use or fact type")
        require(type(source_ids) is list and len(source_ids) <= 128, "Invalid source identifiers")
        for source_id in source_ids:
            token(source_id, "source_id")
        require(len(set(source_ids)) == len(source_ids), "Duplicate source identifiers")
        when = utc(as_of)
        licence = self.licences.get(licence_id)
        reasons = []
        if licence is None:
            reasons.append("UNKNOWN_LICENCE")
        else:
            if use not in licence["uses"]:
                reasons.append("USE_NOT_GRANTED")
            if territory not in licence["territories"]:
                reasons.append("TERRITORY_NOT_GRANTED")
            if fact_type not in licence["fact_types"]:
                reasons.append("FACT_TYPE_NOT_GRANTED")
            if not source_ids or not set(source_ids) <= set(licence["source_ids"]):
                reasons.append("SOURCE_NOT_LICENSED")
            if not utc(licence["valid_from"]) <= when < utc(licence["valid_until"]):
                reasons.append("LICENCE_NOT_CURRENT")
        return {"allowed": not reasons, "reasons": reasons, "licence_id": licence_id,
                "use": use, "territory": territory, "checked_at": as_of,
                "basis": "declared synthetic permissions"}

    def require(self, **kwargs) -> dict:
        result = self.check(**kwargs)
        require(result["allowed"], ", ".join(result["reasons"]), "RIGHTS_DENIED")
        return result
