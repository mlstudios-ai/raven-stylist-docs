"""Attribute key → source file + JSON path mapping.

Callers reference attributes by user-facing keys (e.g. ``"identity"``,
``"style_dna"``). The internal layout — which file holds the data and what
the JSON key is called inside that file — is hidden behind this table so it
can change without breaking the API contract.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class Source(str, Enum):
    PROFILE = "profile"
    PERSONA = "persona"
    PHOTOS = "photos"


@dataclass(frozen=True)
class AttributeSpec:
    key: str
    source: Source
    json_path: str | None
    description: str
    always_on: bool = False


ATTRIBUTES: dict[str, AttributeSpec] = {
    spec.key: spec
    for spec in [
        AttributeSpec("photos", Source.PHOTOS, None,
                      "Photo observations list. Profile photo always included.",
                      always_on=True),
    ]
}


def all_keys() -> list[str]:
    return list(ATTRIBUTES.keys())


def always_on_keys() -> list[str]:
    return [k for k, spec in ATTRIBUTES.items() if spec.always_on]


def resolve(requested: list[str] | None) -> list[str]:
    """Resolve the caller-supplied attribute list into a final list of keys.

    - ``None`` or empty → minimum (always-on keys only).
    - ``["all"]`` → every key.
    - Otherwise → always-on keys ∪ requested keys.

    Raises ``KeyError`` (caller maps to 400) if any requested key is unknown.
    """
    if not requested:
        return always_on_keys()
    if requested == ["all"]:
        return all_keys()
    unknown = [k for k in requested if k not in ATTRIBUTES]
    if unknown:
        raise KeyError(unknown)
    return list(dict.fromkeys(always_on_keys() + requested))
