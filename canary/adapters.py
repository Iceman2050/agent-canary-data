"""Datastore adapters and the monitored watch layer. Stdlib only.

Adapter interface (duck-typed base class ``DatastoreAdapter``)::

    class MyAdapter(DatastoreAdapter):
        def write_record(self, record: CanaryRecord) -> None: ...
        def read_record(self, record_id: str, accessor: str,
                        accessor_context: str = "", query: str = "") -> Optional[dict]: ...
        def list_records(self, accessor: str, accessor_context: str = "",
                         query: str = "") -> list[dict]: ...
        def canary_ids(self) -> set[str]: ...

Rules for custom adapters:
- ``write_record`` persists the record AND registers its id as a canary.
- ``read_record``/``list_records`` must route every read through a
  tripwire check: any record whose id is in ``canary_ids()`` being read
  emits a ``TripwireEvent``.
- ``MonitoredStore`` (below) does this for you — wrap any adapter in it
  and reads are watched automatically. Use it rather than re-implementing
  the check in each adapter.

Two adapters ship: ``JsonFileAdapter`` (flat files, zero setup) and
``SqliteAdapter`` (stdlib sqlite3, transactional).
"""

from __future__ import annotations

import json
import os
import sqlite3
import threading
from typing import Dict, List, Optional, Set

from .core import CanaryRecord, TripwireEvent


class DatastoreAdapter:
    """Duck-typed base class. Subclass and implement the four methods."""

    def write_record(self, record: CanaryRecord) -> None:
        raise NotImplementedError

    def read_record(
        self,
        record_id: str,
        accessor: str,
        accessor_context: str = "",
        query: str = "",
    ) -> Optional[Dict]:
        raise NotImplementedError

    def list_records(
        self,
        accessor: str,
        accessor_context: str = "",
        query: str = "",
    ) -> List[Dict]:
        raise NotImplementedError

    def canary_ids(self) -> Set[str]:
        raise NotImplementedError


# ---------------------------------------------------------------------------
# Monitored watch layer — the tripwire. Any read of a canary record emits a
# TripwireEvent. Wrap ANY DatastoreAdapter with this.
# ---------------------------------------------------------------------------

class MonitoredStore:
    """Watch layer: flags ANY read of a canary record."""

    def __init__(self, adapter: DatastoreAdapter):
        self._adapter = adapter
        self._lock = threading.Lock()
        self._events: List[TripwireEvent] = []

    # -- writes pass straight through -----------------------------------
    def write_record(self, record: CanaryRecord) -> None:
        self._adapter.write_record(record)

    # -- reads are tripwired --------------------------------------------
    def _tripwire(self, record_id: str, accessor: str,
                  accessor_context: str, query: str) -> None:
        if record_id in self._adapter.canary_ids():
            with self._lock:
                self._events.append(
                    TripwireEvent(
                        record_id=record_id,
                        accessor=accessor,
                        accessor_context=accessor_context,
                        query=query,
                    )
                )

    def read_record(self, record_id: str, accessor: str,
                    accessor_context: str = "", query: str = "") -> Optional[Dict]:
        result = self._adapter.read_record(
            record_id, accessor, accessor_context, query
        )
        if result is not None:
            self._tripwire(record_id, accessor, accessor_context,
                           query or f"read_record({record_id})")
        return result

    def list_records(self, accessor: str, accessor_context: str = "",
                     query: str = "") -> List[Dict]:
        results = self._adapter.list_records(accessor, accessor_context, query)
        for r in results:
            self._tripwire(r["record_id"], accessor, accessor_context,
                           query or "list_records()")
        return results

    def events(self) -> List[TripwireEvent]:
        with self._lock:
            return list(self._events)


# ---------------------------------------------------------------------------
# JSON-file adapter
# ---------------------------------------------------------------------------

class JsonFileAdapter(DatastoreAdapter):
    """Flat-file datastore: records.json + canaries.json side by side."""

    def __init__(self, directory: str):
        self.directory = directory
        os.makedirs(directory, exist_ok=True)
        self._records_path = os.path.join(directory, "records.json")
        self._canaries_path = os.path.join(directory, "canaries.json")

    def _load(self, path: str, default):
        if not os.path.exists(path):
            return default
        with open(path, "r", encoding="utf-8") as fh:
            return json.load(fh)

    def _save(self, path: str, payload) -> None:
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, indent=2)

    def write_record(self, record: CanaryRecord) -> None:
        records = self._load(self._records_path, {})
        records[record.record_id] = record.to_dict()
        self._save(self._records_path, records)
        canaries = set(self._load(self._canaries_path, []))
        canaries.add(record.record_id)
        self._save(self._canaries_path, sorted(canaries))

    def read_record(self, record_id: str, accessor: str,
                    accessor_context: str = "", query: str = "") -> Optional[Dict]:
        return self._load(self._records_path, {}).get(record_id)

    def list_records(self, accessor: str, accessor_context: str = "",
                     query: str = "") -> List[Dict]:
        return list(self._load(self._records_path, {}).values())

    def canary_ids(self) -> Set[str]:
        return set(self._load(self._canaries_path, []))


# ---------------------------------------------------------------------------
# SQLite adapter
# ---------------------------------------------------------------------------

class SqliteAdapter(DatastoreAdapter):
    """SQLite datastore via stdlib sqlite3. ``path`` may be a file or ':memory:'."""

    def __init__(self, path: str):
        self.path = path
        # Keep one connection for :memory: so tables persist.
        self._conn = sqlite3.connect(path, check_same_thread=False)
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS records ("
            "record_id TEXT PRIMARY KEY, payload TEXT NOT NULL)"
        )
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS canaries (record_id TEXT PRIMARY KEY)"
        )
        self._conn.commit()

    def write_record(self, record: CanaryRecord) -> None:
        self._conn.execute(
            "INSERT OR REPLACE INTO records (record_id, payload) VALUES (?, ?)",
            (record.record_id, json.dumps(record.to_dict())),
        )
        self._conn.execute(
            "INSERT OR IGNORE INTO canaries (record_id) VALUES (?)",
            (record.record_id,),
        )
        self._conn.commit()

    def read_record(self, record_id: str, accessor: str,
                    accessor_context: str = "", query: str = "") -> Optional[Dict]:
        row = self._conn.execute(
            "SELECT payload FROM records WHERE record_id = ?", (record_id,)
        ).fetchone()
        return json.loads(row[0]) if row else None

    def list_records(self, accessor: str, accessor_context: str = "",
                     query: str = "") -> List[Dict]:
        return [
            json.loads(row[0])
            for row in self._conn.execute("SELECT payload FROM records")
        ]

    def canary_ids(self) -> Set[str]:
        return {
            row[0]
            for row in self._conn.execute("SELECT record_id FROM canaries")
        }

    def close(self) -> None:
        self._conn.close()
