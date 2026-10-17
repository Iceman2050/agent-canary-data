"""Tests for agent-canary-data."""

import pytest

from canary import (
    CanaryRecord,
    TripwireEvent,
    JsonFileAdapter,
    SqliteAdapter,
    MonitoredStore,
)
from canary.core import plant_canaries
from canary.demo import MockAgent, MockDatastore, build_demo_store


def test_clean_agent_trips_nothing():
    store = build_demo_store()
    agent = MockAgent(store, agent_id="agent-clean-01", mode="clean")
    events = agent.run_task("summarize top customers")
    assert events == []
    report = store.events()
    assert report == []


def test_snooping_agent_trips_canary():
    store = build_demo_store()
    agent = MockAgent(store, agent_id="agent-snoop-01", mode="snooping")
    events = agent.run_task("summarize top customers")
    assert len(events) > 0
    assert all(e.record_id.startswith("canary-") for e in events)


def test_trip_report_contains_record_id_and_accessor_context():
    store = build_demo_store()
    agent = MockAgent(
        store, agent_id="agent-snoop-02", mode="snooping"
    )
    agent.run_task("summarize top customers")
    events = store.events()
    assert events, "snooping agent must produce tripwire events"
    for ev in events:
        assert ev.record_id  # record id present
        assert ev.accessor == "agent-snoop-02"  # accessor identity present
        assert "mode=snooping" in ev.accessor_context  # accessor context present
        assert ev.timestamp  # timestamp present
        assert ev.query  # query present
        assert ev.verdict == "AUTHORIZATION-EXCEEDED"


def test_direct_read_of_canary_trips_tripwire():
    store = build_demo_store()
    canary_id = next(iter(store._adapter.canary_ids()))
    result = store.read_record(
        canary_id,
        accessor="agent-direct-01",
        accessor_context="task='fetch record' mode=direct",
        query=f"read_record({canary_id})",
    )
    assert result is not None
    events = store.events()
    assert len(events) == 1
    assert events[0].record_id == canary_id
    assert events[0].accessor == "agent-direct-01"


def test_read_of_real_record_does_not_trip():
    store = build_demo_store()
    result = store.read_record(
        "real-customer-0000",
        accessor="agent-clean-02",
        accessor_context="task='summarize' mode=clean",
        query="get_customer(i=0)",
    )
    assert result is not None
    assert store.events() == []


def test_json_file_adapter_roundtrip(tmp_path):
    adapter = JsonFileAdapter(str(tmp_path))
    records = plant_canaries(count=1, seed=7)
    for r in records:
        adapter.write_record(r)
    assert len(adapter.canary_ids()) == len(records)
    store = MonitoredStore(adapter)
    store.read_record(
        records[0].record_id, accessor="a1", accessor_context="ctx", query="q"
    )
    assert len(store.events()) == 1


def test_sqlite_adapter_roundtrip():
    adapter = SqliteAdapter(":memory:")
    records = plant_canaries(record_types=["credential"], count=2, seed=9)
    for r in records:
        adapter.write_record(r)
    assert len(adapter.canary_ids()) == 2
    store = MonitoredStore(adapter)
    store.list_records(accessor="a2", accessor_context="ctx", query="q")
    assert len(store.events()) == 2
    adapter.close()


def test_plant_canaries_deterministic():
    a = plant_canaries(count=2, seed=123)
    b = plant_canaries(count=2, seed=123)
    assert [r.record_id for r in a] == [r.record_id for r in b]


def test_events_serialize_roundtrip():
    ev = TripwireEvent(
        record_id="canary-abc123", accessor="agent-x",
        accessor_context="mode=test", query="q"
    )
    restored = TripwireEvent.from_dict(ev.to_dict())
    assert restored.record_id == ev.record_id
    assert restored.accessor_context == ev.accessor_context
