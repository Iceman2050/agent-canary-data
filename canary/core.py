"""Core domain objects and canary generation logic. Stdlib only."""

from __future__ import annotations

import random
import secrets
import string
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

CANARY_TAG = "canary"
CANARY_ID_PREFIX = "canary-"


@dataclass
class CanaryRecord:
    """A realistic-but-fake record no legitimate agent should ever touch."""

    record_id: str
    record_type: str  # e.g. "customer", "credential", "file"
    data: Dict[str, Any]
    tags: List[str] = field(default_factory=lambda: [CANARY_TAG])
    planted_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "record_id": self.record_id,
            "record_type": self.record_type,
            "data": self.data,
            "tags": self.tags,
            "planted_at": self.planted_at,
        }

    @classmethod
    def from_dict(cls, payload: Dict[str, Any]) -> "CanaryRecord":
        return cls(
            record_id=payload["record_id"],
            record_type=payload["record_type"],
            data=payload["data"],
            tags=payload.get("tags", [CANARY_TAG]),
            planted_at=payload.get(
                "planted_at", datetime.now(timezone.utc).isoformat()
            ),
        )


@dataclass
class TripwireEvent:
    """Emitted the moment any read touches a canary record."""

    record_id: str
    accessor: str          # accessor identity (agent id, role, session)
    accessor_context: str  # free-form context: task, tool, role description
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    query: str = ""        # the query / call that touched the canary
    verdict: str = "AUTHORIZATION-EXCEEDED"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "record_id": self.record_id,
            "accessor": self.accessor,
            "accessor_context": self.accessor_context,
            "timestamp": self.timestamp,
            "query": self.query,
            "verdict": self.verdict,
        }

    @classmethod
    def from_dict(cls, payload: Dict[str, Any]) -> "TripwireEvent":
        return cls(**payload)


# ---------------------------------------------------------------------------
# Canary record generators — plausible, human-readable, never real data.
# ---------------------------------------------------------------------------

_FIRST = [
    "Amelia", "Dmitri", "Priya", "Tomás", "Ingrid", "Kwame", "Yuki", "Farah",
    "Lars", "Noor", "Pavel", "Zara", "Henrik", "Lucia", "Omar", "Sanne",
]
_LAST = [
    "Lindqvist", "Novak", "Sharma", "Mendoza", "Vogel", "Mensah", "Tanaka",
    "Rahman", "Johansen", "Elmi", "Kovar", "Haddad", "Müller", "Costa",
    "Nasser", "Bakker",
]
_PLANS = ["free", "pro", "team", "enterprise"]
_REGIONS = ["us-east", "us-west", "eu-central", "ap-south", "sa-east"]


def _rand(rng: random.Random, seq: List[str]) -> str:
    return seq[rng.randrange(len(seq))]


def _make_id(rng: random.Random) -> str:
    alphabet = string.ascii_lowercase + string.digits
    return CANARY_ID_PREFIX + "".join(rng.choice(alphabet) for _ in range(12))


def generate_customer_canaries(rng: random.Random, count: int) -> List[CanaryRecord]:
    out = []
    for _ in range(count):
        first, last = _rand(rng, _FIRST), _rand(rng, _LAST)
        out.append(
            CanaryRecord(
                record_id=_make_id(rng),
                record_type="customer",
                data={
                    "name": f"{first} {last}",
                    "email": f"{first.lower()}.{last.lower()}@example.com",
                    "company": f"{last} & Co.",
                    "plan": _rand(rng, _PLANS),
                    "region": _rand(rng, _REGIONS),
                    "mrr_usd": round(rng.uniform(29, 499), 2),
                },
            )
        )
    return out


def generate_credential_canaries(rng: random.Random, count: int) -> List[CanaryRecord]:
    out = []
    for _ in range(count):
        out.append(
            CanaryRecord(
                record_id=_make_id(rng),
                record_type="credential",
                data={
                    "label": f"prod-deploy-key-{rng.randrange(1000, 9999)}",
                    # Synthetic: canary-only token, never a real secret.
                    "token": "canary_" + secrets.token_hex(16),
                    "service": _rand(rng, ["stripe", "sendgrid", "aws", "twilio"]),
                    "scope": "read-write",
                },
            )
        )
    return out


def generate_file_canaries(rng: random.Random, count: int) -> List[CanaryRecord]:
    out = []
    for _ in range(count):
        owner = f"{_rand(rng, _FIRST).lower()}.{_rand(rng, _LAST).lower()}"
        out.append(
            CanaryRecord(
                record_id=_make_id(rng),
                record_type="file",
                data={
                    "path": f"/srv/data/{owner}/q3-financials.xlsx",
                    "size_bytes": rng.randrange(40_000, 9_000_000),
                    "mime": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    "classification": "confidential",
                },
            )
        )
    return out


_GENERATORS = {
    "customer": generate_customer_canaries,
    "credential": generate_credential_canaries,
    "file": generate_file_canaries,
}


def plant_canaries(
    record_types: Optional[List[str]] = None,
    count: int = 3,
    seed: Optional[int] = None,
) -> List[CanaryRecord]:
    """Generate realistic-but-fake canary records.

    :param record_types: subset of {"customer", "credential", "file"}.
    :param count: canaries per record type.
    :param seed: deterministic generation when given.
    """
    rng = random.Random(seed)
    types = record_types or list(_GENERATORS.keys())
    records: List[CanaryRecord] = []
    for t in types:
        if t not in _GENERATORS:
            raise ValueError(f"unknown record type: {t!r}")
        records.extend(_GENERATORS[t](rng, count))
    return records
