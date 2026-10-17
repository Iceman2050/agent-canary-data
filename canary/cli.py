"""CLI: plant | monitor | report. Stdlib only."""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from typing import List

from .adapters import JsonFileAdapter, MonitoredStore, SqliteAdapter
from .core import TripwireEvent, plant_canaries
from .demo import build_demo_store, MockAgent

EVENTS_DIR = os.environ.get("CANARY_DATA_DIR", os.path.expanduser("~/.canary-data"))


def _events_path(directory: str) -> str:
    return os.path.join(directory, "events.jsonl")


def _load_events(directory: str) -> List[dict]:
    path = _events_path(directory)
    events: List[dict] = []
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if line:
                    events.append(json.loads(line))
    return events


def _append_events(directory: str, events: List[TripwireEvent]) -> None:
    if not events:
        return
    os.makedirs(directory, exist_ok=True)
    with open(_events_path(directory), "a", encoding="utf-8") as fh:
        for ev in events:
            fh.write(json.dumps(ev.to_dict()) + "\n")


def _make_store(args, monitored: bool = True):
    if args.backend == "sqlite":
        adapter = SqliteAdapter(args.sqlite_path)
    else:
        adapter = JsonFileAdapter(args.dir)
    return MonitoredStore(adapter) if monitored else adapter


# ---------------------------------------------------------------------------
# plant
# ---------------------------------------------------------------------------

def cmd_plant(args) -> int:
    records = plant_canaries(
        record_types=args.types.split(",") if args.types else None,
        count=args.count,
        seed=args.seed,
    )
    store = _make_store(args, monitored=False)
    for record in records:
        store.write_record(record)
    print(f"Planted {len(records)} canary record(s):")
    for record in records:
        print(f"  {record.record_id}  [{record.record_type}]")
    return 0


# ---------------------------------------------------------------------------
# monitor
# ---------------------------------------------------------------------------

def cmd_monitor(args) -> int:
    """Run a simulated agent session and watch for canary touches."""
    store = _make_store(args, monitored=True)
    agent = MockAgent(
        store, agent_id=args.agent_id, mode=args.mode
    )
    events = agent.run_task(args.task)
    _append_events(args.dir, events)
    print(f"Monitor session complete: {len(events)} tripwire event(s).")
    for ev in events:
        print(
            f"  TRIPPED {ev.record_id} by {ev.accessor} "
            f"@ {ev.timestamp}"
        )
    if not events:
        print("  (clean — no canary records were read)")
    return 0


# ---------------------------------------------------------------------------
# report
# ---------------------------------------------------------------------------

def cmd_report(args) -> int:
    events = _load_events(args.dir)
    if args.json:
        print(json.dumps(events, indent=2))
        return 0
    if not events:
        print("No tripwire events. Report is empty — no agent exceeded authorization.")
        return 0
    print(f"{len(events)} tripwire event(s) — AUTHORIZATION EXCEEDED:")
    print()
    for ev in events:
        print(f"  record_id : {ev['record_id']}")
        print(f"  accessor  : {ev['accessor']}")
        print(f"  context   : {ev['accessor_context']}")
        print(f"  timestamp : {ev['timestamp']}")
        print(f"  query     : {ev['query']}")
        print(f"  verdict   : {ev['verdict']}")
        print()
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="canary",
        description="Canary data tripwires: plant fake records, monitor reads, report trips.",
    )
    p.add_argument("--dir", default=os.path.join(EVENTS_DIR, "store"),
                   help="datastore/event directory (default ~/.canary-data/store)")
    p.add_argument("--backend", choices=["json", "sqlite"], default="json")
    p.add_argument("--sqlite-path", default=os.path.join(EVENTS_DIR, "store.db"),
                   help="sqlite file when --backend sqlite")
    sub = p.add_subparsers(dest="command", required=True)

    pp = sub.add_parser("plant", help="generate and plant canary records")
    pp.add_argument("--types", default=None,
                    help="comma-separated: customer,credential,file")
    pp.add_argument("--count", type=int, default=3,
                    help="canaries per type (default 3)")
    pp.add_argument("--seed", type=int, default=None)
    pp.set_defaults(func=cmd_plant)

    mp = sub.add_parser("monitor", help="run a watched agent session")
    mp.add_argument("--agent-id", default="agent-demo-01")
    mp.add_argument("--mode", choices=["clean", "snooping"], default="clean")
    mp.add_argument("--task", default="summarize top customers")
    mp.set_defaults(func=cmd_monitor)

    rp = sub.add_parser("report", help="list tripped canaries")
    rp.add_argument("--json", action="store_true")
    rp.set_defaults(func=cmd_report)

    return p


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
