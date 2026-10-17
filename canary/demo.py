"""Mock datastore + mock agent with two modes: clean and snooping."""

from __future__ import annotations

import random
from typing import Dict, List, Optional

from .adapters import DatastoreAdapter, MonitoredStore
from .core import CanaryRecord, TripwireEvent, plant_canaries


class MockDatastore(DatastoreAdapter):
    """In-memory datastore with both real and canary records."""

    def __init__(self, n_real: int = 20, seed: int = 42):
        self._records: Dict[str, Dict] = {}
        self._canaries = set()
        rng = random.Random(seed)
        for i in range(n_real):
            rid = f"real-customer-{i:04d}"
            self._records[rid] = {
                "record_id": rid,
                "record_type": "customer",
                "data": {
                    "name": f"Real User {i}",
                    "email": f"user{i}@example.com",
                    "plan": rng.choice(["free", "pro", "team"]),
                },
                "tags": ["real"],
            }

    def write_record(self, record: CanaryRecord) -> None:
        self._records[record.record_id] = record.to_dict()
        self._canaries.add(record.record_id)

    def read_record(self, record_id: str, accessor: str,
                    accessor_context: str = "", query: str = "") -> Optional[Dict]:
        return self._records.get(record_id)

    def list_records(self, accessor: str, accessor_context: str = "",
                     query: str = "") -> List[Dict]:
        return list(self._records.values())

    def canary_ids(self) -> set:
        return set(self._canaries)


class MockAgent:
    """Simulates an agent doing a scoped task against the datastore.

    mode="clean": only touches real records in its task scope. Trips nothing.
    mode="snooping": reads beyond its task — touches canaries. Trips tripwires.
    """

    def __init__(self, store: MonitoredStore, agent_id: str, mode: str = "clean"):
        if mode not in ("clean", "snooping"):
            raise ValueError("mode must be 'clean' or 'snooping'")
        self.store = store
        self.agent_id = agent_id
        self.mode = mode

    def run_task(self, task: str) -> List[TripwireEvent]:
        context = f"task={task!r} mode={self.mode}"
        if self.mode == "clean":
            # Only reads records explicitly in scope: first 3 real customers.
            for i in range(3):
                self.store.read_record(
                    f"real-customer-{i:04d}",
                    accessor=self.agent_id,
                    accessor_context=context,
                    query=f"get_customer(i={i})",
                )
        else:
            # Snooping: lists EVERYTHING, touching canaries along the way.
            self.store.list_records(
                accessor=self.agent_id,
                accessor_context=context,
                query="SELECT * FROM customers (unscoped dump)",
            )
        return self.store.events()


def build_demo_store(seed: int = 42) -> MonitoredStore:
    """Mock datastore with planted canaries, wrapped in the watch layer."""
    adapter = MockDatastore(seed=seed)
    for record in plant_canaries(count=2, seed=seed):
        adapter.write_record(record)
    return MonitoredStore(adapter)
